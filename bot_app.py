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
# ── Logging → stdout ──────────────────────────────────────────────────────
# Railway يصنّف كل ما يُكتب على stderr كـ "error" (أحمر). تسجيل بايثون الافتراضي
# يكتب لـ stderr، فتظهر تحذيراتنا (مثل فشل pytrends المتوقّع) حمراء. نوجّهها لـ
# stdout ونُسكت FutureWarning من pytrends حتى تبقى السجلّات نظيفة.
import sys as _sys
import logging as _logging
import warnings as _warnings
_warnings.filterwarnings("ignore", category=FutureWarning)
_logging.basicConfig(
    level=_logging.INFO,
    stream=_sys.stdout,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

import asyncio
import os
import pathlib
import queue
import threading

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from telebot.types import Update

from deal_pulse_bot import (
    bot,
    idle_watcher,
    clean_legacy_columns,
    ensure_tracking_tables,
    backfill_user_behavior,
    IDLE_KICK_MINUTES,
)
from telebot import ExceptionHandler

from api.routers import admin, auth, coupons, go, seo, social, track, users
from api.utils.rate_limit import limiter
from api.workers.scheduler import start_workers

# ─── Webhook mode: synchronous + crash-resilient update processing ──────────
# سبب جذري (شُخّص 2026-06-02): telebot الافتراضي threaded=True يستخدم بركة خيوط،
# وفي util.WorkerThread.run عند رمي أي معالج لاستثناء يتجمّد الخيط على
# continue_event.wait() للأبد. في polling يحرّره bot.polling()؛ لكن في WEBHOOK
# لا شيء يحرّره → بعد استثناءين (عامِلان فقط) يتجمّد كل العمّال → كل الأزرار
# تتوقّف عن الاستجابة (الخدمة ترد 200 لكن لا معالج يشتغل).
# الإصلاح: معالجة متزامنة (threaded=False) — لا بركة خيوط تتجمّد — + معالِج
# استثناءات يسجّل ويعتبره مُعالَجاً حتى لا يُسقط معالجٌ واحد الـ webhook بـ 500
# (فيدخل تيليجرام في حلقة إعادة إرسال).
class _WebhookExceptionHandler(ExceptionHandler):
    def handle(self, exception):  # noqa: D401
        _logging.getLogger("dp.bot").error(
            "bot handler exception: %s", exception, exc_info=exception
        )
        return True  # handled → لا إعادة رفع → webhook يرجّع 200

bot.threaded = False
bot.exception_handler = _WebhookExceptionHandler()

# ─── Background update workers (بركة دائمة بدل asyncio.to_thread) ────────────
# لماذا: telebot يحفظ requests.Session في thread-local. مع asyncio.to_thread
# تتبدّل الخيوط فتُنشأ جلسة جديدة كل مرة (اتصال TLS بارد لتيليجرام) → بطء، وأي
# تعلّق يصطدم بـ apihelper.READ_TIMEOUT=30s فيعلّق الـ webhook 30 ثانية كاملة
# (هذا سبب «بطء ٣٠ث»). الحل: خيوط عاملة **دائمة** (جلسة مستقرّة + إعادة استخدام
# اتصال) تستهلك من طابور؛ والـ webhook يضع التحديث ويرجّع 200 فوراً (لا انتظار،
# لا إعادة إرسال من تيليجرام، ولا تجمّد — لكل عامل حلقة تلتقط الاستثناءات).
_BOT_UPDATE_QUEUE: "queue.Queue" = queue.Queue(maxsize=2000)
_NUM_BOT_WORKERS = 4
_bot_log = _logging.getLogger("dp.bot")


def _bot_update_worker():
    while True:
        update = _BOT_UPDATE_QUEUE.get()
        try:
            bot.process_new_updates([update])
        except Exception as exc:  # حلقة العامل لا تموت أبداً
            _bot_log.error("update worker error: %s", exc, exc_info=exc)
        finally:
            _BOT_UPDATE_QUEUE.task_done()


for _wi in range(_NUM_BOT_WORKERS):
    threading.Thread(
        target=_bot_update_worker, name=f"dp-bot-worker-{_wi}", daemon=True
    ).start()

# ─── التحقق من المتغيرات الحرجة ───────────────────────────────────────────────
TOKEN_ENV = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN_ENV:
    raise RuntimeError("❌ BOT_TOKEN/TELEGRAM_BOT_TOKEN غير موجود في متغيرات البيئة")

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
# Telegram يُلزِم 1..256 حرف، لكن الأمان يستوجب ≥32 حرف عشوائي حقيقي.
# قيمة قصيرة تسمح بـ brute-force تجريبي على الـ webhook endpoint.
# نُحذّر بدلاً من فشل الإقلاع — حتى لا نُسقط الإنتاج لو الـ secret الحالي قصير.
if len(WEBHOOK_SECRET) < 32:
    print(
        f"⚠️  WARNING: WEBHOOK_SECRET قصير (الطول={len(WEBHOOK_SECRET)}). "
        "يُوصى بقيمة ≥32 حرف. ولّد قيمة آمنة عبر: openssl rand -base64 48"
    )

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

# ─── Rate limiting (slowapi + Redis) ─────────────────────────────────────────
# الـ limiter يُسجَّل على الـ app + handler للـ 429 responses.
# الحدود الفعلية تُطبَّق بـ @limiter.limit("...") في كل router.
app.state.limiter = limiter


def _rate_limit_with_cors_handler(request: Request, exc: RateLimitExceeded):
    """Handler مخصّص لـ 429 يضمن وجود CORS headers.

    لماذا: handler الافتراضي من slowapi يُرجع JSONResponse مباشرة قبل أن
    يصل الطلب لـ CORSMiddleware في chain الـ Starlette → المتصفح يرى رد
    بدون 'Access-Control-Allow-Origin' فيحجب الرد ويظهر للمستخدم كخطأ
    شبكة بدل رسالة "حاولت كثيراً". هذا الـ handler يضيف الـ headers يدوياً.
    """
    response = JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )
    origin = request.headers.get("origin", "")
    if origin and (origin in ALLOWED_ORIGINS or origin == "null"):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


