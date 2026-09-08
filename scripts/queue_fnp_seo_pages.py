"""
يصفّ صفحات هبوط /c/ لفيرنز اند بيتل (master.id=82) ثم يولّدها عبر الـ LLM.

نفس مسار ناتشورال تاتش (jobs 91-93): إدراج صفوف queued في seo_generation_jobs
ثم process_pending_jobs. الكلمات مختارة يدوياً من Google Autocomplete السعودي
(gl=sa) لا من قوالب seed_long_tail العامة — طلب FNP الحقيقي توصيل الورد لا
«كود خصم {store} 2026».

الناتج صفحات status='draft' في seo_landing_pages تُراجَع وتُنشر يدوياً.
bilingual مفعّل افتراضياً (AR + EN لكل كلمة).

الاستخدام:
    python -m scripts.queue_fnp_seo_pages          # يصفّ ثم يولّد
    python -m scripts.queue_fnp_seo_pages --queue-only
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # ويندوز cp1252 يـcrash على العربية
    except (AttributeError, ValueError):
        pass

from api.db import get_db_context
from api.seo.generator import process_pending_jobs

MASTER_ID = 82

KEYWORDS = [
    "كوبون فيرنز اند بيتل",
    "توصيل ورد الرياض",
    "توصيل ورد جدة",
    "فيرنز اند بيتل",
]


def queue() -> list[int]:
    ids: list[int] = []
    with get_db_context() as conn:
        with conn.cursor() as cur:
            for kw in KEYWORDS:
                cur.execute(
                    "SELECT id FROM seo_generation_jobs "
                    "WHERE matched_master_id=%s AND target_keyword=%s",
                    (MASTER_ID, kw),
                )
                row = cur.fetchone()
                if row:
                    print(f"  = موجود مسبقاً: {kw} (job {row[0]})")
                    continue
                cur.execute(
                    "INSERT INTO seo_generation_jobs "
                    "(target_keyword, matched_master_id, state) "
                    "VALUES (%s, %s, 'queued') RETURNING id",
                    (kw, MASTER_ID),
                )
                jid = cur.fetchone()[0]
                ids.append(jid)
                print(f"  + queued: {kw} (job {jid})")
    return ids


if __name__ == "__main__":
    print("صفّ وظائف FNP…")
    queued = queue()
    print(f"صُفّ {len(queued)} وظيفة جديدة.")
    if "--queue-only" in sys.argv:
        sys.exit(0)
    if not queued:
        print("لا جديد — تخطّي التوليد.")
        sys.exit(0)
    print("توليد…")
    stats = process_pending_jobs(batch=len(queued) * 2)
    print(stats)
