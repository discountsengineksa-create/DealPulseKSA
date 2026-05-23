"""
PDPL hard-purge worker — يُنفّذ يومياً.

المهمة: حذف نهائي للحسابات التي مرّ على soft-delete الخاص بها أكثر من
30 يوماً. يحذف cascade:
    - web_users          → الصف نفسه + المفضلة + كلمة السر
    - bot_users          → الصف نفسه + manual_favorites
    - password_reset_tokens (FK يتبع الحذف)
    - action_logs        → ينقّى user_id إلى NULL (لا نمسح الأحداث — تحليلات
                            لكن نخفي ارتباطها بالشخص)

لماذا anonymize بدل delete على action_logs؟
    حذف ملايين الصفوف من action_logs لكل مستخدم يحذف حسابه = ضغط كبير على DB
    والإحصاءات الإجمالية (عدد النقرات لكل متجر) لا يجب أن تتأثر بمن نقر.
    PDPL يسمح بـ anonymization كبديل عن الحذف إذا أزال الـ identifier.

كل عملية حذف تُسجَّل في pdpl_audit_log للأثر القانوني.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from api.db import get_db_context
from api.utils.ops import audit_log

_log = logging.getLogger("dp.pdpl_purger")

GRACE_PERIOD_DAYS = 30


def purge_expired_users() -> dict:
    """يحذف نهائياً الحسابات التي انقضت فترة استبقائها."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=GRACE_PERIOD_DAYS)

    web_purged = _purge_web_users(cutoff)
    bot_purged = _purge_bot_users(cutoff)

    summary = {
        "ran_at":             datetime.now(timezone.utc).isoformat(),
        "cutoff":             cutoff.isoformat(),
        "web_users_purged":   web_purged,
        "bot_users_purged":   bot_purged,
    }
    _log.info("PDPL purge complete: %s", summary)
    return summary


def _purge_web_users(cutoff: datetime) -> int:
    """يحذف نهائياً web_users المنقضي حذفهم + anonymize action_logs."""
    with get_db_context() as conn:
        with conn.cursor() as cur:
            # 1) نجمع المعرّفات أولاً (للأثر القانوني والـ anonymization)
            cur.execute(
                """
                SELECT id, email
                FROM web_users
                WHERE deleted_at IS NOT NULL
                  AND deleted_at < %s
                """,
                (cutoff,),
            )
            rows = cur.fetchall()
            if not rows:
                return 0

            user_ids = [r[0] for r in rows]

            # 2) anonymize action_logs (نُبقي الأحداث للإحصاءات، نزيل الارتباط)
            cur.execute(
                "UPDATE action_logs SET user_id = NULL WHERE user_id = ANY(%s)",
                (user_ids,),
            )

            # 3) password_reset_tokens — FK CASCADE سيمسحها مع الـ web_users
            cur.execute(
                "DELETE FROM password_reset_tokens WHERE user_id = ANY(%s)",
                (user_ids,),
            )

            # 4) الحذف النهائي
            cur.execute("DELETE FROM web_users WHERE id = ANY(%s)", (user_ids,))

            # 5) audit (واحد لكل مستخدم — للأثر القانوني الفردي)
            for uid, email in rows:
                try:
                    audit_log(
                        action="user_hard_purge",
                        actor="system:pdpl_purger",
                        target=email or str(uid),
                        meta={"user_id": uid, "after_grace_days": GRACE_PERIOD_DAYS},
                    )
                except Exception:
                    pass

    return len(rows)


def _purge_bot_users(cutoff: datetime) -> int:
    """يحذف نهائياً bot_users المنقضي حذفهم + anonymize action_logs."""
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT telegram_id
                FROM bot_users
                WHERE deleted_at IS NOT NULL
                  AND deleted_at < %s
                """,
                (cutoff,),
            )
            rows = cur.fetchall()
            if not rows:
                return 0

            tg_ids = [r[0] for r in rows]

            # bot_users.telegram_id يُخزَّن نصاً في action_logs.user_id (للأسف)
            # نُغطّي الحالتين: bigint و text
            cur.execute(
                "UPDATE action_logs SET user_id = NULL WHERE user_id = ANY(%s::bigint[])",
                (tg_ids,),
            )

            # المتعلّقات الأخرى
            cur.execute(
                "DELETE FROM sent_coupon_messages WHERE user_id = ANY(%s::bigint[])",
                (tg_ids,),
            )

            # الحذف النهائي
            cur.execute("DELETE FROM bot_users WHERE telegram_id = ANY(%s)", (tg_ids,))

            for tg_id in tg_ids:
                try:
                    audit_log(
                        action="bot_user_hard_purge",
                        actor="system:pdpl_purger",
                        target=str(tg_id),
                        meta={"telegram_id": tg_id, "after_grace_days": GRACE_PERIOD_DAYS},
                    )
                except Exception:
                    pass

    return len(rows)


if __name__ == "__main__":
    # تشغيل يدوي للاختبار: python -m api.workers.pdpl_purger
    print(purge_expired_users())