app.add_exception_handler(RateLimitExceeded, _rate_limit_with_cors_handler)

# CORS hardening:
#   - X-Admin-Secret أُزيل من allow_headers — لا يُستخدم cross-origin أبداً
#     (الداشبورد محلي والـ workers تكلّم Railway مباشرةً، بدون متصفّح).
#   - "null" origin مسموح فقط لـ Telegram Mini App (Telegram WebApp يستخدم null).
#   - لو "*" موجود في ALLOWED_ORIGINS مع allow_credentials=True، FastAPI/CORS
#     ترفض الـ preflight تلقائياً، لكن نتأكّد صراحةً.
if "*" in ALLOWED_ORIGINS:
    raise RuntimeError("ALLOWED_ORIGINS=* غير مسموح مع allow_credentials=True")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ─── دمج Routers الـ API ──────────────────────────────────────────────────────
app.include_router(coupons.router, prefix="/api/v1")
app.include_router(track.router,   prefix="/api/v1")
app.include_router(users.router,   prefix="/api/v1")
app.include_router(auth.router,    prefix="/api/v1")
app.include_router(admin.router,   prefix="/api/v1")
app.include_router(seo.router,     prefix="/api/v1")   # Week 5-6 — SEO landing pages (read)
app.include_router(social.router,  prefix="/api/v1")   # Week 7-8 — social listener ingest
# Week 4 — Affiliate cloaking: /go/{slug} (بدون /api/v1 — رابط عام قصير)
app.include_router(go.router)


