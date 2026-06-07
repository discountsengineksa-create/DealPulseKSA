"""
Endpoints لتتبّع فتح/نقر حملات الإشعارات والبريد.

المسارات (بدون /api/v1 prefix — مدخلات عامة قصيرة):
  GET /bt/o/{token}.gif   ← يرجّع pixel 1x1 شفاف + يسجّل فتح بريد
  GET /bt/c/{token}/{lid} ← 302 إلى URL الأصلي + يسجّل نقرة

ملاحظات أمنية:
  • token = UUID فريد لكل مستلم. ليس قابلاً للتخمين، لذا لا حاجة لـ signing.
  • بدون CORS — هذي endpoints public للزوّار (من بريد أو متصفح).
  • IP يُحفظ كـ hash فقط (احتراماً للخصوصية + ipv4 enrichment لاحقاً).
  • فشل التسجيل لا يُسبّب 5xx — pixel/redirect يعمل دائماً (best-effort tracking).
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from psycopg2.extras import RealDictCursor

from api.db import get_db

_log = logging.getLogger("dp.broadcast_tracking")

# ─── كاشف البوتات الـpre-fetching ──────────────────────────────────────────
# Telegram/WhatsApp/Slack/Discord/Gmail-proxy يفتحون كل URL تلقائياً قبل أن
# يضغطه المستخدم (لتوليد link preview أو cache صور البريد). بدون استبعادهم
# تظهر CTR وهمية ٪١٠٠. نُسجّل عدّاد منفصل (preview_count) لو احتيج لاحقاً.
_BOT_UA_PATTERN = re.compile(
    r"("
    r"TelegramBot|WhatsApp|facebookexternalhit|Facebot|LinkedInBot|"
    r"Slackbot|DiscordBot|SkypeUriPreview|TwitterBot|Twitterbot|"
    r"GoogleImageProxy|YahooMailProxy|Outlook|MSOffice|"
    r"vkShare|W3C_Validator|Pingdom|googleweblight|Mediapartners-Google|"
    r"Googlebot|bingbot|Baiduspider|YandexBot|DuckDuckBot|"
    r"Applebot|PetalBot|SeznamBot|"
    r"HeadlessChrome|PhantomJS|Lighthouse|Chrome-Lighthouse|"
    r"\bspider\b|\bcrawler\b|\bscraper\b"
    r")",
    re.IGNORECASE,
)


def _is_bot_user_agent(ua: str | None) -> bool:
    """يرجّع True لو الـUser-Agent يبدو لبوت/preview/proxy."""
    if not ua:
        return True   # طلب بدون UA = على الأغلب بوت/سكربت
    return bool(_BOT_UA_PATTERN.search(ua))

router = APIRouter(prefix="/bt", tags=["broadcast-tracking"])

# 1×1 GIF شفاف (43 بايت — أصغر صورة ممكنة)
_PIXEL_GIF_BYTES = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


def _hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:32]


def _client_ip(request: Request) -> str | None:
    """يستخرج IP من ترويسات الـproxy أو client.host."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    real = request.headers.get("x-real-ip", "")
    if real:
        return real.strip()
    return request.client.host if request.client else None


# ════════════════════════════════════════════════════════════════════════════
# /bt/o/{token}.gif — تتبّع فتح البريد
# ════════════════════════════════════════════════════════════════════════════

