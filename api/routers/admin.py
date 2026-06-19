"""
Admin endpoints — يستدعيها الـ dashboard فقط.

POST /api/v1/admin/broadcast/{master_id}
    يطلق نشر العرض على كل منصات السوشيال في خيط خلفي (daemon thread).
    الـ Header `X-Admin-Secret` لازم يطابق ADMIN_SHARED_SECRET.

POST /api/v1/admin/trigger-directive
    يولّد توجيه AI فوراً (يدوي — عادة الـ scheduler يشغله كل 3 ساعات).
"""
from __future__ import annotations

import os
import secrets as _secrets
import threading

from pydantic import BaseModel

from fastapi import APIRouter, Header, HTTPException, Query, Request

from api.social.dispatcher import broadcast_to_all_platforms
from api.utils.rate_limit import LIMIT_ADMIN, limiter

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_admin(x_admin_secret: str) -> None:
    expected = os.getenv("ADMIN_SHARED_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_SHARED_SECRET not configured")
    # compare_digest يحمي من timing attacks (المقارنة بـ == تكشف طول السر تدريجياً)
    if not _secrets.compare_digest(x_admin_secret or "", expected):
        raise HTTPException(status_code=403, detail="forbidden")


# ─── Email Diagnostics ────────────────────────────────────────────────────
# يكشف لماذا "نسيت كلمة المرور" لا يصل: غالباً RESEND_API_KEY مفقود في Railway،
# أو الدومين غير موثّق على Resend. كلا المسارين الفرعيين يطبع رسائل واضحة.
@router.get("/email-status")
def email_status(x_admin_secret: str = Header(..., alias="X-Admin-Secret")):
    """يرجع حالة إعدادات الإيميل — يساعد في تشخيص عدم وصول الرسائل."""
    _verify_admin(x_admin_secret)
    resend_key = os.getenv("RESEND_API_KEY")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "onboarding@resend.dev")

    if resend_key:
        transport = "resend"
        configured = True
        hint = "Resend مفعّل. تأكد من توثيق الدومين (DNS records في Cloudflare) "\
               "وأن SMTP_FROM يستخدم الدومين الموثّق."
    elif smtp_user and smtp_pass:
        transport = "smtp"
        configured = True
        hint = "SMTP مفعّل. ملاحظة: Railway يحجب outbound SMTP عادةً — "\
               "الأفضل التحويل إلى Resend."
    else:
        transport = "dev_mode"
        configured = False
        hint = "⚠️ لا RESEND_API_KEY ولا SMTP creds — الكود يطبع للوغ فقط. "\
               "اضبط RESEND_API_KEY في Railway → Variables، ثم أعد التشغيل."

    return {
        "transport": transport,
        "configured": configured,
        "resend_key_set": bool(resend_key),
        "smtp_user_set": bool(smtp_user),
        "smtp_pass_set": bool(smtp_pass),
        "from_address": smtp_from,
        "hint": hint,
    }


class EmailTestRequest(BaseModel):
    to: str
    # اختياري — اختبر بعنوان From مختلف (مثلاً onboarding@resend.dev للسندبوكس)
    from_override: str | None = None


@router.post("/email-test")
def email_test(
    payload: EmailTestRequest,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يرسل اختبار إيميل + يرجع رد Resend الكامل (status + id + error).

    sent:true لا يعني وصول الإيميل — يعني Resend قَبِل الطلب فقط. للتحقق
    من التوصيل الفعلي افحص لوحة Resend (resend.com/emails) أو استدعِ
    GET /admin/email-trace/{id} بالـ id المرجع.
    """
    _verify_admin(x_admin_secret)
    import requests as _rq
    resend_key = os.getenv("RESEND_API_KEY")
    smtp_from = payload.from_override or os.getenv("SMTP_FROM") or "onboarding@resend.dev"
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "نبض الصفقات")

    if not resend_key:
        return {
            "sent": False,
            "transport": "none",
            "error": "RESEND_API_KEY غير معرّف على Railway",
        }

    try:
        resp = _rq.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}",
                     "Content-Type": "application/json"},
            json={
                "from": f"{smtp_from_name} <{smtp_from}>",
                "to": [payload.to],
                "subject": "✅ اختبار إرسال — نبض الصفقات",
                "html": "<p>هذه رسالة اختبار. لو وصلتك → الإعدادات تعمل.</p>"
                        "<p>If you received this, your config works.</p>",
            },
            timeout=15,
        )
        body = {}
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {"raw": resp.text[:500]}
        return {
            "sent": resp.status_code in (200, 201, 202),
            "status_code": resp.status_code,
            "from_used": f"{smtp_from_name} <{smtp_from}>",
            "to": payload.to,
            "resend_id": body.get("id"),
            "resend_response": body,
            "hint": (
                "لو status_code=403 → الدومين غير موثّق على Resend. "
                "جرّب from_override='onboarding@resend.dev' (سندبوكس Resend)."
                if resp.status_code == 403
                else "افحص resend.com/emails لرؤية delivery status (delivered/bounced/spam)."
            ),
        }
    except Exception as e:
        return {"sent": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


class UserLookupRequest(BaseModel):
    username: str  # جوال أو إيميل


@router.post("/user-lookup")
def user_lookup(
    payload: UserLookupRequest,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يفحص هل الـ username (جوال أو إيميل) مسجّل في web_users.

    forgot-password يُرجع نفس الرد العام حتى لو الحساب غير موجود (حماية ضد
    user enumeration). هذا endpoint للأدمن فقط — يكشف إن كان الحساب موجوداً
    + يعرض آخر طلبات استعادة كلمة المرور لهذا المستخدم.
    """
    _verify_admin(x_admin_secret)
    import psycopg2
    from psycopg2.extras import RealDictCursor
    db_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")
    if not db_url:
        return {"error": "DATABASE_URL not set"}

    username = payload.username.strip()
    phone = username
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if phone.startswith("0"):
        phone = "+966" + phone[1:]
    if phone.startswith("5") and len(phone) == 9:
        phone = "+966" + phone

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, email, phone_number, display_name, created_at,
                       email_verified_at, status
                FROM web_users
                WHERE phone_number = %s OR email = %s OR phone_number = %s
                LIMIT 1
                """,
                (username, username.lower(), phone),
            )
            user = cur.fetchone()
            if not user:
                return {
                    "found": False,
                    "hint": f"لا حساب في web_users يطابق '{username}'. "
                            "forgot-password يُرجع 200 generic ولا يرسل إيميل.",
                }
            cur.execute(
                """
                SELECT created_at, expires_at, used, request_ip
                FROM password_reset_tokens
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (user["id"],),
            )
            recent_tokens = cur.fetchall()
        return {
            "found": True,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "phone_number": user["phone_number"],
                "display_name": user["display_name"],
                "created_at": str(user["created_at"]),
                "email_verified_at": str(user["email_verified_at"]) if user["email_verified_at"] else None,
                "status": user["status"],
            },
            "recent_reset_requests": [
                {
                    "created_at": str(t["created_at"]),
                    "expires_at": str(t["expires_at"]),
                    "used": t["used"],
                    "ip": str(t["request_ip"]) if t["request_ip"] else None,
                }
                for t in recent_tokens
            ],
        }
    finally:
        conn.close()