# ─── Lifecycle ────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    """
    تشغيل آمن مع multi-worker:
    - تهيئة DB تتم في كل worker (idempotent — CREATE IF NOT EXISTS)
    - idle_watcher يشتغل في كل worker (كل واحد يفحص حصته)
    - webhook registration: نتحقق أولاً، ولا نمسحه/نُسجّله إلا إذا اختلف
      (يمنع race condition بين الـ workers)
    """
    clean_legacy_columns()
    ensure_tracking_tables()
    backfill_user_behavior()
    threading.Thread(target=idle_watcher, daemon=True).start()
    print(f"✅ idle_watcher started (timeout={IDLE_KICK_MINUTES}m)")

    # Week 2 — velocity aggregator + spike detector + email dispatcher
    # (idempotent: only the first worker process boots the scheduler)
    try:
        start_workers()
    except Exception as e:
        print(f"⚠️ start_workers warning: {e}")

    # webhook: idempotent — يُسجَّل فقط إذا كان غير صحيح
    try:
        current = bot.get_webhook_info()
        if current.url == WEBHOOK_URL:
            print(f"✅ webhook already set correctly — skip")
        else:
            bot.set_webhook(
                url=WEBHOOK_URL,
                allowed_updates=["message", "callback_query", "message_reaction"],
                secret_token=WEBHOOK_SECRET,
            )
            print(f"✅ webhook registered at {WEBHOOK_URL}")
    except Exception as e:
        print(f"⚠️ webhook registration warning: {e}")


@app.on_event("shutdown")
def on_shutdown():
    # لا نمسح الـ webhook عند إيقاف worker واحد لأنه قد يكون
    # مجرد إعادة تشغيل أو تحديث — workers أخرى ما زالت تعمل.
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
    # نضع التحديث في طابور العمّال الدائمين ونرجّع 200 فوراً — لا ننتظر اكتمال
    # المعالجة (التي قد تستغرق ثوانٍ لنداءات تيليجرام). هذا يمنع تعليق الـ webhook
    # وإعادة إرسال تيليجرام، ويحافظ على جلسات اتصال مستقرّة في خيوط العمّال.
    if update is not None:
        try:
            _BOT_UPDATE_QUEUE.put_nowait(update)
        except queue.Full:
            _bot_log.warning("update queue full — dropping update %s", update.update_id)
    return {"ok": True}


# ─── System endpoints ─────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "deal-pulse-unified"}


@app.get("/health/workers", tags=["system"])
def health_workers():
    """تشخيص حالة الـ workers (Week 2)."""
    import os as _os
    from api.utils.redis_client import get_redis
    out = {
        "redis_url_set": bool(_os.getenv("REDIS_URL")),
        "disable_workers": _os.getenv("DISABLE_WORKERS"),
    }
    try:
        r = get_redis()
        out["redis_ping"] = r.ping()
        out["redis_class"] = type(r).__name__
        # حجم events:raw stream
        try:
            out["events_raw_len"] = r.xlen("events:raw")
        except Exception as exc:
            out["events_raw_len_error"] = str(exc)[:200]
        # حالة consumer group
        try:
            groups = r.xinfo_groups("events:raw")
            out["consumer_groups"] = [
                {
                    "name": g.get("name") or g.get(b"name", b"").decode("utf-8", "ignore"),
                    "consumers": g.get("consumers") or g.get(b"consumers"),
                    "pending": g.get("pending") or g.get(b"pending"),
                    "last_delivered_id": g.get("last-delivered-id") or g.get(b"last-delivered-id"),
                }
                for g in groups
            ]
        except Exception as exc:
            out["consumer_groups_error"] = str(exc)[:200]
    except Exception as exc:
        out["redis_error"] = str(exc)[:200]
    # scheduler state
    try:
        from api.workers.scheduler import _started, _scheduler, _consumer_thread
        out["scheduler_started"] = _started
        out["scheduler_jobs"] = (
            [j.id for j in _scheduler.get_jobs()] if _scheduler else []
        )
        out["consumer_thread_alive"] = (
            _consumer_thread.is_alive() if _consumer_thread else False
        )
    except Exception as exc:
        out["scheduler_error"] = str(exc)[:200]
    return out


_BASE_DIR = pathlib.Path(__file__).parent
_LOGO_CACHE = {"max-age": "86400"}  # cache 24h


@app.get("/miniapp", include_in_schema=False)
def serve_miniapp():
    """يخدم واجهة الـ Telegram Mini App."""
    return FileResponse(_BASE_DIR / "miniapp.html", media_type="text/html")


# ─── Static assets (logos, fonts) — صراحة بدون mount لتجنب فتح الجذر ────────
_STATIC_FILES = {
    "logo.png":  "image/png",
    "logo1.jpeg": "image/jpeg",
    "logo2.jpeg": "image/jpeg",
    "logo3.jpeg": "image/jpeg",
    "logo4.jpeg": "image/jpeg",
    "Cairo-Bold.ttf": "font/ttf",
}


@app.get("/{filename}", include_in_schema=False)
def serve_static(filename: str):
    """يخدم ملفات ثابتة محددة فقط (logos, fonts) مع cache طويل."""
    if filename not in _STATIC_FILES:
        raise HTTPException(status_code=404)
    file_path = _BASE_DIR / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(
        file_path,
        media_type=_STATIC_FILES[filename],
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )


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
