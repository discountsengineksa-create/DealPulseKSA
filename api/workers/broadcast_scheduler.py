"""
Worker جدولة الحملات.

يفحص الجداول المستحقّة (next_run_at <= NOW) ويرسلها.
يجب أن يُشغَّل كل دقيقة (cron أو Railway scheduled job).

الاستخدام:
    python api/workers/broadcast_scheduler.py

أو من cron (مرة كل دقيقة):
    * * * * * /usr/bin/python /app/api/workers/broadcast_scheduler.py >> /var/log/dp_sched.log 2>&1

النتيجة تُكتب لـ stdout (JSON list من الإرسالات).
"""
from __future__ import annotations

import json
import logging
import sys

from api.db import get_db_context
from api.audience_sender import process_due_schedules

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
_log = logging.getLogger("dp.scheduler")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    try:
        with get_db_context() as conn:
            conn.autocommit = True
            results = process_due_schedules(conn)
    except Exception as exc:
        _log.exception("scheduler failed: %s", exc)
        return 1

    if not results:
        _log.info("لا جداول مستحقّة الآن.")
        return 0

    _log.info("شُغّلت %d جدولة:", len(results))
    print(json.dumps(results, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
