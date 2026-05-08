"""
Deal Pulse KSA — Unified Service (Bot + API + Mini App)

خدمة موحّدة واحدة على Railway تجمع:
  1. Telegram Bot Webhook
  2. FastAPI endpoints (/api/v1/coupons, /api/v1/track)
  3. Mini App static serving (/miniapp)

تشغيل محلي:
    uvicorn bot_app:app --host 0.0.0.0 --port 8080

الإنتاج (Railway):
    Custom Start Command: uvicorn bot_app:app --host 0.0.0.0 --port $PORT

متغيرات البيئة المطلوبة:
    BOT_TOKEN | TELEGRAM_BOT_TOKEN  — توكن البوت من BotFather (يقبل أي اسم)
    WEBHOOK_SECRET                  — سلسلة عشوائية ≥ 32 حرف
    WEBHOOK_BASE_URL                — public HTTPS URL (يُضاف https:// تلقائياً لو نُسي)
    DATABASE_URL                    — postgres connection string
    ALLOWED_ORIGINS                 — افتراضي: null (لـ Telegram WebApp)
"""
import os
import pathlib
import threading

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from telebot.types import Update

from deal_pulse_bot import (
    bot,
    idle_watcher,
    clean_legacy_columns,
    ensure_tracking_tables,
    backfill_user_behavior,
    IDLE_TIMEOUT_MINUTES,
)
from api.routers import coupons, track

# ─── التحقق من المتغيرات الحرجة ───────────────────────────────────────────────
TOKEN_ENV = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN_ENV:
    raise RuntimeError("❌ BOT_TOKEN/TELEGRAM_BOT_TOKEN غير موجود في متغيرات البيئة")

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

_raw_base = os.environ["WEBHOOK_BASE_URL"].rstrip("/")
# auto-add https:// if user forgot the protocol on Railway
if not _raw_base.startswith(("http://", "https://")):
    _raw_base = "https://" + _raw_base
WEBHOOK_BASE_URL = _raw_base
WEBHOOK_PATH = f"/telegram/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

# CORS — null هو origin الـ Telegram Mini App
_raw_origins = os.getenv("ALLOWED_ORIGINS", "null")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# ─── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Deal Pulse KSA — Unified Service",
    description="بوت + API + Mini App في خدمة واحدة",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ─── دمج Routers الـ API ──────────────────────────────────────────────────────
app.include_router(coupons.router, prefix="/api/v1")
app.include_router(track.router,   prefix="/api/v1")


# ─── Lifecycle ────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    clean_legacy_columns()
    ensure_tracking_tables()
    backfill_user_behavior()
    threading.Thread(target=idle_watcher, daemon=True).start()
    print(f"✅ idle_watcher started (timeout={IDLE_TIMEOUT_MINUTES}m)")

    bot.remove_webhook()
    bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=["message", "callback_query", "message_reaction"],
        secret_token=WEBHOOK_SECRET,
    )
    print(f"✅ webhook registered at {WEBHOOK_URL}")


@app.on_event("shutdown")
def on_shutdown():
    try:
        bot.remove_webhook()
    except Exception:
        pass


# ─── Telegram Webhook ─────────────────────────────────────────────────────────
@app.post(WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="invalid secret token")

    payload = await request.body()
    update = Update.de_json(payload.decode("utf-8"))
    bot.process_new_updates([update])
    return {"ok": True}


# ─── System endpoints ─────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "deal-pulse-unified"}


@app.get("/miniapp", include_in_schema=False)
def serve_miniapp():
    """يخدم واجهة الـ Telegram Mini App."""
    html_path = pathlib.Path(__file__).parent / "miniapp.html"
    return FileResponse(html_path, media_type="text/html")


@app.get("/", include_in_schema=False)
def root():
    """صفحة جذر بسيطة — تحويل سريع للميني آب."""
    return {
        "service": "deal-pulse-unified",
        "endpoints": {
            "miniapp": "/miniapp",
            "api": "/api/v1/coupons/",
            "docs": "/docs",
            "health": "/health",
        },
    }
