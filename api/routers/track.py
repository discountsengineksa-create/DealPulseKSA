import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg2.extras import RealDictCursor

from api.db import get_db
from api.schemas.track import (
    TrackRequest, TrackResponse,
    CategoryViewRequest, CategoryViewResponse,
    SearchLogRequest, SearchLogResponse,
    CodeRequestRequest, CodeRequestResponse,
    ReportCodeRequest, ReportCodeResponse,
    StoryViewRequest, StoryViewResponse,
    SetLangRequest, SetLangResponse,
    VisitRequest, VisitResponse,
)
from api.utils.geo_extractor import extract as extract_geo
from api.utils.fraud_scoring import compute_quality_score
from api.utils.event_publisher import publish_event
from api.utils.code_reports import record_code_report
from api.utils.rate_limit import LIMIT_TRACK, limiter

# حدود مخصّصة لقنوات تسجيل خفيفة (search/request-code) — أقل من /track العام
# لمنع إغراق direct_search و unavailable_codes_requests من سكربتات.
LIMIT_TRACK_SEARCH       = "30/minute"
LIMIT_TRACK_REQUEST_CODE = "5/minute"
# بلاغ الكود لا يعمل: 3 بلاغات/دقيقة لكل IP — كافٍ للاستخدام الطبيعي،
# يقطع spam بدون تعطيل العميل الجاد. السحب التلقائي يحتاج 10 مبلّغين فريدين
# فلا يمكن لمستخدم واحد إجبار السحب.
LIMIT_TRACK_REPORT       = "3/minute"
# فتح ستوري: 60/دقيقة — طبيعي لجلسة تصفّح نشطة (يفتح/يغلق بسرعة).
LIMIT_TRACK_STORY_VIEW   = "60/minute"
# زيارة موقع: مرة واحدة لكل جلسة، لكن نسمح 20/دقيقة لكل IP (شبكات مشتركة/NAT).
LIMIT_TRACK_VISIT        = "20/minute"

_log = logging.getLogger("dp.track")
router = APIRouter(prefix="/track", tags=["tracking"])

# عتبة جودة الحدث — لا نُحدّث عدادات master لو الجودة أقل من هذا الحد
# (يمنع bots من تضخيم الأرقام الظاهرة في الواجهة).
QUALITY_THRESHOLD_FOR_COUNTERS = 50


@router.post("", response_model=TrackResponse, status_code=201)
@limiter.limit(LIMIT_TRACK)
def track_action(payload: TrackRequest, request: Request, conn=Depends(get_db)):
    """
    تسجيل حركة مستخدم (نقر رابط / نسخ كوبون / بحث) من أي مصدر.

    خطوات التنفيذ:
      1. إثراء الحدث من الـ Cloudflare Worker (x-dp-* headers): country,
         city, ASN, ip_hash, bot_score...
      2. حساب quality_score من 0..100 (anti-fraud heuristics).
      3. التحقق من وجود المتجر.
      4. INSERT idempotent في action_logs (ON CONFLICT (event_id) DO NOTHING).
      5. تحديث عدادات master فقط لو الحدث عالي الجودة (quality >= 50).
      6. تحديث web_users لو من الموقع وعالي الجودة.
      7. XADD إلى Redis Stream events:raw (best-effort).

    لو حقول الـ Geo فاضية (Worker لم يصل بعد أو طلب من curl محلي)، الكود
    يكمل بقيم NULL — quality_score يتراجع 5 نقاط فقط.
    """
    # 1) إثراء + score
    geo = extract_geo(request)
    quality, is_dc, is_proxy = compute_quality_score(geo)
    event_id = payload.event_id or geo.event_id

    # 1.5) Anti-abuse: throttle نسخ كوبونات لمسجّلي الموقع — حد 30 ثانية
    #     يحمي من scraping للأكواد بعد التسجيل. لا يطبق على البوت/الميني-ويب.
    if (payload.action == "copy_coupon"
            and payload.source == "web"
            and payload.user_id):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXTRACT(EPOCH FROM (NOW() - last_copy_at))::int AS seconds_ago
                FROM web_users WHERE id = %s
                """,
                (payload.user_id,),
            )
            row = cur.fetchone()
            if row and row[0] is not None and row[0] < 30:
                wait = 30 - int(row[0])
                raise HTTPException(
                    status_code=429,
                    detail=f"الرجاء الانتظار {wait} ثانية قبل نسخ كوبون جديد",
                )

    # 2) التحقق من وجود المتجر
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM master WHERE store_id = %s", (payload.store_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail=f"store '{payload.store_id}' not found")

    # 3) Idempotent INSERT في action_logs
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO action_logs (
                user_id, store_id, action_type, details, source,
                event_id, ip_hash, user_agent_hash,
                country_code, region_code, city, postal_code,
                lat, lng, isp, asn,
                is_datacenter, is_proxy, device_class,
                cf_bot_score, quality_score, story_view_id, visitor_id
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s::uuid, decode(%s, 'hex'), decode(%s, 'hex'),
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s::uuid, %s::uuid
            )
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
                payload.user_id, payload.store_id, payload.action, payload.details, payload.source,
                event_id, geo.ip_hash, geo.ua_hash,
                geo.country_code, geo.region_code, geo.city, geo.postal_code,
                geo.lat, geo.lng, geo.isp, geo.asn,
                is_dc, is_proxy, geo.device_class,
                geo.cf_bot_score, quality, payload.story_view_id, payload.visitor_id,
            ),
        )

        # 4) تحديث عدادات master — فقط للأحداث عالية الجودة
        if quality >= QUALITY_THRESHOLD_FOR_COUNTERS:
            cur.execute(
                """
                UPDATE master SET
                    total_coupon_copies = total_coupon_copies
                        + CASE WHEN %s = 'copy_coupon' THEN 1 ELSE 0 END,
                    total_link_clicks   = total_link_clicks
                        + CASE WHEN %s = 'click_link'  THEN 1 ELSE 0 END
                WHERE store_id = %s
                """,
                (payload.action, payload.action, payload.store_id),
            )

            # 5) العدادات الشخصية لمستخدمي الموقع المسجّلين
            if payload.source == "web" and payload.user_id:
                if payload.action == "click_link":
                    cur.execute(
                        "UPDATE web_users SET visited_clicks = visited_clicks + 1, last_seen = NOW() WHERE id = %s",
                        (payload.user_id,),
                    )
                elif payload.action == "copy_coupon":
                    cur.execute(
                        """
                        UPDATE web_users
                        SET store_copy_count = store_copy_count + 1,
                            copied_coupons_history = array_append(copied_coupons_history, %s),
                            last_copy_at = NOW(),
                            last_seen = NOW()
                        WHERE id = %s
                        """,
                        (payload.store_id, payload.user_id),
                    )
        else:
            _log.info("Low-quality event quarantined: store=%s action=%s quality=%d asn=%s",
                      payload.store_id, payload.action, quality, geo.asn)

    # 6) Best-effort fan-out إلى Redis Stream (consumers يفعلون التجميع + التنبيهات)
    publish_event("events:raw", {
        "event_id": event_id,
        "store_id": payload.store_id,
        "action": payload.action,
        "source": payload.source,
        "user_id": payload.user_id,
        "country": geo.country_code,
        "city": geo.city,
        "quality": quality,
        "is_datacenter": is_dc,
        "is_proxy": is_proxy,
    })

    return TrackResponse(
        ok=True, action=payload.action,
        store_id=payload.store_id, source=payload.source,
    )


@router.post("/category-view", response_model=CategoryViewResponse, status_code=201)
@limiter.limit("60/minute")
def log_category_view(payload: CategoryViewRequest, request: Request, conn=Depends(get_db)):
    """تسجيل اهتمام صريح بقسم (view_tag) — بلا متجر.

    يوحّد عُرف البوت: action_logs(action_type='view_tag', details='tag:<اسم>',
    store_id=NULL). هذا هو مصدر «نقاط القسم» الحقيقي في لوحة تحليل الأقسام
    (نية صريحة، بدل وراثة كل تفاعل متجر موسوم بالقسم). لا تحديث لعدّادات master.
    """
    tag = payload.tag.strip()
    if not tag:
        raise HTTPException(status_code=400, detail="tag cannot be empty")

    geo = extract_geo(request)
    quality, is_dc, is_proxy = compute_quality_score(geo)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO action_logs (
                user_id, store_id, action_type, details, source,
                event_id, ip_hash, user_agent_hash,
                country_code, region_code, city, postal_code,
                lat, lng, isp, asn,
                is_datacenter, is_proxy, device_class,
                cf_bot_score, quality_score, visitor_id
            )
            VALUES (
                %s, NULL, 'view_tag', %s, %s,
                %s::uuid, decode(%s, 'hex'), decode(%s, 'hex'),
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s::uuid
            )
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
                payload.user_id, f"tag:{tag}", payload.source,
                geo.event_id, geo.ip_hash, geo.ua_hash,
                geo.country_code, geo.region_code, geo.city, geo.postal_code,
                geo.lat, geo.lng, geo.isp, geo.asn,
                is_dc, is_proxy, geo.device_class,
                geo.cf_bot_score, quality, payload.visitor_id,
            ),
        )
    return CategoryViewResponse(ok=True, tag=tag)


_PLATFORM_TO_SOURCE = {
    "Web": "web",
    "Bot": "bot",
    "Dashboard": "dashboard",
    "Miniapp": "telegram_miniapp",
}


@router.post("/search", response_model=SearchLogResponse, status_code=201)
@limiter.limit(LIMIT_TRACK_SEARCH)
def log_search(payload: SearchLogRequest, request: Request, conn=Depends(get_db)):
    """
    تسجيل كلمة بحث — كتابتان atomic في DB:
      1. direct_search: للوحة القرار + تحليل فجوات الكلمات (دائماً).
      2. action_logs (action_type='search'): لـ«مين نسخ من متجر» — فقط
         إذا في store_id مطابق (لأن «مين نسخ» يجمع بـ store_id).
    هذا يطابق سلوك البوت (log_search + log_action) فيوحّد المخرَجات بين
    التبويبات بغض النظر عن مصدر العميل (web / miniapp / bot).
    """
    with conn.cursor() as cur:
        # (1) direct_search — لكل بحث (مع/بدون match) لتحليل الفجوات
        cur.execute(
            """
            INSERT INTO direct_search
                (search_keyword, store_id, user_found, platform, name_en, user_id, user_email)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                payload.keyword, payload.store_id, payload.user_found,
                payload.platform, payload.name_en,
                payload.user_id, payload.user_email,
            ),
        )

        # (2) action_logs — فقط إذا في store_id (مرآة لـ log_action في البوت)
        if payload.store_id:
            geo = extract_geo(request)
            quality, is_dc, is_proxy = compute_quality_score(geo)
            source = _PLATFORM_TO_SOURCE.get(payload.platform, "web")
            cur.execute(
                """
                INSERT INTO action_logs (
                    user_id, store_id, action_type, details, source,
                    event_id, ip_hash, user_agent_hash,
                    country_code, region_code, city, postal_code,
                    lat, lng, isp, asn,
                    is_datacenter, is_proxy, device_class,
                    cf_bot_score, quality_score, visitor_id
                )
                VALUES (
                    %s, %s, 'search', %s, %s,
                    %s::uuid, decode(%s, 'hex'), decode(%s, 'hex'),
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s::uuid
                )
                ON CONFLICT (event_id) DO NOTHING
                """,
                (
                    payload.user_id, payload.store_id,
                    f"keyword:{payload.keyword};found:{payload.user_found}",
                    source,
                    geo.event_id, geo.ip_hash, geo.ua_hash,
                    geo.country_code, geo.region_code, geo.city, geo.postal_code,
                    geo.lat, geo.lng, geo.isp, geo.asn,
                    is_dc, is_proxy, geo.device_class,
                    geo.cf_bot_score, quality, payload.visitor_id,
                ),
            )
    return SearchLogResponse(ok=True, keyword=payload.keyword)


@router.post("/request-code", response_model=CodeRequestResponse, status_code=201)
@limiter.limit(LIMIT_TRACK_REQUEST_CODE)
def request_code(payload: CodeRequestRequest, request: Request, conn=Depends(get_db)):
    """
    تسجيل طلب عميل لتوفير كود متجر غير موجود حالياً.

    يستقبل من:
      - الموقع: brand_name + user_email (مطلوب للتواصل لاحقاً)
      - البوت:  brand_name + user_id (telegram_id)
      - يمكن إرسال كلاهما معاً لو متوفر
    """
    brand = payload.brand_name.strip()
    if not brand:
        raise HTTPException(status_code=400, detail="brand_name cannot be empty")

    email = (payload.user_email or "").strip() or None
    if not email and not payload.user_id:
        raise HTTPException(
            status_code=400,
            detail="either user_email (web) or user_id (bot) must be provided",
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO unavailable_codes_requests
                (brand_name, user_email, user_id, requested_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING id
            """,
            (brand, email, payload.user_id),
        )
        new_id = cur.fetchone()[0]

    return CodeRequestResponse(ok=True, request_id=new_id, brand_name=brand)


# ════════════════════════════════════════════════════════════════════════════
# بلاغ «الكود لا يعمل» — يستدعي helper مشترك (api/utils/code_reports.py)
# ════════════════════════════════════════════════════════════════════════════
@router.post("/report-code-issue", response_model=ReportCodeResponse, status_code=201)
@limiter.limit(LIMIT_TRACK_REPORT)
def report_code_issue(payload: ReportCodeRequest, request: Request, conn=Depends(get_db)):
    """بلاغ من عميل مسجّل بأن كود متجر لا يعمل.

    التطبيق الفعلي (insert + auto-suspend + alerts) في
    api/utils/code_reports.py — يستدعيه البوت أيضاً مباشرة بدون HTTP.
    """
    if payload.source == "web" and not payload.web_user_id:
        raise HTTPException(400, "web_user_id is required for source='web'")
    if payload.source in ("telegram_miniapp", "bot") and not payload.tg_user_id:
        raise HTTPException(400, f"tg_user_id is required for source='{payload.source}'")

    geo = extract_geo(request)
    try:
        result = record_code_report(
            conn,
            store_id=payload.store_id, source=payload.source,
            web_user_id=payload.web_user_id, tg_user_id=payload.tg_user_id,
            issue_note=payload.issue_note,
            ip_hash=geo.ip_hash, ua_hash=geo.ua_hash,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    return ReportCodeResponse(
        ok=True, report_id=result["report_id"], auto_suspended=result["auto_suspended"],
    )


# ════════════════════════════════════════════════════════════════════════════
# تسجيل فتحة ستوري (Migration 029)
# ════════════════════════════════════════════════════════════════════════════
@router.post("/story-view", response_model=StoryViewResponse, status_code=201)
@limiter.limit(LIMIT_TRACK_STORY_VIEW)
def log_story_view(payload: StoryViewRequest, request: Request, conn=Depends(get_db)):
    """تسجيل فتحة ستوري لمسجّل فقط. لا يُسجَّل الزوار.

    العميل يولّد view_id (UUID v4) ثم يُمرّره مع كل نسخ/زيارة لاحقاً عبر
    /track.story_view_id لربط الـ engagement بنفس الفتحة.
    """
    if payload.source == "web" and not payload.web_user_id:
        raise HTTPException(400, "web_user_id is required for source='web'")
    if payload.source == "telegram_miniapp" and not payload.tg_user_id:
        raise HTTPException(400, "tg_user_id is required for source='telegram_miniapp'")

    geo = extract_geo(request)
    with conn.cursor() as cur:
        # was_promoted: snapshot لـ master.is_promoted لحظة الفتح.
        # BOOL_OR + COALESCE للتعامل مع master.store_id غير الفريد.
        cur.execute(
            """
            SELECT BOOL_OR(COALESCE(is_promoted, FALSE)) AS was_promoted
              FROM master
             WHERE store_id = %s
            """,
            (payload.store_id,),
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            # BOOL_OR على مجموعة فارغة يُرجع NULL → ما في متجر بهذا الـ id
            raise HTTPException(404, f"store '{payload.store_id}' not found")
        was_promoted = bool(row[0])

        # was_trending: snapshot للمتجر كـ«ترند» وقت فتح الستوري — يعتمد على
        # تثبيت الأدمن اليدوي (master.is_trending='ترند 🔥') فقط، ليطابق توقّع
        # المالك: «ما حطيته ترند يدوياً → ما يُحسب ستوري ترند». الخوارزمية
        # (compute_trending_store_ids) ترفع متاجر عادية لـtop-3/7 في كتالوج
        # صغير فتلوّث bucket «ستوري ترند» بمتاجر غير مقصودة.
        cur.execute(
            "SELECT BOOL_OR(is_trending = 'ترند 🔥') FROM master WHERE store_id = %s",
            (payload.store_id,),
        )
        _row = cur.fetchone()
        was_trending = bool(_row[0]) if _row and _row[0] is not None else False

        cur.execute(
            """
            INSERT INTO story_views (
                view_id, store_id, source,
                web_user_id, tg_user_id,
                ip_hash, user_agent_hash,
                was_promoted, was_trending
            )
            VALUES (%s::uuid, %s, %s, %s, %s,
                    decode(%s, 'hex'), decode(%s, 'hex'),
                    %s, %s)
            ON CONFLICT (view_id) DO NOTHING
            """,
            (
                payload.view_id, payload.store_id, payload.source,
                payload.web_user_id, payload.tg_user_id,
                geo.ip_hash, geo.ua_hash,
                was_promoted, was_trending,
            ),
        )

    return StoryViewResponse(ok=True, view_id=payload.view_id)


# ════════════════════════════════════════════════════════════════════════════
# حفظ لغة المستخدم المفضّلة (آخر اختيار) — مصدر الحقيقة لإرسال المنشورات بلغته
# ════════════════════════════════════════════════════════════════════════════
@router.post("/set-lang", response_model=SetLangResponse, status_code=200)
@limiter.limit("20/minute")
def set_lang(payload: SetLangRequest, request: Request, conn=Depends(get_db)):
    """يحدّث اللغة المعتمدة:
      - web                  → web_users.lang  (WHERE id = user_id)
      - telegram_miniapp/bot → bot_users.lang  (WHERE telegram_id = tg_user_id)

    البوت يعرض اختيار اللغة مرة واحدة فقط، فالميني-ويب هو مكان تغييرها لاحقاً
    لمستخدم تيليجرام (نفس الشخص، نفس صف bot_users).
    """
    if payload.source == "web":
        if not payload.user_id:
            raise HTTPException(400, "user_id is required for source='web'")
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE web_users SET lang = %s WHERE id = %s",
                (payload.lang, payload.user_id),
            )
    else:  # telegram_miniapp / bot
        if not payload.tg_user_id:
            raise HTTPException(
                400, f"tg_user_id is required for source='{payload.source}'")
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE bot_users SET lang = %s WHERE telegram_id = %s",
                (payload.lang, payload.tg_user_id),
            )

    return SetLangResponse(ok=True, lang=payload.lang, source=payload.source)


# ════════════════════════════════════════════════════════════════════════════
# تسجيل زيارة موقع على مستوى الجلسة (Migration 060) — «نبض الزوّار»
# ════════════════════════════════════════════════════════════════════════════
from urllib.parse import urlparse  # noqa: E402 (محلي بالـendpoint — لا يستخدمه غيره)

# تصنيف مصدر الإحالة بحدّ النقطة (label-aware) لتفادي مطابقات substring الخاطئة
# (مثل "x.com" داخل "wix.com"). نطابق على وسم نطاق كامل أو نطاق قصير معروف.
_SEARCH_LABELS = {"google", "bing", "yahoo", "duckduckgo", "yandex", "baidu"}
_SOCIAL_LABELS = {
    "instagram", "facebook", "fb", "twitter", "tiktok", "youtube", "youtu",
    "snapchat", "threads", "linkedin", "pinterest", "reddit", "whatsapp", "telegram",
}
# نطاقات قصيرة (وسمها الأول ليس اسم البراند) — تُطابق كنطاق كامل.
_SOCIAL_FULL = {"x.com", "t.co", "t.me", "fb.com", "youtu.be", "lnkd.in"}


def _strip_www(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def _classify_referrer(referrer: str | None, site_host: str | None) -> tuple[str, str | None]:
    """يُرجع (kind, host) من الإحالة الخام.

    kind: 'direct' (بلا إحالة) · 'internal' (تنقّل داخل الموقع) ·
          'search' (محرّك بحث) · 'social' (منصة تواصل) · 'referral' (موقع آخر).
    """
    if not referrer:
        return "direct", None
    try:
        host = _strip_www((urlparse(referrer).hostname or "").lower())
    except Exception:
        host = ""
    if not host:
        return "direct", None
    if site_host and (host == site_host or host.endswith("." + site_host)):
        return "internal", host
    # وسوم النطاق (l.instagram.com → {l, instagram, com}) للمطابقة على حدّ نقطة
    labels = set(host.split("."))
    if host in _SOCIAL_FULL or labels & _SOCIAL_LABELS:
        return "social", host
    if labels & _SEARCH_LABELS:
        return "search", host
    return "referral", host


@router.post("/visit", response_model=VisitResponse, status_code=201)
@limiter.limit(LIMIT_TRACK_VISIT)
def log_visit(payload: VisitRequest, request: Request, conn=Depends(get_db)):
    """تسجيل زيارة موقع — صف واحد لكل جلسة في web_visits.

    على عكس action_logs (حدث صريح لكل نقر/نسخ)، هذا يلتقط مجرد المرور بالموقع
    حتى لو لم يتفاعل الزائر إطلاقاً — يسدّ الفجوة التي كانت تُخفي الزوّار عن
    الداشبورد. الإثراء الجغرافي + الجودة من نفس مسار action_logs، و visit_id
    الفريد يجعل الـ ping idempotent (إعادة الإرسال لا تُكرّر الصف).
    """
    geo = extract_geo(request)
    quality, is_dc, _is_proxy = compute_quality_score(geo)

    site_host = _strip_www((urlparse(str(request.headers.get("origin") or "")).hostname or "").lower())
    ref_kind, ref_host = _classify_referrer(payload.referrer, site_host or None)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO web_visits (
                visit_id, visitor_id, user_id, source,
                referrer_kind, referrer_host, landing_path,
                ip_hash, user_agent_hash,
                country_code, region_code, city, device_class, asn,
                is_datacenter, cf_bot_score, quality_score
            )
            VALUES (
                %s::uuid, %s::uuid, %s, %s,
                %s, %s, %s,
                decode(%s, 'hex'), decode(%s, 'hex'),
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (visit_id) DO NOTHING
            """,
            (
                payload.visit_id, payload.visitor_id, payload.user_id, payload.source,
                ref_kind, ref_host, payload.landing_path,
                geo.ip_hash, geo.ua_hash,
                geo.country_code, geo.region_code, geo.city, geo.device_class, geo.asn,
                is_dc, geo.cf_bot_score, quality,
            ),
        )

    return VisitResponse(ok=True, visit_id=payload.visit_id)
