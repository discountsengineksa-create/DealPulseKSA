"""
platform_settings — مفتاح/قيمة لإعدادات وقت التشغيل التي يحترمها العمّال
(workers) في كل دورة بدون إعادة نشر. تُدار من صفحة «متابعة المنصة» في الداشبورد.

كل الدوال best-effort: لو الجدول مفقود أو حدث خطأ، نرجع الافتراضي بدل ما
نُسقط العامل. الجدول يُنشأ تلقائياً عند أول استخدام (CREATE TABLE IF NOT EXISTS)
حتى تشتغل الميزة فوراً دون انتظار تشغيل migration_032 يدوياً.
"""
from __future__ import annotations

import logging
from typing import Optional

from api.db import get_db_context

_log = logging.getLogger("dp.settings")

_DDL = """
CREATE TABLE IF NOT EXISTS platform_settings (
    key         VARCHAR(60)  PRIMARY KEY,
    value       TEXT,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by  VARCHAR(80)
)
"""


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """يرجّع قيمة المفتاح (نصاً) أو default لو مفقود/خطأ."""
    try:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
                cur.execute("SELECT value FROM platform_settings WHERE key = %s", (key,))
                row = cur.fetchone()
                if row and row[0] is not None:
                    return row[0]
    except Exception as exc:
        _log.warning("get_setting(%s) failed: %s", key, exc)
    return default


def set_setting(key: str, value: str, *, updated_by: str = "dashboard") -> None:
    """upsert لمفتاح/قيمة. يرمي عند الفشل (المُستدعي يعرض الخطأ)."""
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(_DDL)
            cur.execute(
                """
                INSERT INTO platform_settings (key, value, updated_at, updated_by)
                VALUES (%s, %s, NOW(), %s)
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    updated_at = NOW(),
                    updated_by = EXCLUDED.updated_by
                """,
                (key, value, updated_by),
            )


def all_settings() -> dict[str, str]:
    """يرجّع كل الإعدادات كـ dict. {} عند الخطأ."""
    out: dict[str, str] = {}
    try:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
                cur.execute("SELECT key, value FROM platform_settings")
                for k, v in cur.fetchall():
                    out[k] = v
    except Exception as exc:
        _log.warning("all_settings failed: %s", exc)
    return out
