"""
محرّك SEO الأوتوماتيكي (المرحلة 1) — توليد + نشر صفحات هبوط يومياً بلا تدخّل بشري.

يُشغَّل 3 صباحاً (Riyadh) من المجدول (api/workers/scheduler.py):
  1. اختيار المتاجر الجديدة (بلا صفحة منشورة) مرتّبة بالشعبية الكلية — بكوبون فعّال فقط.
  2. ربطها بمناسبة سعودية قادمة خلال 14 يوم (seasonal_events.occasion_date).
  3. إنشاء seo_generation_jobs (الكلمة المستهدفة تتضمّن المناسبة إن وُجدت).
  4. التوليد عبر الـ LLM (generator.process_pending_jobs) — يطبّق الحظر على
     الكلمة (matcher) وعلى نص الصفحة (generator) عربي/إنجليزي.
  5. نشر تلقائي **مُبوّب**: كوبون فعّال + حد أدنى للطول + سقف يومي + IndexNow.
     لا مراجعة يدوية — لكن بوابات آلية تحمي الدومين من محتوى رقيق/مكرّر.

التحكّم بالبيئة (على خدمة الـ API):
  SEO_AUTO_PUBLISH_ENABLED  — 'true' لتفعيل النشر التلقائي (افتراضي معطّل للأمان)
  SEO_TOP_STORES            — عدد المتاجر يومياً (افتراضي 4)
  SEO_DAILY_PUBLISH_CAP     — أقصى صفحات تُنشر/يوم (افتراضي 10 = ~4 متاجر × لغتين)
  SEO_MIN_BODY_WORDS        — أدنى عدد كلمات لنشر الصفحة (افتراضي 350)
"""
from __future__ import annotations

import logging
import os
import re

from psycopg2.extras import RealDictCursor

from api.db import get_db_context

_log = logging.getLogger("dp.seo.auto")

TOP_N = int(os.getenv("SEO_TOP_STORES", "4"))
DAILY_PUBLISH_CAP = int(os.getenv("SEO_DAILY_PUBLISH_CAP", "10"))
MIN_BODY_WORDS = int(os.getenv("SEO_MIN_BODY_WORDS", "350"))
OCCASION_WINDOW_DAYS = 14


def select_top_demand_stores(cur, n: int) -> list[dict]:
    """المتاجر المؤهّلة للتوليد — **الجديدة أولاً** (بلا صفحة منشورة) مرتّبة بالشعبية
    الكلية (نقرات + نسخ ×2). تغطية كاملة: لا تعتمد على طلب آخر 24 ساعة.
    بوابات White-Hat: كوبون فعّال + غير موقوف + قناة website + seo_enabled (قائمة المنع).
    المتاجر المُغطّاة (لها صفحة منشورة) لا تُرجَع — دورة التحديث مرحلة منفصلة."""
    cur.execute(
        """
        SELECT m.id,
               COALESCE(NULLIF(m.name_en, ''), m.store_id) AS store_name,
               (COALESCE(m.total_link_clicks, 0)
                + COALESCE(m.total_coupon_copies, 0) * 2) AS demand
        FROM master m
        WHERE m.public_coupon IS NOT NULL AND m.public_coupon <> ''
          AND COALESCE(m.is_suspended, FALSE) = FALSE
          -- يحترم قنوات النشر: لا نولّد صفحة SEO عامة لمتجر مخفيّ عن الموقع
          -- (مثل متجر منعه المعلن من القناة، أو حصري للبوت). NULL = كل القنوات.
          AND (m.publish_channels IS NULL OR m.publish_channels ILIKE '%%website%%')
          -- قائمة المنع: معلن يمنع SEO على البراند → نستثنيه نهائياً (خطر حظر).
          AND COALESCE(m.seo_enabled, TRUE) = TRUE
          -- التغطية أولاً: فقط المتاجر اللي ما لها صفحة منشورة بعد.
          AND NOT EXISTS (
              SELECT 1 FROM seo_landing_pages p
              WHERE p.master_id = m.id AND p.status = 'published'
          )
        ORDER BY demand DESC
        LIMIT %s
        """,
        (n,),
    )
    return [dict(r) for r in cur.fetchall()]


