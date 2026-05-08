"""
Deal Pulse KSA — FastAPI Backend
تشغيل محلي:  uvicorn api.main:app --reload --port 8000
توثيق تلقائي: http://localhost:8000/docs
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import coupons, track

# ─── النطاقات المسموح لها بالاتصال بالـ API ────────────────────────────────
# في .env: ALLOWED_ORIGINS=https://yoursite.com,https://app.yoursite.com
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:8000,null"
)
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app = FastAPI(
    title="Deal Pulse KSA API",
    description="محرك كوبونات نبض الصفقات — واجهة برمجية للويب والجوال",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],   # نحصر على ما نحتاجه فعلاً
    allow_headers=["Content-Type", "Authorization"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(coupons.router, prefix="/api/v1")
app.include_router(track.router,   prefix="/api/v1")


@app.get("/health", tags=["system"])
def health_check():
    """نقطة مراقبة للـ uptime checkers والـ load balancers."""
    return {"status": "ok", "service": "deal-pulse-api"}
