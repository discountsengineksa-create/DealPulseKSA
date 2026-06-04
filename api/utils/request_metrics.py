"""
API request metrics — مراقبة أداء الموقع الحقيقية (زمن الاستجابة + الأخطاء).

التصميم (لا يُبطّئ أي طلب):
  • middleware يقيس كل طلب ويستدعي record_request() — مجرّد append في الذاكرة
    تحت قفل خفيف (بلا I/O في مسار الطلب).
  • thread خلفي (run_metrics_flusher) يكبس الدفعات لجدول api_request_metrics
    كل FLUSH_SECONDS، ويُنظّف الصفوف الأقدم من RETENTION_DAYS مرة كل ساعة.
  • buffer محدود (maxlen) — لو تعطّل الـ flusher يسقط الأقدم بدل ما تنفجر الذاكرة.

الجدول يُنشأ تلقائياً عند أول كبسة (CREATE TABLE IF NOT EXISTS) فتشتغل الميزة
فوراً دون انتظار migration_033 يدوياً.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque

from psycopg2.extras import execute_values

from api.db import get_db_context

_log = logging.getLogger("dp.metrics")

FLUSH_SECONDS = 5
RETENTION_DAYS = 7
_CLEANUP_EVERY_SEC = 3600

_BUF: deque = deque(maxlen=20000)
_LOCK = threading.Lock()

_DDL = """
CREATE TABLE IF NOT EXISTS api_request_metrics (
    id          BIGSERIAL   PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    method      VARCHAR(8),
    path        TEXT,
    status_code SMALLINT,
    latency_ms  INTEGER
)
"""
_DDL_IDX1 = ("CREATE INDEX IF NOT EXISTS idx_api_metrics_created "
             "ON api_request_metrics (created_at DESC)")
_DDL_IDX2 = ("CREATE INDEX IF NOT EXISTS idx_api_metrics_errors "
             "ON api_request_metrics (created_at DESC) WHERE status_code >= 500")

# مسارات لا قيمة لمراقبتها (ضوضاء)
_SKIP_PREFIXES = ("/docs", "/openapi", "/redoc", "/favicon", "/static", "/health")

_NUM = re.compile(r"^\d+$")


def _norm_path(path: str) -> str:
    """يقلّص المسارات عالية التنوّع لقوالب حتى يبقى التجميع ذا معنى."""
    path = (path or "/").split("?", 1)[0]
    out = []
    for s in path.split("/"):
        if not s:
            out.append(s)
        elif _NUM.match(s):
            out.append("{id}")
        elif len(s) > 24:
            out.append("{slug}")
        else:
            out.append(s)
    norm = "/".join(out) or "/"
    norm = re.sub(r"^/go/[^/]+", "/go/{slug}", norm)
    return norm[:200]


def record_request(method: str, path: str, status_code: int, latency_ms: int) -> None:
    """يُستدعى من الـ middleware لكل طلب. سريع، بلا I/O، لا يرمي أبداً."""
    try:
        p = path or "/"
        if any(p.startswith(pre) for pre in _SKIP_PREFIXES):
            return
        if (method or "").upper() == "OPTIONS":
            return
        with _LOCK:
            _BUF.append(((method or "")[:8], _norm_path(p), int(status_code), int(latency_ms)))
    except Exception:
        pass


def _drain() -> list:
    with _LOCK:
        if not _BUF:
            return []
        items = list(_BUF)
        _BUF.clear()
        return items


def _flush_once() -> int:
    items = _drain()
    if not items:
        return 0
    try:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
                execute_values(
                    cur,
                    "INSERT INTO api_request_metrics (method, path, status_code, latency_ms) VALUES %s",
                    items,
                )
        return len(items)
    except Exception as exc:
        _log.warning("metrics flush failed (%d rows dropped): %s", len(items), exc)
        return 0


def _cleanup_old() -> None:
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(_DDL)
            cur.execute(_DDL_IDX1)
            cur.execute(_DDL_IDX2)
            cur.execute(
                "DELETE FROM api_request_metrics "
                "WHERE created_at < NOW() - make_interval(days => %s)",
                (RETENTION_DAYS,),
            )


def run_metrics_flusher(stop_event=None) -> None:
    """حلقة الكبس الخلفية. تعمل كـ daemon thread في كل عملية worker."""
    _log.info("✅ api-metrics flusher started (every %ds, retain %dd)",
              FLUSH_SECONDS, RETENTION_DAYS)
    last_cleanup = 0.0
    while not (stop_event is not None and stop_event.is_set()):
        time.sleep(FLUSH_SECONDS)
        try:
            _flush_once()
        except Exception as exc:
            _log.warning("metrics flush loop error: %s", exc)
        now = time.time()
        if now - last_cleanup > _CLEANUP_EVERY_SEC:
            last_cleanup = now
            try:
                _cleanup_old()
            except Exception as exc:
                _log.warning("metrics cleanup error: %s", exc)


def start_metrics_flusher() -> threading.Thread:
    """يبدأ الـ flusher كـ daemon. يُستدعى مرة في كل عملية عند الإقلاع."""
    t = threading.Thread(target=run_metrics_flusher, name="api-metrics-flusher", daemon=True)
    t.start()
    return t
