"""
Deal Pulse KSA — Bot Webhook Service

يستقبل تحديثات Telegram عبر webhook بدلاً من polling.
يستورد الـ handlers من deal_pulse_bot.py ويشغّل idle_watcher كـ daemon thread.

تشغيل محلي (للاختبار):
    uvicorn bot_app:app --host 0.0.0.0 --port 8001

الإنتاج (Railway):
    Procfile entry: bot: uvicorn bot_app:app --host 0.0.0.0 --port $PORT

متغيرات البيئة المطلوبة:
    BOT_TOKEN          — توكن البوت من BotFather
    WEBHOOK_SECRET     — سلسلة عشوائية ≥ 32 حرف
    WEBHOOK_BASE_URL   — الـ public HTTPS URL لهذه الخدمة (مثلاً https://bot.your-domain.com)
"""
import os
import threading

from fastapi import FastAPI, Request, HTTPException, Header
from telebot.types import Update

from deal_pulse_bot import (
    bot,
    idle_watcher,
    clean_legacy_columns,
    ensure_tracking_tables,
    backfill_user_behavior,
    IDLE_TIMEOUT_MINUTES,
)

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
WEBHOOK_BASE_URL = os.environ["WEBHOOK_BASE_URL"].rstrip("/")
WEBHOOK_PATH = f"/telegram/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

app = FastAPI(
    title="Deal Pulse KSA — Bot Webhook",
    docs_url=None,
    redoc_url=None,
)


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


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "deal-pulse-bot"}
