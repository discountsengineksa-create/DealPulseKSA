"""
Affiliate cloaking redirect (Week 4).

GET /go/{slug}
  1. يبحث عن المتجر بالـ cloaked_slug ويحوّل لرابط الأفلييت الحقيقي (302).
  2. "Bot Challenge": الزائر المشكوك فيه (quality_score منخفض) يحصل على صفحة
     تحدّي JS بدل التحويل المباشر. البوتات اللي ما تشغّل JS تتوقف هنا فلا
     تصل لرابط الأفلييت — يحمي حساب الأفلييت من النقرات الوهمية وحظره.
  3. النقرات عالية الجودة فقط تُحدّث عدّاد master.total_link_clicks
     (نفس فلسفة /track في الأسبوع الأول).

ملاحظة أمنية: رابط الأفلييت لا يظهر أبداً في جسم HTML — فقط في ترويسة
302 Location، ولعميل اجتاز فحص الجودة أو أثبت تشغيل JS (h=1).

الإثراء (geo + bot score) يأتي من Cloudflare Worker عبر x-dp-* headers.
لو الـ Worker غائب (تطوير محلي أو route غير مضاف)، quality_score يرتفع
افتراضياً → التحويل يمر مباشرة (fail-open) ويتعطّل التحدّي فقط.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg2.extras import RealDictCursor

from api.db import get_db
from api.utils.event_publisher import publish_event
from api.utils.fraud_scoring import compute_quality_score
from api.utils.geo_extractor import extract as extract_geo
from api.utils.rate_limit import LIMIT_GO_REDIRECT, limiter
from api.utils.redis_client import get_redis

_log = logging.getLogger("dp.go")
router = APIRouter(prefix="/go", tags=["cloaking"])

# نفس عتبة /track — تحت هذا الحد لا نُحدّث العدّادات ونطلب تحدّي JS
QUALITY_THRESHOLD = 50

# ─── Redis cache for slug→(store_id, affiliate_link) ─────────────────────────
# يُسرّع التحويلات الشائعة (نفس الـ slug آلاف المرات في الدقيقة).
# TTL=10min: قصير كفاية لانعكاس تغييرات master، طويل كفاية لتقليل DB hits.
_CACHE_TTL_SEC = 600


def _cache_lookup(slug: str) -> tuple[int, str, str] | None:
    """يبحث في Redis. يُعيد (id, store_id, affiliate_link) أو None."""
    try:
        r = get_redis()
        raw = r.get(f"go:slug:{slug}")
        if not raw:
            return None
        # تنسيق: "id|store_id|url"
        parts = raw.split("|", 2)
        if len(parts) != 3:
            return None
        return int(parts[0]), parts[1], parts[2]
    except Exception:
        return None


def _cache_store(slug: str, master_id: int, store_id: str, link: str) -> None:
    """يخزّن في Redis مع TTL. خاطئ بصمت لو Redis معطّل."""
    try:
        r = get_redis()
        r.set(f"go:slug:{slug}", f"{master_id}|{store_id}|{link}")
        r.expire(f"go:slug:{slug}", _CACHE_TTL_SEC)
    except Exception:
        pass


def _challenge_page(slug: str, s: str, u: str = "") -> str:
    """صفحة تحدّي JS — تُعيد التوجيه لنفس الرابط مع h=1 لإثبات تشغيل JS."""
    safe_slug = "".join(c for c in slug if c.isalnum())
    safe_src = "".join(c for c in (s or "") if c.isalnum()) or "web"
    safe_u = "".join(c for c in (u or "") if c.isdigit())
    u_q = f"&u={safe_u}" if safe_u else ""
    target = f"/go/{safe_slug}?s={safe_src}&h=1{u_q}"
    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>جارٍ التحويل…</title>
<style>
  body{{font-family:'Segoe UI',Tahoma,sans-serif;background:#FAFAF8;color:#111827;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
  .box{{text-align:center}}
  .spin{{width:42px;height:42px;border:4px solid #D1FAE5;border-top-color:#10B981;
        border-radius:50%;animation:r .8s linear infinite;margin:0 auto 16px}}
  @keyframes r{{to{{transform:rotate(360deg)}}}}
</style></head>
<body><div class="box">
  <div class="spin"></div>
  <div>جارٍ تحويلك إلى المتجر…</div>
</div>
<script>
  // عميل حقيقي يشغّل JS → يُعاد التوجيه مع إثبات h=1.
  setTimeout(function(){{ window.location.replace("{target}"); }}, 600);
</script>
</body></html>"""


def _not_found_page() -> str:
    """صفحة 404 بسيطة — لا تكشف وجود/عدم وجود الـ slug."""
    return """<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow"><title>غير متوفر</title>
<style>body{font-family:'Segoe UI',Tahoma,sans-serif;background:#FAFAF8;color:#111827;
text-align:center;padding-top:18vh}</style></head>
<body><h2>الرابط غير متوفر</h2>
<p>قد يكون العرض انتهى. تصفّح أحدث العروض على <a href="https://dealpulseksa.com">dealpulseksa.com</a>.</p>
</body></html>"""


