"""
Parse the `x-dp-*` headers attached by the Cloudflare Worker into a typed
GeoContext. When the Worker is absent (local dev, or DNS hasn't propagated),
fields fall back to None — the origin handles missing values gracefully.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Request

# ملح تجزئة الـIP — يمنع استرجاع الـIP الخام من الهاش. اضبطه عبر IP_HASH_SALT.
_IP_HASH_SALT = os.getenv("IP_HASH_SALT", "dpk-geo-fallback")


def _fallback_ip_hash(req: Request) -> Optional[str]:
    """بصمة IP احتياطية حين يغيب Cloudflare Worker (x-dp-ip-hash فارغ).

    نقرأ IP العميل من ترويسات البروكسي القياسية (Cloudflare/Railway) ونُجزّئه
    sha256(salt+ip) → hex، فتبقى بصمة الزائر ثابتة عبر النقر/النسخ حتى بلا الـ
    Worker. لا تعطي مدينة (تحتاج GeoIP) لكنها تعطي هوية مميِّزة للزائر."""
    h = req.headers
    raw_ip = (
        (h.get("cf-connecting-ip") or "").strip()
        or (h.get("x-forwarded-for") or "").split(",")[0].strip()
        or (h.get("x-real-ip") or "").strip()
        or (req.client.host if req.client else "")
    )
    if not raw_ip:
        return None
    return hashlib.sha256(f"{_IP_HASH_SALT}:{raw_ip}".encode()).hexdigest()


@dataclass
class GeoContext:
    event_id: str
    ip_hash: Optional[str]
    ua_hash: Optional[str]
    country_code: Optional[str]
    region_code: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    asn: Optional[int]
    isp: Optional[str]
    device_class: Optional[str]
    cf_bot_score: Optional[int]
    verified_bot: bool


def _safe_int(s: Optional[str]) -> Optional[int]:
    try:
        return int(s) if s else None
    except (TypeError, ValueError):
        return None


def _safe_float(s: Optional[str]) -> Optional[float]:
    try:
        return float(s) if s else None
    except (TypeError, ValueError):
        return None


def extract(req: Request) -> GeoContext:
    """Build a GeoContext from the FastAPI request headers."""
    h = req.headers
    # نُفضّل بصمة الـWorker (مُملّحة عنده)؛ وإلا نشتقّ بصمة IP احتياطية من
    # ترويسات البروكسي حتى لا يبقى الزائر بلا بصمة حين يغيب الـWorker.
    ip_hash = h.get("x-dp-ip-hash") or _fallback_ip_hash(req)
    return GeoContext(
        event_id=h.get("x-dp-event-id") or str(uuid.uuid4()),
        ip_hash=ip_hash,
        ua_hash=h.get("x-dp-ua-hash") or None,
        country_code=(h.get("x-dp-country") or "").upper()[:2] or None,
        region_code=(h.get("x-dp-region") or "")[:8] or None,
        city=(h.get("x-dp-city") or "")[:80] or None,
        postal_code=(h.get("x-dp-postal") or "")[:16] or None,
        lat=_safe_float(h.get("x-dp-lat")),
        lng=_safe_float(h.get("x-dp-lng")),
        asn=_safe_int(h.get("x-dp-asn")),
        isp=(h.get("x-dp-isp") or "")[:120] or None,
        device_class=h.get("x-dp-device") or None,
        cf_bot_score=_safe_int(h.get("x-dp-bot-score")),
        verified_bot=h.get("x-dp-verified-bot") == "1",
    )