def upcoming_occasion(cur) -> dict | None:
    """أقرب مناسبة سعودية قادمة خلال نافذة OCCASION_WINDOW_DAYS (أو None)."""
    cur.execute(
        """
        SELECT event_name, occasion_date
        FROM seasonal_events
        WHERE occasion_date IS NOT NULL
          AND occasion_date BETWEEN CURRENT_DATE
                               AND CURRENT_DATE + (%s || ' days')::interval
        ORDER BY occasion_date ASC
        LIMIT 1
        """,
        (OCCASION_WINDOW_DAYS,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def enqueue_for_stores(cur, stores: list[dict], occasion: dict | None) -> int:
    """ينشئ وظيفة توليد لكل متجر — الكلمة المستهدفة تتضمّن المناسبة إن وُجدت."""
    occ = (occasion or {}).get("event_name")
    enq = 0
    for s in stores:
        if occ:
            kw = f"كود خصم {s['store_name']} {occ} 2026"
        else:
            kw = f"كود خصم {s['store_name']} 2026"
        cur.execute(
            """
            INSERT INTO seo_generation_jobs
                (trend_signal_id, target_keyword, matched_master_id, state)
            VALUES (NULL, %s, %s, 'queued')
            ON CONFLICT (target_keyword, matched_master_id)
                WHERE state IN ('queued', 'running')
                DO NOTHING
            """,
            (kw, s["id"]),
        )
        enq += cur.rowcount
    return enq


def auto_publish(cur, cap: int) -> list[dict]:
    """ينشر المسودّات المؤهَّلة (بوابات White-Hat) حتى السقف اليومي.
    البوابات: كوبون فعّال + حد أدنى طول + **تفرّد** (لا ننشر صفحة شبه مطابقة لمنشورة)."""
    cur.execute(
        """
        SELECT p.id, p.slug, p.lang, p.target_keyword, p.title_meta
        FROM seo_landing_pages p
        JOIN master m ON m.id = p.master_id
        WHERE p.status = 'draft'
          AND m.public_coupon IS NOT NULL AND m.public_coupon <> ''
          AND COALESCE(m.is_suspended, FALSE) = FALSE
          -- قائمة المنع: لا ننشر صفحة لمتجر مُعطّل SEO (خط الدفاع الأخير).
          AND COALESCE(m.seo_enabled, TRUE) = TRUE
          AND array_length(regexp_split_to_array(trim(p.body_markdown), '\\s+'), 1) >= %s
        ORDER BY p.id ASC
        """,
        (MIN_BODY_WORDS,),
    )
    candidates = [dict(r) for r in cur.fetchall()]
    published: list[dict] = []
    for d in candidates:
        if len(published) >= cap:
            break
        # تفرّد: تخطّى لو فيه صفحة منشورة بنفس الكلمة أو عنوان شبه مطابق (>0.7)
        cur.execute(
            """
            SELECT 1 FROM seo_landing_pages pub
            WHERE pub.status = 'published' AND pub.lang = %s
              AND (pub.target_keyword = %s OR similarity(pub.title_meta, %s) > 0.7)
            LIMIT 1
            """,
            (d["lang"], d["target_keyword"], d.get("title_meta") or ""),
        )
        if cur.fetchone():
            cur.execute("UPDATE seo_landing_pages SET status='rejected_dup' WHERE id=%s",
                        (d["id"],))
            continue
        cur.execute(
            "UPDATE seo_landing_pages SET status='published', published_at=NOW(), "
            "last_indexed_at=NOW() WHERE id=%s",
            (d["id"],),
        )
        published.append(d)
    return published


def run_daily_seo_cycle(force: bool = False) -> dict:
    """الدورة اليومية الكاملة (المجدول 3ص، أو يدوياً بـ force=True من الداشبورد)."""
    if not force and os.getenv("SEO_AUTO_PUBLISH_ENABLED", "false").lower() not in ("1", "true", "yes"):
        _log.info("seo auto-publish disabled (SEO_AUTO_PUBLISH_ENABLED!=true) — skip")
        return {"enabled": False}

    from api.seo.generator import process_pending_jobs

    # 1-3) اختيار + ربط مناسبة + enqueue
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            stores = select_top_demand_stores(cur, TOP_N)
            occ = upcoming_occasion(cur)
            enqueued = enqueue_for_stores(cur, stores, occ) if stores else 0
        conn.commit()

    _log.info("seo daily: top_stores=%d occasion=%s enqueued=%d",
              len(stores), (occ or {}).get("event_name"), enqueued)

    # 4) توليد (LLM) — كل متجر = صفحتان (ع+إ)
    gen = process_pending_jobs(batch=max(TOP_N, 1)) if enqueued else {"generated": 0}

    # 5) نشر مُبوّب + IndexNow
    published = []
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            published = auto_publish(cur, DAILY_PUBLISH_CAP)
        conn.commit()

    if published:
        try:
            from api.seo.indexer import submit_page
            for p in published:
                try:
                    submit_page(landing_page_id=p["id"], slug=p["slug"])
                except Exception as ex:  # noqa: BLE001
                    _log.warning("indexnow failed for %s: %s", p["slug"], ex)
        except Exception as ex:  # noqa: BLE001
            _log.warning("indexer import failed: %s", ex)

    try:
        from api.utils.ops import audit_log
        audit_log(action="seo_auto_cycle", target="daily",
                  meta={"stores": len(stores), "occasion": (occ or {}).get("event_name"),
                        "enqueued": enqueued, "generated": gen.get("generated", 0),
                        "published": len(published)})
    except Exception:  # noqa: BLE001
        pass

    result = {
        "enabled": True,
        "top_stores": len(stores),
        "occasion": (occ or {}).get("event_name"),
        "enqueued": enqueued,
        "generated": gen.get("generated", 0),
        "published": len(published),
    }
    _log.info("seo daily cycle done: %s", result)
    return result