@router.get("/email-trace/{email_id}")
def email_trace(
    email_id: str,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يفحص حالة إيميل من Resend عبر الـ id (delivered/bounced/complained).

    يستدعى بعد /admin/email-test بـ resend_id المُرجَع.
    """
    _verify_admin(x_admin_secret)
    import requests as _rq
    resend_key = os.getenv("RESEND_API_KEY")
    if not resend_key:
        return {"error": "RESEND_API_KEY غير معرّف"}
    try:
        resp = _rq.get(
            f"https://api.resend.com/emails/{email_id}",
            headers={"Authorization": f"Bearer {resend_key}"},
            timeout=10,
        )
        return {
            "status_code": resp.status_code,
            "data": resp.json() if resp.content else {},
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:300]}"}


@router.post("/broadcast/{master_id}")
@limiter.limit(LIMIT_ADMIN)
def broadcast(
    master_id: int,
    request: Request,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    _verify_admin(x_admin_secret)
    # خيط خلفي بدل FastAPI BackgroundTasks: حقن BackgroundTasks يتعارض مع decorator
    # الـ rate-limit (slowapi) فيرجع 422. الـ dispatcher يفتح اتصاله الخاص فهو آمن للخيط.
    threading.Thread(
        target=broadcast_to_all_platforms,
        args=(master_id,),
        daemon=True,
    ).start()
    from api.utils.ops import audit_log
    audit_log(action="broadcast", target=str(master_id))
    return {"status": "queued", "master_id": master_id}


@router.post("/social/run-reel-batch")
@limiter.limit(LIMIT_ADMIN)
def run_reel_batch(
    request: Request,
    force_reset: int = Query(
        default=0, ge=0, le=6,
        description="عدد المتاجر التي تُصفَّر last_reeled_at قبل التشغيل "
                    "(أحدث n متاجر). 0 = استخدم المنتظرين الفعليين فقط."
    ),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يطلق Reel جماعي فوراً.

    لو الـpool الفعلي (last_reeled_at IS NULL) أقل من 6 → استخدم
    `?force_reset=6` ليُصفَّر آخر 6 متاجر (بحسب أحدث تحديث) ثم يدخلون
    في batch جديد. مفيد عندما تكون كل المتاجر سبق ودخلوا ريل سابقاً
    لكن كوبوناتهم تجدّدت.
    """
    _verify_admin(x_admin_secret)
    from api.db import get_db_context
    from api.social.reels_batch import run_pending_batches

    reset_count = 0
    if force_reset > 0:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH recent AS (
                        SELECT id FROM master
                        WHERE (publish_channels IS NULL
                               OR 'instagram' = ANY(
                                   string_to_array(COALESCE(publish_channels,''), ',')
                               ))
                        ORDER BY COALESCE(last_modified, NOW()) DESC, id DESC
                        LIMIT %s
                    )
                    UPDATE master SET last_reeled_at = NULL
                    WHERE id IN (SELECT id FROM recent)
                    RETURNING id
                    """,
                    (force_reset,),
                )
                reset_count = len(cur.fetchall())
            conn.commit()

    # شغّل البث في خيط خلفي — إنشاء MP4 + رفع Cloudinary + Graph API قد
    # يستغرق 30-60 ثانية. لا نريد timeout على HTTP.
    def _bg():
        from api.db import get_db_context as gdb
        try:
            with gdb() as c:
                count = run_pending_batches(c)
                print(f"[admin] manual reel_batch produced {count} reel(s)")
        except Exception as e:
            print(f"[admin] manual reel_batch crashed: {type(e).__name__}: {e}")

    threading.Thread(target=_bg, daemon=True).start()
    from api.utils.ops import audit_log
    audit_log(action="run_reel_batch", target=f"force_reset={force_reset}")
    return {
        "status": "queued",
        "force_reset_applied": reset_count,
        "hint": "تابع social_posts_log بعد ~60 ثانية — صف جديد بـplatform='instagram_reel_batch'.",
    }


@router.post("/trigger-directive")
@limiter.limit(LIMIT_ADMIN)
def trigger_directive(
    request: Request,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    Manual trigger للـ LLM directive generator. يُستخدم للاختبار وللحالات
    الطارئة بدون انتظار الـ scheduler. النتيجة تعود مباشرة في الـ response
    (مش background) عشان نقدر نشوف cache_hit + cost + summary.
    """
    _verify_admin(x_admin_secret)
    # Lazy import — avoid loading the LLM SDK on every admin request
    from api.utils.llm_service import generate_directive
    result = generate_directive()
    return {
        "directive_id":         result.get("directive_id"),
        "cache_hit":            result.get("cache_hit"),
        "is_mock":              result.get("is_mock", False),
        "summary":              result.get("summary"),
        "directives_count":     len(result.get("directives") or []),
        "directives":           result.get("directives", []),
        "model":                result.get("model"),
        "provider":             result.get("provider"),
        "fallback_used":        result.get("fallback_used"),
        "cost_usd":             result.get("cost_usd"),
        "tokens_input":         result.get("tokens_input"),
        "tokens_output":        result.get("tokens_output"),
        "refused_by_guardian":  result.get("refused_by_guardian"),
        "refused_reason":       result.get("refused_reason"),
    }


# ─── Week 5-6: SEO generator triggers ──────────────────────────────────────
@router.post("/seo-run")
def seo_run(
    batch: int = Query(default=3, ge=0, le=20),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    تشغيل يدوي لخط أنابيب الـ SEO:
      1. تجميع الترند الداخلي (مجاني)
      2. مطابقة الكلمات بالمتاجر وإنشاء وظائف (مجاني)
      3. توليد batch صفحات عبر الـ LLM (يستهلك الميزانية — batch=0 يتخطّاه)
    """
    _verify_admin(x_admin_secret)
    from api.seo.trends import aggregate_internal_search
    from api.seo.matcher import match_and_enqueue
    from api.seo.generator import process_pending_jobs

    trends = aggregate_internal_search()
    enqueued = match_and_enqueue()
    gen = process_pending_jobs(batch=batch) if batch else {"processed": 0, "generated": 0, "failed": 0}
    return {"trends_upserted": trends, "jobs_enqueued": enqueued, "generation": gen}


@router.post("/seo-snapshot")
def seo_snapshot(x_admin_secret: str = Header(..., alias="X-Admin-Secret")):
    """يلتقط لقطة أداء SEO الآن (PageSpeed + GSC) ويخزّنها — يدوي أو من الكرون."""
    _verify_admin(x_admin_secret)
    from api.seo.perf_snapshot import capture_snapshot
    return capture_snapshot()


@router.post("/seo-auto-run")
def seo_auto_run(x_admin_secret: str = Header(..., alias="X-Admin-Secret")):
    """تشغيل يدوي لدورة محرّك SEO الأوتوماتيكية الكاملة (نفس دورة 3 صباحاً):
    أكثر المتاجر طلباً → ربط مناسبة → توليد → نشر مُبوّب. force=True يتجاوز
    مفتاح SEO_AUTO_PUBLISH_ENABLED (التشغيل هنا قرار صريح من المالك)."""
    _verify_admin(x_admin_secret)
    from api.seo.auto_pipeline import run_daily_seo_cycle
    return run_daily_seo_cycle(force=True)


@router.post("/seo-publish/{page_id}")
def seo_publish(
    page_id: int,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """ينشر صفحة هبوط (draft → published) ثم يخطر الموقع + IndexNow (best-effort)."""
    _verify_admin(x_admin_secret)
    from api.db import get_db_context
    from api.seo.indexer import submit_page

    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE seo_landing_pages SET status='published', published_at=NOW() "
                "WHERE id=%s AND status<>'published' RETURNING slug",
                (page_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="page not found or already published")

    slug = row[0]
    index_result = submit_page(landing_page_id=page_id, slug=slug)
    # ضع وقت آخر فهرسة على الصفحة (كان عموداً غير مُستخدم)
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE seo_landing_pages SET last_indexed_at=NOW() WHERE id=%s", (page_id,))
    from api.utils.ops import audit_log
    audit_log(action="seo_publish", target=slug, meta={"page_id": page_id})
    return {"published": True, "page_id": page_id, "slug": slug, "index": index_result}


@router.get("/seo-drafts")
def seo_drafts(
    limit: int = Query(default=50, ge=1, le=200),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """قائمة صفحات الهبوط بحالة draft — لعرضها في الداشبورد للنشر بضغطة."""
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT p.id, p.slug, p.target_keyword, p.title_meta, p.description_meta,
                       p.lang, p.master_id,
                       COALESCE(NULLIF(m.name_en, ''), m.store_id) AS store_name,
                       length(p.body_markdown) AS body_len
                FROM seo_landing_pages p
                LEFT JOIN master m ON m.id = p.master_id
                WHERE p.status = 'draft'
                ORDER BY p.id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return {"total": len(rows), "drafts": rows}


# ─── Week 7-8: Social listener controls ────────────────────────────────────
@router.post("/social-run")
def social_run(
    batch: int = Query(default=20, ge=1, le=100),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يعالج الإشارات الجديدة (scoring + matching + توليد الردود)."""
    _verify_admin(x_admin_secret)
    from api.social_listener.responder import process_new_signals
    return process_new_signals(batch=batch)


@router.post("/social-poll-now")
def social_poll_now(
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """تشغيل دورة polling يدوية فوراً (Reddit) لتشخيص لماذا لا تظهر leads."""
    _verify_admin(x_admin_secret)
    from api.social_listener.pollers import run_all_pollers
    try:
        return {"ok": True, "stats": run_all_pollers()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:500]}


@router.get("/social-debug")
def social_debug(
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    تشخيص شامل لـ pipeline رادار الصفقات:
      • قيم env vars الحرجة (مُلخّصة دون كشف أسرار)
      • عدد الإشارات حسب status في social_signals
      • أحدث 10 إشارات (id, platform, status, captured_at, preview)
      • عدد المصطلحات النشطة في scorer
      • حالة الجدولة (آخر تشغيل لـ social_listener job)
    """
    _verify_admin(x_admin_secret)
    import os as _os
    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context

    subs = (_os.getenv("REDDIT_SUBREDDITS") or "").strip()
    sub_count = len([s for s in subs.split(",") if s.strip()]) if subs else 0

    env_info = {
        "REDDIT_SUBREDDITS_count": sub_count,
        "REDDIT_SUBREDDITS_preview": subs[:200] if subs else "(unset → uses default 7 subs)",
        "SOCIAL_RESPOND_MIN_INTENT": _os.getenv("SOCIAL_RESPOND_MIN_INTENT", "0.5 (default)"),
        "SOCIAL_AUTO_APPROVE": _os.getenv("SOCIAL_AUTO_APPROVE") or "(off)",
        "WORKER_SOCIAL_PROCESS_MIN": _os.getenv("WORKER_SOCIAL_PROCESS_MIN", "10 (default)"),
        "DISABLE_WORKERS": _os.getenv("DISABLE_WORKERS") or "(off)",
    }

    out = {"env": env_info, "db": {}}

    def _safe(label, fn):
        try:
            out["db"][label] = fn()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            out["db"][f"{label}_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"

    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _safe("signals_total", lambda: (
                cur.execute("SELECT COUNT(*) AS n FROM social_signals"),
                cur.fetchone()["n"],
            )[1])
            _safe("signals_by_status", lambda: (
                cur.execute(
                    "SELECT status, COUNT(*) AS n FROM social_signals "
                    "GROUP BY status ORDER BY n DESC"
                ),
                [dict(r) for r in cur.fetchall()],
            )[1])
            _safe("recent_signals", lambda: (
                cur.execute(
                    "SELECT id, platform, status, intent_score, "
                    "to_char(captured_at, 'YYYY-MM-DD HH24:MI') AS at, "
                    "LEFT(content, 140) AS preview "
                    "FROM social_signals ORDER BY id DESC LIMIT 10"
                ),
                [dict(r) for r in cur.fetchall()],
            )[1])
            _safe("last_ingest_at", lambda: (
                cur.execute(
                    "SELECT to_char(MAX(captured_at), 'YYYY-MM-DD HH24:MI') AS t "
                    "FROM social_signals"
                ),
                cur.fetchone()["t"],
            )[1])
            _safe("active_listening_terms", lambda: (
                cur.execute(
                    "SELECT COUNT(*) AS n FROM social_listening_terms WHERE active = TRUE"
                ),
                cur.fetchone()["n"],
            )[1])
            _safe("v_social_leads_total", lambda: (
                cur.execute("SELECT COUNT(*) AS n FROM v_social_leads"),
                cur.fetchone()["n"],
            )[1])

    # حالة الـ scheduler
    try:
        from api.workers.scheduler import _scheduler, _started
        out["scheduler"] = {
            "started": _started,
            "social_job_next_run": (
                str(_scheduler.get_job("social_listener").next_run_time)
                if _scheduler and _scheduler.get_job("social_listener") else None
            ),
        }
    except Exception as exc:
        out["scheduler_error"] = str(exc)[:200]

    return out


# ═════════════════════════════════════════════════════════════════════════════
# محرك الفرص — Google Trends + keyword CRUD (migration_020)
# ═════════════════════════════════════════════════════════════════════════════
class OpportunityKeywordCreate(BaseModel):
    keyword: str
    store_id: str | None = None
    notes: str | None = None
    active: bool = True


class OpportunityKeywordUpdate(BaseModel):
    keyword: str | None = None
    store_id: str | None = None
    notes: str | None = None
    active: bool | None = None


@router.get("/seo-opportunities")
def seo_opportunities_list(
    sort: str = Query(default="trend_score", description="trend_score|rising_pct|created_at|keyword"),
    only_active: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """قائمة الكلمات المُتابَعة في محرك الفرص + درجة Google Trends لكل منها."""
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context

    sort_col = {
        "trend_score": "trend_score DESC NULLS LAST",
        "rising_pct":  "rising_pct DESC NULLS LAST",
        "created_at":  "created_at DESC",
        "keyword":     "keyword ASC",
    }.get(sort, "trend_score DESC NULLS LAST")

    where = "active = TRUE" if only_active else "1=1"

    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, keyword, store_id, notes, active,
                       trend_score, trend_avg,
                       COALESCE(trend_peak, 0)     AS trend_peak,
                       rising_pct,
                       COALESCE(related_top, '[]'::jsonb)    AS related_top,
                       COALESCE(related_rising, '[]'::jsonb) AS related_rising,
                       to_char(last_checked_at, 'YYYY-MM-DD HH24:MI') AS last_checked_at,
                       last_error, generated_page_id,
                       to_char(created_at, 'YYYY-MM-DD HH24:MI') AS created_at
                FROM seo_opportunity_keywords
                WHERE {where}
                ORDER BY {sort_col}
                LIMIT %s
                """,
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return {"total": len(rows), "keywords": rows}


@router.post("/seo-opportunities")
def seo_opportunities_create(
    payload: OpportunityKeywordCreate,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """إضافة keyword جديد للمتابعة."""
    _verify_admin(x_admin_secret)
    kw = (payload.keyword or "").strip()
    if not kw:
        raise HTTPException(status_code=400, detail="keyword required")
    if len(kw) > 200:
        raise HTTPException(status_code=400, detail="keyword too long (max 200 chars)")

    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO seo_opportunity_keywords
                        (keyword, store_id, notes, active)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, keyword
                    """,
                    (kw, payload.store_id, payload.notes, payload.active),
                )
                row = dict(cur.fetchone())
            except Exception as exc:
                # على الأرجح UNIQUE violation
                if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
                    raise HTTPException(status_code=409, detail="keyword already exists")
                raise HTTPException(status_code=500, detail=str(exc)[:200])
    return {"ok": True, "created": row}


@router.put("/seo-opportunities/{kw_id}")
def seo_opportunities_update(
    kw_id: int,
    payload: OpportunityKeywordUpdate,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """تعديل keyword موجود (الكلمة نفسها، المتجر، الملاحظات، التفعيل)."""
    _verify_admin(x_admin_secret)
    fields, values = [], []
    if payload.keyword is not None:
        kw = payload.keyword.strip()
        if not kw or len(kw) > 200:
            raise HTTPException(status_code=400, detail="invalid keyword")
        fields.append("keyword = %s"); values.append(kw)
    if payload.store_id is not None:
        fields.append("store_id = %s"); values.append(payload.store_id or None)
    if payload.notes is not None:
        fields.append("notes = %s"); values.append(payload.notes or None)
    if payload.active is not None:
        fields.append("active = %s"); values.append(payload.active)
    if not fields:
        raise HTTPException(status_code=400, detail="nothing to update")
    fields.append("updated_at = NOW()")
    values.append(kw_id)

    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE seo_opportunity_keywords SET {', '.join(fields)} "
                f"WHERE id = %s RETURNING id",
                values,
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="keyword not found")
    return {"ok": True, "id": kw_id}


@router.delete("/seo-opportunities/{kw_id}")
def seo_opportunities_delete(
    kw_id: int,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """حذف keyword نهائياً."""
    _verify_admin(x_admin_secret)
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM seo_opportunity_keywords WHERE id = %s RETURNING id",
                (kw_id,),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="keyword not found")
    return {"ok": True, "deleted": kw_id}


@router.post("/seo-opportunities/{kw_id}/refresh")
def seo_opportunities_refresh(
    kw_id: int,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """جلب فوري لدرجة Google Trends لهذا الـ keyword (بدون انتظار الـ scheduler)."""
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context
    from api.seo.trends_puller import fetch_keyword_score

    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT keyword FROM seo_opportunity_keywords WHERE id = %s",
                (kw_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="keyword not found")
            kw = row["keyword"]

        import json as _json
        result = fetch_keyword_score(kw)
        with conn.cursor() as cur2:
            if result["ok"]:
                cur2.execute(
                    """
                    UPDATE seo_opportunity_keywords
                    SET trend_score=%s, trend_avg=%s,
                        trend_peak=%s, rising_pct=%s,
                        related_top=%s::jsonb, related_rising=%s::jsonb,
                        last_checked_at=NOW(), last_error=NULL
                    WHERE id=%s
                    """,
                    (result["trend_score"], result["trend_avg"],
                     result.get("trend_peak", 0), result["rising_pct"],
                     _json.dumps(result.get("related_top") or []),
                     _json.dumps(result.get("related_rising") or []),
                     kw_id),
                )
            else:
                cur2.execute(
                    """
                    UPDATE seo_opportunity_keywords
                    SET last_checked_at=NOW(), last_error=%s
                    WHERE id=%s
                    """,
                    (result["error"], kw_id),
                )
    return {"ok": result["ok"], "result": result}


@router.post("/seo-opportunities/refresh-all")
def seo_opportunities_refresh_all(
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """جلب فوري لكل الـ active keywords (يستغرق وقتاً — 5s × عدد الكلمات)."""
    _verify_admin(x_admin_secret)
    from api.seo.trends_puller import refresh_all_active_keywords
    try:
        return {"ok": True, "stats": refresh_all_active_keywords()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:500]}


class TrackRelatedQueryBody(BaseModel):
    keyword: str
    store_id: str | None = None


@router.post("/seo-opportunities/track-related")
def seo_opportunities_track_related(
    payload: TrackRelatedQueryBody,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    يحوّل related query من Google Trends إلى keyword مُتابع رسمياً.
    استدعاء نقرة-واحدة من الـ dashboard عند ضغط [+ تتبّع] بجانب اقتراح.
    Idempotent: لو الـ keyword موجود مسبقاً يُرجع id الموجود.
    """
    _verify_admin(x_admin_secret)
    kw = (payload.keyword or "").strip()
    if not kw or len(kw) > 200:
        raise HTTPException(status_code=400, detail="invalid keyword")

    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id FROM seo_opportunity_keywords WHERE keyword = %s",
                (kw,),
            )
            existing = cur.fetchone()
            if existing:
                return {"ok": True, "already_tracked": True, "id": existing["id"]}
            cur.execute(
                """
                INSERT INTO seo_opportunity_keywords
                    (keyword, store_id, notes, active)
                VALUES (%s, %s, %s, TRUE)
                RETURNING id
                """,
                (kw, payload.store_id, "auto-tracked من Google Trends related"),
            )
            new_id = cur.fetchone()["id"]
    return {"ok": True, "created": True, "id": new_id}


@router.get("/trends-debug")
def trends_debug(
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يتحقق من حالة pytrends + Google Suggest على Railway."""
    _verify_admin(x_admin_secret)
    from api.seo.trends_puller import (
        get_init_status, fetch_keyword_score, fetch_google_suggestions,
    )
    out = {"init_status": get_init_status()}
    # اختبار pytrends
    try:
        out["pytrends_test"] = fetch_keyword_score("noon", geo="SA",
                                                    with_related=False)
    except Exception as exc:
        out["pytrends_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    # اختبار Google Suggest (لا يستخدم pytrends — مسار مستقل)
    try:
        out["suggest_test_arabic"] = fetch_google_suggestions(
            "كود خصم نون", hl="ar", gl="sa"
        )
    except Exception as exc:
        out["suggest_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    return out


@router.post("/seo-opportunities/{kw_id}/generate-page")
def seo_opportunities_generate_page(
    kw_id: int,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    يولّد صفحة هبوط /c/{slug} لهذا الـ keyword الآن:
      1. يطابق المتجر (store_id المُحدّد، أو trigram على master)
      2. يُنشئ seo_generation_jobs بـ state='queued'
      3. يُشغّل process_pending_jobs(batch=1) فوراً (sync)
      4. يحدّث seo_opportunity_keywords.generated_page_id
    """
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context

    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, keyword, store_id, generated_page_id "
                "FROM seo_opportunity_keywords WHERE id = %s",
                (kw_id,),
            )
            opp = cur.fetchone()
            if not opp:
                raise HTTPException(status_code=404, detail="keyword not found")
            if opp["generated_page_id"]:
                return {"ok": True, "already_generated": True,
                        "page_id": opp["generated_page_id"]}

            kw = opp["keyword"]

            # 1) أوجد المتجر المُطابق
            if opp["store_id"]:
                cur.execute("SELECT id FROM master WHERE store_id = %s LIMIT 1",
                            (opp["store_id"],))
            else:
                cur.execute(
                    """
                    SELECT id,
                           GREATEST(
                               similarity(lower(store_id),                    lower(%(q)s)),
                               similarity(lower(COALESCE(name_en, '')),       lower(%(q)s)),
                               similarity(lower(COALESCE(store_tags, '')),    lower(%(q)s))
                           ) AS sim
                    FROM master ORDER BY sim DESC LIMIT 1
                    """,
                    {"q": kw},
                )
            master = cur.fetchone()
            if not master:
                raise HTTPException(status_code=400,
                    detail="no matching store — set store_id manually or add the store to master")

            master_id = master["id"]

            # 2) أنشئ job (مع تجاهل التكرارات)
            cur.execute(
                """
                INSERT INTO seo_generation_jobs
                    (target_keyword, matched_master_id, state)
                VALUES (%s, %s, 'queued')
                ON CONFLICT (target_keyword, matched_master_id)
                    WHERE state IN ('queued', 'running')
                    DO NOTHING
                RETURNING id
                """,
                (kw, master_id),
            )
            job_row = cur.fetchone()
            job_id = job_row["id"] if job_row else None

    # 3) شغّل الوظيفة فوراً (sync). قد تستغرق 20-40 ثانية بسبب LLM
    from api.seo.generator import process_pending_jobs
    try:
        stats = process_pending_jobs(batch=1)
    except Exception as exc:
        return {"ok": False, "error": f"generator crashed: {str(exc)[:200]}",
                "job_id": job_id}

    # 4) ابحث عن الصفحة الناتجة واربطها
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, slug, status FROM seo_landing_pages "
                "WHERE target_keyword = %s ORDER BY id DESC LIMIT 1",
                (kw,),
            )
            page = cur.fetchone()
            if page:
                cur.execute(
                    "UPDATE seo_opportunity_keywords SET generated_page_id=%s WHERE id=%s",
                    (page["id"], kw_id),
                )
                return {"ok": True, "page_id": page["id"], "slug": page["slug"],
                        "status": page["status"], "generator_stats": stats}

    return {"ok": True, "job_id": job_id, "generator_stats": stats,
            "note": "job queued/ran but no page row found yet — check seo-drafts"}


@router.get("/social-pending")
def social_pending(
    limit: int = Query(default=50, ge=1, le=200),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """ردود بانتظار المراجعة/النشر — لعرضها في الداشبورد."""
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT r.id, r.rendered_text, r.link_url, r.review_status, r.master_id,
                       s.platform, s.author_handle, s.content AS signal_content,
                       s.intent_score, s.source_url
                FROM social_responses r
                JOIN social_signals s ON s.id = r.signal_id
                WHERE r.review_status IN ('pending', 'auto_approved', 'approved')
                ORDER BY r.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return {"total": len(rows), "responses": rows}


@router.post("/social-approve/{response_id}")
def social_approve(
    response_id: int,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يعتمد رداً وينشره (عبر SOCIAL_POST_WEBHOOK أو يعلّمه approved)."""
    _verify_admin(x_admin_secret)
    from api.social_listener.poster import post_response
    from api.utils.ops import audit_log
    res = post_response(response_id)
    audit_log(action="social_approve", target=str(response_id), meta=res)
    return res


@router.post("/social-reject/{response_id}")
def social_reject(
    response_id: int,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    _verify_admin(x_admin_secret)
    from api.db import get_db_context
    from api.utils.ops import audit_log
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE social_responses SET review_status='rejected' WHERE id=%s",
                (response_id,),
            )
    audit_log(action="social_reject", target=str(response_id))
    return {"ok": True, "rejected": response_id}


# ─── Cross-cutting controls (migration_016) ─────────────────────────────────
@router.get("/audit-log")
def audit_log_list(
    limit: int = Query(default=100, ge=1, le=500),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """آخر عمليات الأدمن (سجل التدقيق PDPL)."""
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, actor, action, target, status,
                       to_char(created_at, 'YYYY-MM-DD HH24:MI') AS at
                FROM pdpl_audit_log ORDER BY id DESC LIMIT %s
                """,
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return {"total": len(rows), "entries": rows}


@router.get("/quiet-hours")
def quiet_hours_list(x_admin_secret: str = Header(..., alias="X-Admin-Secret")):
    """نوافذ كتم التنبيهات."""
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context
    from api.utils.ops import is_quiet_now
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, label, start_hour, end_hour, timezone, channels, active "
                "FROM alert_quiet_hours ORDER BY id"
            )
            rows = [dict(r) for r in cur.fetchall()]
    quiet, label = is_quiet_now("email")
    return {"windows": rows, "email_muted_now": quiet, "active_window": label}


@router.post("/quiet-hours/{qid}/toggle")
def quiet_hours_toggle(qid: int, x_admin_secret: str = Header(..., alias="X-Admin-Secret")):
    """يبدّل تفعيل نافذة هدوء."""
    _verify_admin(x_admin_secret)
    from api.db import get_db_context
    from api.utils.ops import audit_log
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alert_quiet_hours SET active = NOT active WHERE id=%s RETURNING active",
                (qid,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="quiet-hours window not found")
    audit_log(action="quiet_hours_toggle", target=str(qid), meta={"active": row[0]})
    return {"ok": True, "id": qid, "active": row[0]}


@router.get("/experiments")
def experiments_results(x_admin_secret: str = Header(..., alias="X-Admin-Secret")):
    """نتائج تجارب A/B (impressions/clicks/conversions لكل arm)."""
    _verify_admin(x_admin_secret)
    from api.utils.ops import experiment_results
    return {"results": experiment_results()}


@router.get("/seo-google-check")
def seo_google_check(x_admin_secret: str = Header(..., alias="X-Admin-Secret")):
    """
    تشخيص إعداد Google Indexing API. يفحص: المفتاح، الـ token، ownership.
    يُرجع رسالة واضحة لأي خطأ + خطوة الإصلاح التالية.
    """
    _verify_admin(x_admin_secret)
    from api.seo.indexer import diagnose_google_setup
    return diagnose_google_setup()


@router.get("/seo-draft/{page_id}")
def seo_draft_full(
    page_id: int,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يجلب محتوى مسودّة كامل (للعرض في الداشبورد أو الـ CLI قبل النشر)."""
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor

    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT p.id, p.slug, p.lang, p.target_keyword, p.status,
                       p.title_meta, p.description_meta, p.body_markdown,
                       COALESCE(NULLIF(m.name_en, ''), m.store_id) AS store_name,
                       to_char(p.published_at, 'YYYY-MM-DD HH24:MI') AS published_at
                FROM seo_landing_pages p
                LEFT JOIN master m ON m.id = p.master_id
                WHERE p.id = %s
                """,
                (page_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="page not found")
    return dict(row)


class SeoDraftUpdate(BaseModel):
    """تعديل حقول مسودّة قبل النشر (كلها اختيارية — نُحدّث الموجود فقط)."""
    title_meta: str | None = None
    description_meta: str | None = None
    body_markdown: str | None = None


@router.put("/seo-draft/{page_id}")
def seo_draft_update(
    page_id: int,
    payload: SeoDraftUpdate,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يُعدّل محتوى مسودّة (title/description/body). للمسودّات فقط — لا تعديل بعد النشر."""
    _verify_admin(x_admin_secret)
    from api.db import get_db_context

    sets: list[str] = []
    params: list = []
    if payload.title_meta is not None:
        sets.append("title_meta = %s")
        params.append(payload.title_meta[:180])
    if payload.description_meta is not None:
        sets.append("description_meta = %s")
        params.append(payload.description_meta[:280])
    if payload.body_markdown is not None:
        sets.append("body_markdown = %s")
        params.append(payload.body_markdown)
        # نُحدّث body_html_hash لو body تغيّر
        import hashlib
        sets.append("body_html_hash = %s")
        params.append(hashlib.sha256(payload.body_markdown.encode("utf-8")).digest())

    if not sets:
        raise HTTPException(status_code=400, detail="لا يوجد ما يُحدَّث")

    params.append(page_id)
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE seo_landing_pages SET {', '.join(sets)} "
                f"WHERE id = %s AND status = 'draft' RETURNING id",
                params,
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="مسودّة غير موجودة (أو منشورة بالفعل)")

    from api.utils.ops import audit_log
    audit_log(action="seo_draft_update", target=str(page_id),
              meta={"fields": [s.split("=")[0].strip() for s in sets]})
    return {"ok": True, "page_id": page_id, "updated": True}


@router.delete("/seo-draft/{page_id}")
def seo_draft_delete(
    page_id: int,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يحذف مسودّة نهائياً (لا يُؤثر على الصفحات المنشورة)."""
    _verify_admin(x_admin_secret)
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM seo_landing_pages WHERE id = %s AND status = 'draft' "
                "RETURNING slug",
                (page_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="مسودّة غير موجودة (أو منشورة)")

    from api.utils.ops import audit_log
    audit_log(action="seo_draft_delete", target=str(page_id), meta={"slug": row[0]})
    return {"ok": True, "page_id": page_id, "deleted_slug": row[0]}


@router.post("/seo-seed-custom")
def seo_seed_custom(
    topic: str = Query(..., min_length=2, max_length=80,
                        description="موضوع/مناسبة (مثل: يوم التأسيس، رمضان، عودة المدارس)"),
    max_stores: int = Query(default=15, ge=1, le=50,
                             description="عدد المتاجر التي ننشئ لها صفحة بهذا الموضوع"),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    يولّد وظائف صفحات SEO بموضوع مخصّص (يحدّده المستخدم) × أهمّ المتاجر.

    أمثلة استخدام:
      topic="يوم التأسيس"           → 'كود خصم {store} يوم التأسيس'
      topic="رمضان 2026"            → 'كود خصم {store} رمضان 2026'
      topic="عروض البلاك فرايدي"   → 'كود خصم {store} عروض البلاك فرايدي'

    بعد التشغيل، استدعِ /admin/seo-run?batch=N لتوليد الصفحات الفعلية عبر LLM.
    """
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor

    from api.db import get_db_context

    topic_clean = topic.strip()
    if not topic_clean:
        raise HTTPException(status_code=400, detail="الموضوع لا يمكن أن يكون فارغاً")

    # 3 أنماط لكل متجر لتوسعة التغطية بدون تكرار:
    patterns_ar = [
        "كود خصم {store} {topic}",
        "{store} {topic} 2026",
        "أفضل عروض {store} {topic}",
    ]

    enqueued = 0
    skipped_duplicate = 0
    errors = 0

    with get_db_context() as conn:
        # نأخذ أهم المتاجر بحسب الـ trending score
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, store_id,
                       COALESCE(NULLIF(name_en, ''), store_id) AS display_name
                FROM master
                WHERE COALESCE(affiliate_link, '') <> ''
                ORDER BY (COALESCE(total_link_clicks, 0) + COALESCE(total_coupon_copies, 0) * 2) DESC NULLS LAST
                LIMIT %s
                """,
                (max_stores,),
            )
            stores = cur.fetchall()

        for store in stores:
            name = store["display_name"]
            for pat in patterns_ar:
                kw = pat.format(store=name, topic=topic_clean)
                try:
                    with conn.cursor() as cur:
                        # dedup عبر seo_generation_jobs + seo_landing_pages
                        cur.execute(
                            "SELECT 1 FROM seo_generation_jobs WHERE target_keyword = %s LIMIT 1",
                            (kw,),
                        )
                        if cur.fetchone():
                            skipped_duplicate += 1
                            continue
                        cur.execute(
                            "SELECT 1 FROM seo_landing_pages WHERE target_keyword = %s LIMIT 1",
                            (kw,),
                        )
                        if cur.fetchone():
                            skipped_duplicate += 1
                            continue

                        cur.execute(
                            "INSERT INTO seo_generation_jobs "
                            "(target_keyword, matched_master_id, state) "
                            "VALUES (%s, %s, 'queued')",
                            (kw, store["id"]),
                        )
                        enqueued += 1
                except Exception:
                    errors += 1

    from api.utils.ops import audit_log
    audit_log(
        action="seo_seed_custom",
        target=topic_clean[:60],
        meta={"max_stores": max_stores, "enqueued": enqueued,
              "skipped": skipped_duplicate},
    )
    return {
        "topic":             topic_clean,
        "stores_processed":  len(stores),
        "jobs_enqueued":     enqueued,
        "jobs_skipped_duplicate": skipped_duplicate,
        "errors":            errors,
        "next_action":       "استدعِ /admin/seo-run?batch=N للتوليد الفعلي عبر LLM",
    }


@router.get("/seo-failed-jobs")
def seo_failed_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    آخر وظائف SEO فشلت. مفيد لتشخيص أسباب الفشل (LLM error, JSON parse, ...).
    يرجّع: id, target_keyword, error_message, completed_at.
    """
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor

    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, target_keyword, state,
                       LEFT(COALESCE(error_message, ''), 500) AS error_message,
                       to_char(completed_at, 'YYYY-MM-DD HH24:MI:SS') AS completed_at
                FROM seo_generation_jobs
                WHERE state = 'failed'
                ORDER BY completed_at DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return {"total": len(rows), "failed_jobs": rows}


@router.post("/seo-retry-failed")
def seo_retry_failed(
    limit: int = Query(default=50, ge=1, le=300),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    يُعيد جدولة الـ failed jobs كـ queued لتُعالَج في الدورة التالية.
    مفيد بعد إصلاح bug — تعيد محاولة كل الفاشلين.
    """
    _verify_admin(x_admin_secret)
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE seo_generation_jobs
                SET state='queued',
                    error_message=NULL,
                    started_at=NULL,
                    completed_at=NULL
                WHERE id IN (
                    SELECT id FROM seo_generation_jobs
                    WHERE state='failed'
                    ORDER BY completed_at DESC NULLS LAST
                    LIMIT %s
                )
                RETURNING id
                """,
                (limit,),
            )
            requeued = len(cur.fetchall())
    return {"requeued": requeued}


@router.post("/seo-seed-long-tail")
def seo_seed_long_tail(
    max_stores: int = Query(default=30, ge=1, le=100,
                             description="عدد المتاجر التي ننتقي منها"),
    sort_by: str = Query(default="trending",
                          description="trending | engagement | recent"),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    يولّد وظائف SEO بكلمات long-tail (منخفضة المنافسة) لأهمّ المتاجر.

    مثال: 30 متجر × 10-12 نمط = 300-360 صفحة محتملة. الـ dedup يمنع التكرار،
    فلو شغّلته مرّتين ما يضاعف العدد.

    بعد التشغيل، استخدم /admin/seo-run?batch=50 لتوليد الصفحات فعلياً عبر LLM.
    """
    _verify_admin(x_admin_secret)
    from api.seo.seed_long_tail import seed_long_tail_jobs
    return seed_long_tail_jobs(max_stores=max_stores, sort_by=sort_by)


@router.post("/seo-resubmit-url")
def seo_resubmit_url(
    url: str = Query(..., min_length=10, description="URL كامل للإعادة الإرسال"),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    إعادة إرسال URL محدّد لكل محركات البحث (IndexNow + Google).
    مفيد عند تحديث محتوى صفحة منشورة أو تشغيل ping يدوي على homepage.
    """
    _verify_admin(x_admin_secret)
    from api.seo.indexer import resubmit_url
    return resubmit_url(url)


# ─── Social Leads Radar (migration_018 — v_social_leads view) ──────────────
@router.get("/social-leads")
def social_leads_list(
    status: str = Query(default="pending", description="pending|replied|dismissed|all"),
    limit: int = Query(default=100, ge=1, le=500),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    قائمة الـ social leads — العملاء الذين كتبوا منشوراً عن متجر نُغطّيه
    وينتظرون رد يدوي.

    status:
      pending    → matched/responded/lead_pending (لم تتعامل معه بعد)
      replied    → lead_replied (ضغطت 'تم الرد')
      dismissed  → lead_dismissed (قرّرت تجاهله)
      all        → كل ما سبق
    """
    _verify_admin(x_admin_secret)
    from psycopg2.extras import RealDictCursor

    from api.db import get_db_context

    status_filter = {
        "pending":   "status IN ('matched', 'responded', 'lead_pending')",
        "replied":   "status = 'lead_replied'",
        "dismissed": "status = 'lead_dismissed'",
        "all":       "1=1",
    }.get(status, "status IN ('matched', 'responded', 'lead_pending')")

    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT lead_id, platform, username, post_text, post_url,
                       intent_score, target_store, target_store_id,
                       target_cloaked_slug, status, age_seconds,
                       to_char(captured_at, 'YYYY-MM-DD HH24:MI') AS captured_at_fmt
                FROM v_social_leads
                WHERE {status_filter}
                ORDER BY captured_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return {"total": len(rows), "status_filter": status, "leads": rows}


@router.post("/social-leads/{lead_id}/mark-replied")
def social_leads_mark_replied(
    lead_id: int,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يعلّم العميل أنك رددت عليه يدوياً → يختفي من شاشة pending."""
    _verify_admin(x_admin_secret)
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE social_signals SET status='lead_replied' WHERE id=%s "
                "AND status IN ('matched','responded','lead_pending') RETURNING id",
                (lead_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found or already processed")
    return {"ok": True, "lead_id": lead_id, "new_status": "lead_replied"}


@router.post("/social-leads/{lead_id}/dismiss")
def social_leads_dismiss(
    lead_id: int,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """يتجاهل العميل (تقرّر عدم الرد) — يختفي من pending."""
    _verify_admin(x_admin_secret)
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE social_signals SET status='lead_dismissed' WHERE id=%s "
                "AND status IN ('matched','responded','lead_pending') RETURNING id",
                (lead_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"ok": True, "lead_id": lead_id, "new_status": "lead_dismissed"}


