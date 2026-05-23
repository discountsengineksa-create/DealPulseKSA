"""
Affiliate cloaking helpers (Week 4).

- generate_slug(): slug عشوائي قصير وآمن للمشاركة لعمود master.cloaked_slug.
- منطق التحويل نفسه في api/routers/go.py.

نستخدم أبجدية بدون أحرف ملتبسة (0/O/1/l/I) لتقليل أخطاء النسخ اليدوي،
وطول 10 خانات يعطي 54^10 ≈ 4.6e17 احتمالاً — تصادم نادر جداً مع الفهرس الفريد.
"""
from __future__ import annotations

import secrets

_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_slug(length: int = 10) -> str:
    """slug عشوائي url-safe بطول ثابت."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
