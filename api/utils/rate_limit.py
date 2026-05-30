"""
Rate limiting موحّد لجميع endpoints الـ FastAPI.

البنية:
    - يستخدم slowapi + Redis (موزَّع على كل replicas).
    - لو REDIS_URL غير معرّف → fallback to in-memory (يعمل لـ single replica فقط).
    - مفتاح التحديد: Cloudflare's CF-Connecting-IP لو وُجد، وإلا client.host.

الحدود (موصى بها):
    /auth/login            10/minute
    /auth/register          5/hour
    /auth/forgot-password   3/15minutes
    /auth/reset-password    5/15minutes
    /track                120/minute   (حجم مشروع عالٍ)
    /go/{slug}             60/minute
    /social/ingest         30/minute
    /admin/*               30/minute

الاستخدام في endpoint:
    from api.utils.rate_limit import limiter
    @router.post("/login")
    @limiter.limit("10/minute")
    def login(request: Request, ...):     # Request param إلزامي لـ slowapi
        ...
"""
from __future__ import annotations

import logging
import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

_log = logging.getLogger("dp.rate_limit")


def _client_ip(request: Request) -> str:
    """
    يُعطي مفتاح التحديد لكل عميل.
    أولوية:
      1) CF-Connecting-IP من Cloudflare (الأكثر دقة، صعب التزوير من خارج CF).
      2) X-Forwarded-For (Railway proxy) — أول IP في القائمة.
      3) request.client.host (fallback مباشر).
    """
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # XFF قد يكون قائمة "ip1, ip2, ip3" — العميل الأصلي هو الأول
        return xff.split(",")[0].strip()
    return get_remote_address(request)


def _build_limiter() -> Limiter:
    """
    يبني الـ limiter — Redis في الإنتاج، in-memory محلياً.

    slowapi يستخدم مكتبة `limits` التي تقبل URI مباشرة:
      - "redis://host:port/0"      → موزَّع
      - "memory://"                → in-memory (process-local)
    """
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        # نمرّر الـ URL كما هو لمكتبة limits — تتولى الاتصال بنفسها
        _log.info("rate-limit storage: Redis")
        return Limiter(
            key_func=_client_ip,
            storage_uri=redis_url,
            strategy="fixed-window",  # أرخص حسابياً من sliding-window، يكفي لحالتنا
        )

    _log.warning("REDIS_URL unset — rate-limit using in-memory (single-replica only)")
    return Limiter(
        key_func=_client_ip,
        storage_uri="memory://",
        strategy="fixed-window",
    )


# Singleton يُستورَد من كل endpoint
limiter: Limiter = _build_limiter()


# ─── ثوابت الحدود ─────────────────────────────────────────────────────────────
# تُجمع هنا للتعديل المركزي بدلاً من تكرار السلاسل في كل router.
LIMIT_LOGIN            = "10/minute"
LIMIT_REGISTER         = "5/hour"
LIMIT_FORGOT_PASSWORD  = "3/15 minutes"
LIMIT_RESET_PASSWORD   = "5/15 minutes"
LIMIT_TRACK            = "120/minute"
LIMIT_GO_REDIRECT      = "60/minute"
LIMIT_SOCIAL_INGEST    = "30/minute"
LIMIT_ADMIN            = "30/minute"
LIMIT_TG_PROFILE_READ  = "60/minute"   # status check (idempotent)
LIMIT_TG_PROFILE_SAVE  = "10/hour"     # write — أبطأ لتفادي الإغراق
