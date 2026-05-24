"""
Long-tail SEO seeder — يُنشئ وظائف توليد لصفحات بكلمات طويلة منخفضة
المنافسة بدلاً من انتظار trends.py.

لماذا long-tail؟
  • "كود نون" = منافسة قمّة، مستحيل ترتيب أول 6 أشهر
  • "كود خصم نون رمضان 2026" = منافسة ضعيفة، ترتيب صفحة 1-2 خلال 4-8 أسابيع
  • 50 صفحة long-tail تجلب زواراً أكثر من 5 صفحات على كلمات عامة

أنماط الكلمات (تُدمج مع اسم كل متجر من جدول master):
  1. كود خصم {store} 2026
  2. كوبون {store} {month}                  (يناير، فبراير، ... الشهر الحالي والقادم)
  3. {store} شحن مجاني
  4. {store} كود خصم نسائي
  5. كود خصم {store} الرياض / جدة / الدمام
  6. {store} عروض رمضان / اليوم الوطني / يوم التأسيس / الجمعة البيضاء
  7. أفضل كود خصم {store} (الأعلى تحويلاً)
  8. {store} كوبون شغّال (قصد المستخدم: التحقّق من الصلاحية)

التكلفة المتوقّعة لـ 50 صفحة:
  • Gemini Pro: ~$0.0003 × 50 = $0.015 (1.5 سنت)
  • bilingual = 50 عربي + 50 إنجليزي = $0.03 (3 سنت)
  • تحت سقف Financial Guardian اليومي ($5) بكثير

الاستخدام:
  • API: POST /admin/seo-seed-long-tail (يُنشئ الوظائف)
        ثم: POST /admin/seo-run?batch=20 (يولّد دفعة)
  • CLI:  python -m api.seo.seed_long_tail  (يُنشئ الوظائف فقط)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from psycopg2.extras import RealDictCursor

from api.db import get_db_context

_log = logging.getLogger("dp.seo.seed_long_tail")


# ─── أنماط الكلمات الطويلة (templates) ──────────────────────────────────────
LONG_TAIL_PATTERNS_AR: list[str] = [
    "كود خصم {store} 2026",
    "كوبون {store} شحن مجاني",
    "{store} كود خصم نسائي",
    "كود خصم {store} الرياض",
    "كود خصم {store} جدة",
    "{store} عروض رمضان",
    "{store} كود خصم اليوم الوطني",
    "{store} عروض الجمعة البيضاء",
    "أفضل كود خصم {store}",
    "{store} كوبون شغّال",
]

# نضيف أنماطاً موسمية بحسب الشهر الحالي (Google يفضّل المحتوى الموسمي)
SEASONAL_PATTERNS_AR: dict[int, list[str]] = {
    # رقم الشهر → [أنماط مخصّصة]
    1:  ["{store} عروض رأس السنة"],
    2:  ["{store} كود خصم يوم التأسيس", "{store} كوبون فبراير"],
    3:  ["{store} عروض رمضان", "{store} كود خصم العشر الأواخر"],
    4:  ["{store} عروض عيد الفطر"],
    6:  ["{store} عروض الصيف"],
    8:  ["{store} عروض العودة للمدارس"],
    9:  ["{store} كود خصم اليوم الوطني السعودي"],
    11: ["{store} عروض الجمعة البيضاء", "{store} كود خصم Black Friday"],
    12: ["{store} عروض نهاية العام", "{store} كود خصم Cyber Monday"],
}


def _build_keywords(store_name: str, store_id: str) -> list[str]:
    """يبني قائمة كلمات long-tail لمتجر معيّن."""
    # نستخدم name_en إن وُجد كنسخة إنجليزية، اسم المتجر العربي/store_id للعربي
    name = (store_name or store_id).strip()
    keywords: list[str] = []

    for pat in LONG_TAIL_PATTERNS_AR:
        keywords.append(pat.format(store=name))

    # أضف الأنماط الموسمية للشهر الحالي
    month = datetime.now().month
    for pat in SEASONAL_PATTERNS_AR.get(month, []):
        keywords.append(pat.format(store=name))

    return keywords


def _enqueue_job(cur, keyword: str, master_id: int) -> Optional[int]:
    """
    يحقن seo_generation_jobs إن لم تكن الكلمة موجودة مسبقاً (بأي حالة).
    يرجّع job_id الجديد، أو None لو موجودة بالفعل.
    """
    # تكرار 1: في job سابق (queued/running/completed/failed)
    cur.execute(
        "SELECT id FROM seo_generation_jobs WHERE target_keyword = %s LIMIT 1",
        (keyword,),
    )
    if cur.fetchone():
        return None

    # تكرار 2: في صفحة منشورة بالفعل
    cur.execute(
        "SELECT id FROM seo_landing_pages WHERE target_keyword = %s LIMIT 1",
        (keyword,),
    )
    if cur.fetchone():
        return None

    cur.execute(
        """
        INSERT INTO seo_generation_jobs
            (target_keyword, matched_master_id, state)
        VALUES (%s, %s, 'queued')
        RETURNING id
        """,
        (keyword, master_id),
    )
    return cur.fetchone()[0]


def seed_long_tail_jobs(*, max_stores: int = 30, sort_by: str = "trending") -> dict:
    """
    يولّد وظائف long-tail لأهمّ المتاجر.

    Args:
        max_stores: عدد المتاجر التي ننتقي منها (افتراضي 30)
        sort_by: 'trending' (افتراضي) | 'engagement' | 'recent'

    Returns:
        {stores_processed, jobs_enqueued, jobs_skipped_duplicate, errors}
    """
    # ترتيب المتاجر — نُولّد للأكثر تفاعلاً أولاً
    order_clause = {
        "trending":   "ORDER BY (COALESCE(total_link_clicks, 0) + "
                      "COALESCE(total_coupon_copies, 0) * 2) DESC NULLS LAST",
        "engagement": "ORDER BY COALESCE(total_coupon_copies, 0) DESC NULLS LAST",
        "recent":     "ORDER BY id DESC",
    }.get(sort_by, "ORDER BY id DESC")

    stats = {
        "stores_processed":        0,
        "jobs_enqueued":           0,
        "jobs_skipped_duplicate":  0,
        "errors":                  0,
    }

    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, store_id,
                       COALESCE(NULLIF(name_en, ''), store_id) AS display_name
                FROM master
                WHERE COALESCE(affiliate_link, '') <> ''
                {order_clause}
                LIMIT %s
                """,
                (max_stores,),
            )
            stores = cur.fetchall()

        if not stores:
            return {**stats, "warning": "no_stores_with_affiliate_link"}

        for store in stores:
            stats["stores_processed"] += 1
            keywords = _build_keywords(store["display_name"], store["store_id"])

            with conn.cursor() as cur:
                for kw in keywords:
                    try:
                        job_id = _enqueue_job(cur, kw, store["id"])
                        if job_id:
                            stats["jobs_enqueued"] += 1
                        else:
                            stats["jobs_skipped_duplicate"] += 1
                    except Exception as exc:
                        _log.warning("enqueue failed for '%s': %s", kw, str(exc)[:120])
                        stats["errors"] += 1

    _log.info("Long-tail seed complete: %s", stats)
    return stats


if __name__ == "__main__":
    # تشغيل CLI: python -m api.seo.seed_long_tail
    import json as _json
    result = seed_long_tail_jobs()
    print(_json.dumps(result, indent=2, ensure_ascii=False))
    print("\nالخطوة التالية:")
    print("  curl -X POST 'https://api.dealpulseksa.com/api/v1/admin/seo-run?batch=20' "
          "-H 'X-Admin-Secret: <secret>'")
