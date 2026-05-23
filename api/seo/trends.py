"""
Trend ingestion — المصدر المجاني: سجلّ البحث الداخلي (direct_search).

يجمّع ما يبحث عنه المستخدمون فعلاً (آخر N يوم) ويحوّله إلى صفوف
trend_signals(source='internal_search'). كل كلمة = صف واحد متطوّر
(UPSERT على source+query_text+geo)، فالـ interest_score يعكس آخر تجميع.

مصادر خارجية (google_trends / serpapi) تُضاف لاحقاً بنفس واجهة الكتابة
لكنها تحتاج مفاتيح API — خارج نطاق هذه المرحلة.
"""
from __future__ import annotations

import logging

from api.db import get_db_context

_log = logging.getLogger("dp.seo.trends")

DEFAULT_WINDOW_DAYS = 30
DEFAULT_MIN_COUNT = 1   # بياناتنا لسا قليلة — نخفّض الحدّ، نرفعه مع النمو


def aggregate_internal_search(
    *, days: int = DEFAULT_WINDOW_DAYS, min_count: int = DEFAULT_MIN_COUNT
) -> int:
    """
    يجمّع direct_search خلال نافذة days ويحدّث trend_signals.
    يرجّع عدد الكلمات المُدخلة/المحدّثة.
    """
    upserted = 0
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH agg AS (
                    SELECT
                        lower(trim(search_keyword))                       AS q,
                        count(*)                                          AS cnt,
                        max(search_date)                                  AS last_seen
                    FROM direct_search
                    WHERE search_date > NOW() - (%s || ' days')::interval
                      AND trim(COALESCE(search_keyword, '')) <> ''
                    GROUP BY lower(trim(search_keyword))
                    HAVING count(*) >= %s
                )
                INSERT INTO trend_signals
                    (source, query_text, geo, interest_score, velocity_score, captured_at)
                SELECT
                    'internal_search', q, 'SA',
                    cnt,
                    ROUND(cnt::numeric / GREATEST(%s, 1), 2),
                    NOW()
                FROM agg
                ON CONFLICT (source, query_text, geo) DO UPDATE
                SET interest_score = EXCLUDED.interest_score,
                    velocity_score = EXCLUDED.velocity_score,
                    captured_at    = EXCLUDED.captured_at
                """,
                (days, min_count, days),
            )
            upserted = cur.rowcount

    _log.info("internal_search trends upserted: %d (window=%dd, min=%d)",
              upserted, days, min_count)
    return upserted
