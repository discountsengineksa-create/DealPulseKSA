"""
Deal Pulse KSA — FastAPI Backend (API-only entrypoint)

ملاحظة مهمة:
    الإنتاج الفعلي على Railway يُشغّل bot_app.py الذي يجمع البوت + API + Mini App
    في خدمة واحدة. هذا الملف موجود فقط للتطوير المحلي لمن يريد تشغيل الـ API
    بمعزل عن البوت (مثلاً اختبارات تكامل أو واجهة فرونت-إند محلية).

تشغيل محلي:  uvicorn api.main:app --reload --port 8000
توثيق تلقائي: http://localhost:8000/docs
"""
import os
import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.routers import admin, auth, coupons, go, seo, social, track, users
from api.utils.rate_limit import limiter

# ─── النطاقات المسموح لها بالاتصال بالـ API ────────────────────────────────
# في .env: ALLOWED_ORIGINS=https://dealpulseksa.com,https://app.dealpulseksa.com
# افتراضياً للتطوير المحلي فقط — في الإنتاج يجب تحديد domains صريحة.
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:8000"
)
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app = FastAPI(
    title="Deal Pulse KSA API",
    description="محرك كوبونات نبض الصفقات — واجهة برمجية للويب والجوال (API-only entrypoint)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Rate limiting (slowapi + Redis) ─────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS ────────────────────────────────────────────────────────────────────
# X-Admin-Secret لا يُمرَّر cross-origin (الداشبورد محلي/مباشر، ليس متصفّح ويب).
if "*" in ALLOWED_ORIGINS:
    raise RuntimeError("ALLOWED_ORIGINS=* غير مسموح مع allow_credentials=True")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ─── Routers (مطابق تماماً لـ bot_app.py) ────────────────────────────────────
app.include_router(auth.router,    prefix="/api/v1")
app.include_router(coupons.router, prefix="/api/v1")
app.include_router(track.router,   prefix="/api/v1")
app.include_router(users.router,   prefix="/api/v1")
app.include_router(admin.router,   prefix="/api/v1")
app.include_router(seo.router,     prefix="/api/v1")
app.include_router(social.router,  prefix="/api/v1")
# /go/{slug} رابط عام قصير بدون /api/v1 prefix
app.include_router(go.router)


@app.get("/health", tags=["system"])
def health_check():
    """نقطة مراقبة للـ uptime checkers والـ load balancers."""
    return {"status": "ok", "service": "deal-pulse-api"}


@app.get("/miniapp", include_in_schema=False)
def serve_miniapp():
    """يخدم واجهة الـ Telegram Mini App."""
    html_path = pathlib.Path(__file__).parent.parent / "miniapp.html"
    return FileResponse(html_path, media_type="text/html")


from fastapi.responses import PlainTextResponse

@app.get("/google2ed86c67fa2838f0.html", response_class=PlainTextResponse)
async def google_verification():
    return "google-site-verification: google2ed86c67fa2838f0.html"