@router.get("/o/{token}.gif", include_in_schema=False)
async def track_open(token: str, request: Request, conn=Depends(get_db)) -> Response:
    """يحدّث open_count + opened_at + يسجّل سطر في broadcast_email_opens.

    يُرجع دائماً pixel GIF حتى لو فشل التحديث (alert يُسجّل).
    """
    if token and len(token) <= 64:   # سلامة أساسية
        try:
            ip = _client_ip(request)
            ip_h = _hash_ip(ip)
            ua = (request.headers.get("user-agent") or "")[:300]
            is_bot = _is_bot_user_agent(ua)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, broadcast_kind FROM broadcast_recipients "
                    "WHERE tracking_token = %s LIMIT 1",
                    (token,),
                )
                row = cur.fetchone()
                if row and row["broadcast_kind"] == "email":
                    rid = row["id"]
                    if is_bot:
                        # bot prefetch (Gmail image proxy, etc.) — لا نحدّث الإحصاء
                        # لكن نحفظ السطر مع علامة (للتشخيص اللاحق)
                        cur.execute(
                            "INSERT INTO broadcast_email_opens "
                            "(recipient_id, ip_hash, user_agent) "
                            "VALUES (%s,%s,%s)",
                            (rid, ip_h, f"[BOT] {ua}"[:300]),
                        )
                    else:
                        cur.execute(
                            "UPDATE broadcast_recipients "
                            "SET open_count = COALESCE(open_count,0) + 1, "
                            "    opened_at  = COALESCE(opened_at, NOW()), "
                            "    status     = CASE WHEN status IN ('sent','queued','sending') "
                            "                       THEN 'opened' ELSE status END "
                            "WHERE id = %s",
                            (rid,),
                        )
                        cur.execute(
                            "INSERT INTO broadcast_email_opens "
                            "(recipient_id, ip_hash, user_agent) "
                            "VALUES (%s,%s,%s)",
                            (rid, ip_h, ua),
                        )
                    conn.commit()
        except Exception as exc:
            _log.warning("open tracking failed for %s: %s", token[:8], str(exc)[:200])
            try: conn.rollback()
            except Exception: pass

    # ترويسات لمنع الـcaching (كل فتح = طلب جديد)
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, private, max-age=0",
        "Pragma": "no-cache", "Expires": "0",
        "Content-Type": "image/gif",
        "Content-Length": str(len(_PIXEL_GIF_BYTES)),
    }
    return Response(content=_PIXEL_GIF_BYTES, media_type="image/gif",
                    headers=headers, status_code=200)


# ════════════════════════════════════════════════════════════════════════════
# /bt/c/{token}/{link_id} — تتبّع نقرة + إعادة توجيه
# ════════════════════════════════════════════════════════════════════════════

@router.get("/c/{token}/{link_id}", include_in_schema=False)
async def track_click(token: str, link_id: int, request: Request,
                       conn=Depends(get_db)) -> RedirectResponse:
    """يسجّل النقرة ثم 302 إلى الـURL الأصلي.

    لو الـtoken أو link_id غير صحيح → 302 إلى الصفحة الرئيسية (آمن).
    """
    fallback_url = "https://dealpulseksa.com"
    target_url = fallback_url

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # ابحث عن الـURL الأصلي
            cur.execute(
                "SELECT id, original_url, broadcast_id, broadcast_kind "
                "FROM broadcast_link_targets WHERE id = %s",
                (link_id,),
            )
            link_row = cur.fetchone()
            if link_row:
                target_url = link_row["original_url"] or fallback_url

            # سجّل النقرة (لو token موجود) — مع كشف البوتات
            if token and len(token) <= 64 and link_row:
                cur.execute(
                    "SELECT id, broadcast_kind FROM broadcast_recipients "
                    "WHERE tracking_token = %s LIMIT 1",
                    (token,),
                )
                rec = cur.fetchone()
                if rec and rec["broadcast_kind"] == link_row["broadcast_kind"]:
                    rid = rec["id"]
                    ip = _client_ip(request)
                    ip_h = _hash_ip(ip)
                    ua = (request.headers.get("user-agent") or "")[:300]
                    referer = (request.headers.get("referer") or "")[:500]
                    is_bot = _is_bot_user_agent(ua)

                    if is_bot:
                        # Telegram/WhatsApp/etc. preview bot — لا نحسبه كنقرة
                        # نُسجّل السطر بعلامة [BOT] للتشخيص فقط
                        cur.execute(
                            "INSERT INTO broadcast_link_clicks "
                            "(recipient_id, link_target_id, ip_hash, user_agent, referrer) "
                            "VALUES (%s,%s,%s,%s,%s)",
                            (rid, link_id, ip_h, f"[BOT] {ua}"[:300], referer),
                        )
                    else:
                        cur.execute(
                            "UPDATE broadcast_recipients "
                            "SET click_count = COALESCE(click_count,0) + 1, "
                            "    clicked_at  = COALESCE(clicked_at, NOW()), "
                            "    status      = CASE WHEN status IN ('sent','opened','queued','sending') "
                            "                       THEN 'clicked' ELSE status END "
                            "WHERE id = %s",
                            (rid,),
                        )
                        cur.execute(
                            "INSERT INTO broadcast_link_clicks "
                            "(recipient_id, link_target_id, ip_hash, user_agent, referrer) "
                            "VALUES (%s,%s,%s,%s,%s)",
                            (rid, link_id, ip_h, ua, referer),
                        )
                    conn.commit()
    except Exception as exc:
        _log.warning("click tracking failed for %s/%s: %s",
                     token[:8] if token else "-", link_id, str(exc)[:200])
        try: conn.rollback()
        except Exception: pass

    # 302 إلى الـURL الأصلي (أو fallback لو غير موجود)
    return RedirectResponse(url=target_url, status_code=302)