@router.get("/{slug}", include_in_schema=False)
@limiter.limit(LIMIT_GO_REDIRECT)
def cloaked_redirect(
    slug: str,
    request: Request,
    s: str = "web",
    h: str = "0",
    u: str = "",
    ctx: str = "",
    conn=Depends(get_db),
):
    # 1) البحث عن المتجر — Redis cache أولاً، ثم DB
    cached = _cache_lookup(slug)
    if cached:
        master_id_int, store_id, target_url = cached
    else:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, store_id, affiliate_link FROM master WHERE cloaked_slug = %s",
                (slug,),
            )
            row = cur.fetchone()
        # slug غير موجود إطلاقاً → 404 بلا تسجيل (لا نعرف أي متجر).
        if not row:
            return HTMLResponse(_not_found_page(), status_code=404)
        target_url = (row.get("affiliate_link") or "").strip()
        store_id = row["store_id"]
        master_id_int = row["id"]
        # نخزّن في الكاش فقط لو الرابط موجود (المتاجر بلا رابط نُعيد فحصها كل مرة).
        if target_url:
            _cache_store(slug, master_id_int, store_id, target_url)

    # 2) إثراء + جودة
    geo = extract_geo(request)
    quality, is_dc, is_proxy = compute_quality_score(geo)
    js_passed = h == "1"
    # bot / miniapp يُحفظان منفصلين؛ أي شيء آخر = web
    source = {"bot": "bot", "miniapp": "telegram_miniapp"}.get(s, "web")
    # u = معرّف مستخدم تيليجرام (يمرّره البوت/الميني) → يربط النقرة + المدينة بالشخص
    click_user_id = int(u) if (u or "").isdigit() else None

    # 3) Bot Challenge — مشكوك فيه ولم يُثبت JS بعد → صفحة تحدّي (بلا تسجيل/تحويل)
    if quality < QUALITY_THRESHOLD and not js_passed:
        _log.info("Bot challenge served: store=%s slug=%s quality=%d asn=%s",
                  store_id, slug, quality, geo.asn)
        return HTMLResponse(_challenge_page(slug, s, u))

    # 4) مسموح — سجّل النقرة (idempotent). العدّاد يرتفع للجودة العالية فقط.
    counted = quality >= QUALITY_THRESHOLD
    # سياق الإسناد (ترند يومي/أسبوعي + أبرز المتاجر) — قائمة بيضاء، يُخزَّن
    # في details لفصل buckets في تحليل المتاجر (mutually-exclusive).
    attr_ctx = ctx if ctx in ("trend:daily", "trend:weekly", "featured") else None
    details_val = attr_ctx if attr_ctx else (
        "via_cloak" if counted else "via_cloak_jschallenge")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO action_logs (
                user_id, store_id, action_type, details, source,
                event_id, ip_hash, user_agent_hash,
                country_code, region_code, city, postal_code,
                lat, lng, isp, asn,
                is_datacenter, is_proxy, device_class,
                cf_bot_score, quality_score
            ) VALUES (
                %s, %s, 'click_link', %s, %s,
                %s::uuid, decode(%s, 'hex'), decode(%s, 'hex'),
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
                click_user_id, store_id,
                details_val, source,
                geo.event_id, geo.ip_hash, geo.ua_hash,
                geo.country_code, geo.region_code, geo.city, geo.postal_code,
                geo.lat, geo.lng, geo.isp, geo.asn,
                is_dc, is_proxy, geo.device_class,
                geo.cf_bot_score, quality,
            ),
        )
        if counted:
            cur.execute(
                "UPDATE master SET total_link_clicks = total_link_clicks + 1 WHERE id = %s",
                (master_id_int,),
            )

    # 5) fan-out best-effort لـ Redis Stream (نفس مسار /track)
    publish_event("events:raw", {
        "event_id": geo.event_id,
        "store_id": store_id,
        "action": "click_link",
        "source": source,
        "country": geo.country_code,
        "city": geo.city,
        "quality": quality,
        "is_datacenter": is_dc,
        "is_proxy": is_proxy,
        "via": "cloak",
    })

    # 6) لو الرابط فاضي: النقرة سُجّلت أعلاه، نُظهر 404 بدلاً من التحويل.
    #    الفائدة: نية المستخدم بالنقر تدخل الترند، حتى لو المتجر بلا رابط أفلييت
    #    (متجر تجريبي مثلاً). master.total_link_clicks ارتفع لو الجودة عالية.
    if not target_url:
        return HTMLResponse(_not_found_page(), status_code=404)

    # 7) تحويل 302 — رابط الأفلييت في الترويسة فقط، بلا كاش ولا referrer
    resp = RedirectResponse(url=target_url, status_code=302)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp
