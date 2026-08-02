"""
Dispatcher: يجلب المتجر من DB، يبني نص المنشور، ويوزّعه على كل poster مُسجَّل.
يُنفَّذ كـ FastAPI BackgroundTask — خارج سياق request — لذا يفتح اتصال مستقلاً.
"""
from __future__ import annotations

import os
import traceback

from psycopg2.extras import RealDictCursor

from api.db import get_pool
from api.social.base import BaseSocialPoster, NotConfiguredError, PostResult
from api.social.ig_slides import upload_howto_slide
from api.social.image_specs import platform_image_url
from api.social.platforms import REGISTERED_POSTERS
from api.social.platforms.instagram import InstagramPoster
from api.social.reels_batch import run_pending_batches
from api.social.template import build_post_text

# المنصات الاجتماعية القابلة للتحكّم من نموذج الماستر (publish_channels).
# يجب أن تطابق مفاتيح PUBLISH_CHANNELS الاجتماعية في dashboard.py.
# منصة مُدارة غير معلَّمة لمتجر = لا تُنشَر له. المنصات غير المُدارة
# (x/pinterest/linkedin) تُنشَر حسب التهيئة كالمعتاد (لا تُسقَط).
_MANAGED_SOCIAL = {"telegram", "discord", "instagram", "threads", "facebook"}

# كاروسيل الفيد التلقائي على إنستقرام.
# تاريخ القرار: عُطِّل 2026-07-15 لأن insights قاست وصول بوسترات الفيد 1.1
# (١٣ منشور بوصول صفر) مقابل 45 للريلز. **أُعيد تفعيله 2026-08-02 بقرار
# المالك**: البوستر لكل متجر جزء من هوية الحساب ومرجع بصري للكود، وغيابه
# لمتجرين جديدين (عبدالصمد القرشي وشفق الشرق) هو ما كشف التعطيل.
# الريل الجماعي يبقى يعمل كما هو — الاثنان لا يتعارضان.
# للتعطيل مجدداً: IG_AUTO_FEED_ENABLED=0 في البيئة (لا يحتاج تعديل كود).
IG_AUTO_FEED_ENABLED = os.getenv("IG_AUTO_FEED_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}


def _fetch_store(conn, master_id: int) -> dict | None:
    """يجلب بيانات المتجر. reels_video_url اختياري — لو عمود غير موجود في
    البيئة (migration_058 لم يُطبَّق بعد) نستعمل to_jsonb للحماية من خطأ ServerError.

    الـCOALESCE(... ->> 'reels_video_url', NULL) آمن: يُرجع NULL إن لم يوجد المفتاح،
    ويُرجع القيمة لو وُجد. هذا يحفظ التوافق الإنتاجي قبل تطبيق الـmigration."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, store_id, name_en, public_coupon,
                   discount_value, extra_offer, extra_offer_en,
                   description, store_bio, store_tags,
                   affiliate_link, logo_url, social_poster_url,
                   publish_channels,
                   (to_jsonb(master) ->> 'reels_video_url') AS reels_video_url
            FROM master
            WHERE id = %s
            """,
            (master_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def _insert_log(
    conn,
    master_id: int,
    store_id: str,
    platform: str,
    post_text: str,
    image_url: str | None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO social_posts_log
                (master_id, store_id, platform, post_text, image_url, status)
            VALUES (%s, %s, %s, %s, %s, 'queued')
            RETURNING id
            """,
            (master_id, store_id, platform, post_text, image_url),
        )
        return cur.fetchone()[0]


def _update_log(
    conn,
    log_id: int,
    status: str,
    platform_post_id: str | None = None,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE social_posts_log
            SET status = %s,
                platform_post_id = %s,
                error_message = %s,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (status, platform_post_id, error_message, log_id),
        )


def _run_one_poster(
    conn,
    master_id: int,
    store: dict,
    post_text: str,
    image_url: str | None,
    poster: BaseSocialPoster,
) -> None:
    """ينفّذ poster واحد، يسجّل النتيجة، يلتقط الاستثناءات بأمان."""
    log_id = _insert_log(
        conn,
        master_id=master_id,
        store_id=store["store_id"],
        platform=poster.name,
        post_text=post_text,
        image_url=image_url,
    )
    conn.commit()

    if not poster.is_configured():
        _update_log(conn, log_id, status="skipped", error_message="not configured")
        conn.commit()
        return

    try:
        result: PostResult = poster.post(post_text, image_url)
        if result.error:
            _update_log(conn, log_id, status="failed", error_message=result.error)
        else:
            _update_log(
                conn,
                log_id,
                status="sent",
                platform_post_id=result.platform_post_id,
            )
    except NotConfiguredError as e:
        _update_log(conn, log_id, status="skipped", error_message=str(e))
    except Exception as e:
        _update_log(
            conn,
            log_id,
            status="failed",
            error_message=f"{type(e).__name__}: {e}",
        )
        print(f"[social] {poster.name} crashed: {traceback.format_exc()}")
    finally:
        conn.commit()


def _run_instagram_extended(
    conn,
    master_id: int,
    store: dict,
    post_text: str,
    base_image: str | None,
    image_url: str | None,
    poster: InstagramPoster,
) -> None:
    """
    إنستقرام: المسار الافتراضي الآن Reels-only (قرار 2026-07-15).

    1) Feed Carousel — معطّل افتراضياً (IG_AUTO_FEED_ENABLED=1 لإعادته):
       بوستر (Slide 1) + بطاقة «كيف تستخدم الكود؟» (Slide 2). قِيس من
       insights أن وصوله الفعلي ~1 على حساب تحت 100 متابع فيكبح التوزيع.
    2) Reel جماعي (تلقائي بعد كل بث ناجح — المسار الأساسي): كل ٦ بثّات = ريل.

    ملاحظة: الستوري التلقائية أُلغيت بقرار المالك (٢٠٢٦-٠٦-١٩) —
    الستوري تُنشَر يدوياً من تطبيق إنستقرام. الكود محذوف لا معطّل.
    """
    if not poster.is_configured():
        return  # حساب غير مهيّأ — لا فيد ولا ريل

    # ── 1) كاروسيل الفيد التلقائي — معطّل افتراضياً (IG_AUTO_FEED_ENABLED) ──
    #   يُتخطّى كلياً في الوضع الافتراضي (Reels-only). لا نُدرج صف Feed في
    #   social_posts_log ولا نبني شرائح ولا ننشر — كل بثّة تُغذّي قائمة الريل فقط.
    if IG_AUTO_FEED_ENABLED:
        # سجّل صف Feed مسبقاً (للحالات اللي تطلع failed قبل النشر)
        log_id = _insert_log(
            conn, master_id=master_id, store_id=store["store_id"],
            platform=poster.name, post_text=post_text, image_url=image_url,
        )
        conn.commit()

        # ابنِ قائمة شرائح الكاروسيل
        slides: list[str] = []
        if image_url:
            slides.append(image_url)

        # شريحة «كيف تستخدم» — مولَّدة فقط لو Cloudinary مهيّأ.
        try:
            howto_url = upload_howto_slide(
                store_id=str(store.get("store_id") or ""),
                store_name=str(store.get("store_id") or ""),
                coupon=(store.get("public_coupon") or None),
            )
        except Exception as e:
            howto_url = None
            print(f"[social] ig howto slide failed: {e}")
        if howto_url:
            slides.append(howto_url)

        # انشر Feed (Carousel لو ≥2 شريحة، single لو 1)
        try:
            if len(slides) >= 2:
                result = poster.post_carousel(post_text, slides)
            else:
                result = poster.post(post_text, slides[0] if slides else None)

            if result.error:
                _update_log(conn, log_id, status="failed", error_message=result.error)
                conn.commit()
                return  # الفيد فشل — لا نكمل للريل في نفس المسار
            feed_post_id = result.platform_post_id or ""
            _update_log(conn, log_id, status="sent", platform_post_id=feed_post_id)
            conn.commit()
        except NotConfiguredError as e:
            _update_log(conn, log_id, status="skipped", error_message=str(e))
            conn.commit()
            return
        except Exception as e:
            _update_log(conn, log_id, status="failed",
                        error_message=f"{type(e).__name__}: {e}")
            conn.commit()
            print(f"[social] instagram feed crashed: {traceback.format_exc()}")
            return

    # ── 2) Batch Reel — كل بث ناجح يضيف هذا المتجر لقائمة انتظار الريل،
    #    ولما توصل ٦+ متاجر منتظرين → ينتج Reel متعدّد (٦ متاجر × ٥ ثوان).
    #
    #    إعادة `last_reeled_at = NULL` للمتجر الحالي تضمن إن «كل ٦ بثّات
    #    = ريل تلقائي» يشتغل دائماً، حتى لو المتجر سبق ودخل ريلاً قبل سنة.
    #    التحديث/إعادة البث على نفس المتجر = إشارة «الكوبون تجدّد، يستاهل
    #    يدخل ريل جديد».
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE master SET last_reeled_at = NULL WHERE id = %s",
                (master_id,),
            )
        conn.commit()
    except Exception as e:
        # فشل الإعادة لا يجب أن يُلغي البث الناجح — نلوغ ونمشي
        conn.rollback()
        print(f"[social] reset last_reeled_at failed for {master_id}: {e}")
    try:
        produced = run_pending_batches(conn)
        if produced:
            print(f"[social] reels_batch produced {produced} reel(s)")
    except Exception as e:
        # فشل الـbatch لا يجب أن يُلغي نجاح الـFeed — نلوغ ونمشي
        print(f"[social] reels_batch crashed: {type(e).__name__}: {e}")


def post_instagram_feed_only(master_id: int) -> dict:
    """ينشر **بوستر الفيد على إنستقرام فقط** لمتجر واحد — بلا لمس بقية المنصات.

    الحاجة: متجر بُثّ أثناء فترة تعطيل الفيد (2026-07-15 ← 2026-08-02) فخرج بلا
    بوستر. إعادة البث الكامل تُكرّر المنشور على تيليجرام وديسكورد وفيسبوك بلا
    داعٍ، فهذا المسار يعالج الفجوة بدقّة. لا يمسّ `last_reeled_at` فلا يُخلّ
    بقائمة انتظار الريل.
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        store = _fetch_store(conn, master_id)
        if not store:
            return {"ok": False, "error": "store not found"}

        raw_channels = store.get("publish_channels")
        allowed = None if raw_channels is None else {
            c.strip() for c in str(raw_channels).split(",") if c.strip()
        }
        if allowed is not None and "instagram" not in allowed:
            return {"ok": False, "error": "instagram not enabled for this store"}

        poster = InstagramPoster()
        if not poster.is_configured():
            return {"ok": False, "error": "instagram not configured"}

        base_image = store.get("social_poster_url") or store.get("logo_url")
        if not base_image:
            return {"ok": False, "error": "no poster or logo image"}
        post_text = build_post_text(store, platform=poster.name)
        image_url = platform_image_url(base_image, poster.name)

        log_id = _insert_log(
            conn, master_id=master_id, store_id=store["store_id"],
            platform=poster.name, post_text=post_text, image_url=image_url,
        )
        conn.commit()

        slides: list[str] = [image_url] if image_url else []
        try:
            howto_url = upload_howto_slide(
                store_id=str(store.get("store_id") or ""),
                store_name=str(store.get("store_id") or ""),
                coupon=(store.get("public_coupon") or None),
            )
            if howto_url:
                slides.append(howto_url)
        except Exception as e:
            print(f"[social] ig howto slide failed: {e}")

        try:
            result = (poster.post_carousel(post_text, slides) if len(slides) >= 2
                      else poster.post(post_text, slides[0] if slides else None))
        except Exception as e:
            _update_log(conn, log_id, status="failed",
                        error_message=f"{type(e).__name__}: {e}")
            conn.commit()
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

        if result.error:
            _update_log(conn, log_id, status="failed", error_message=result.error)
            conn.commit()
            return {"ok": False, "error": result.error}

        _update_log(conn, log_id, status="sent",
                    platform_post_id=result.platform_post_id or "")
        conn.commit()

        # قاعدة المالك: كل بوستر يُحسب ضمن «آخر ٦»، وعند السادس ينزل ريل يجمعهم.
        # لذلك حتى النشر المباشر يعيد المتجر لقائمة الانتظار ويشغّل الدفعة —
        # وإلا خرج بوستر لا يُحسب في العدّ فاختلّ إيقاع الريل.
        produced = 0
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE master SET last_reeled_at = NULL WHERE id = %s",
                            (master_id,))
            conn.commit()
            produced = run_pending_batches(conn) or 0
        except Exception as e:
            conn.rollback()
            print(f"[social] ig-feed reel queue failed for {master_id}: {e}")
        return {"ok": True, "post_id": result.platform_post_id,
                "slides": len(slides), "reels_produced": produced}
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        pool.putconn(conn)


def broadcast_to_all_platforms(master_id: int) -> None:
    """
    نقطة دخول الـ BackgroundTask.
    تجلب المتجر، تبني النص، توزّع على كل المنصات، تسجّل النتائج.
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        store = _fetch_store(conn, master_id)
        if not store:
            print(f"[social] master_id={master_id} not found — skip broadcast.")
            return

        # نفضّل البوستر بالثيم (مقاس 1080×1080 مع كل بيانات العرض)
        # ونرجع للوقو فقط لو ما تم توليد بوستر بعد.
        base_image = store.get("social_poster_url") or store.get("logo_url")

        # قنوات النشر لكل متجر: NULL = كل القنوات (توافق المتاجر القديمة).
        raw_channels = store.get("publish_channels")
        allowed = None if raw_channels is None else {
            c.strip() for c in str(raw_channels).split(",") if c.strip()
        }

        for poster_cls in REGISTERED_POSTERS:
            try:
                poster = poster_cls()
            except Exception as e:
                print(f"[social] failed to instantiate {poster_cls.__name__}: {e}")
                continue
            # منصة مُدارة وغير معلَّمة لهذا المتجر → تخطّاها (تحكّم القناة).
            if (allowed is not None and poster.name in _MANAGED_SOCIAL
                    and poster.name not in allowed):
                continue
            # نص الـcaption مُخصَّص لكل منصة: إنستقرام له شكل مختلف يخدم
            # خوارزميته (hook + CTA بايو + بنك هاشتاقات SEO). باقي المنصات
            # تستخدم النسخة العامة (الروابط فيها نشطة).
            post_text = build_post_text(store, platform=poster.name)
            image_url = platform_image_url(base_image, poster.name)  # مقاس كل منصة

            # ── إنستقرام مسار خاص: Carousel + Story تلقائياً ───────────
            if isinstance(poster, InstagramPoster):
                _run_instagram_extended(conn, master_id, store, post_text,
                                         base_image, image_url, poster)
                continue

            _run_one_poster(conn, master_id, store, post_text, image_url, poster)
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        pool.putconn(conn)
