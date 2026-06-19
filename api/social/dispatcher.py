"""
Dispatcher: يجلب المتجر من DB، يبني نص المنشور، ويوزّعه على كل poster مُسجَّل.
يُنفَّذ كـ FastAPI BackgroundTask — خارج سياق request — لذا يفتح اتصال مستقلاً.
"""
from __future__ import annotations

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
    إنستقرام: مسار موسَّع يستفيد من فورمات المنصة لزيادة الوصول والـengagement.

    1) Feed Carousel (شريحتان):
       - Slide 1: البوستر بالثيم (social_poster_url) — الـhero
       - Slide 2: بطاقة «كيف تستخدم الكود؟» مولَّدة بـPIL، تُرفع لـCloudinary
                   وتُخزَّن بـpublic_id ثابت (إعادة البث = نفس الرابط)
       لو فشلت الشريحة الثانية → نسقط على single-image (لا نُسقط المنشور كاملاً)
    2) Story:
       - بعد نجاح Feed، ننشر نفس البوستر كـStory (24h انكشاف إضافي + ~2-3x وصول)
       - يُسجَّل في social_posts_log بـplatform='instagram_story'
    """
    # سجّل صف Feed مسبقاً (للحالات اللي تطلع failed قبل النشر)
    log_id = _insert_log(
        conn, master_id=master_id, store_id=store["store_id"],
        platform=poster.name, post_text=post_text, image_url=image_url,
    )
    conn.commit()

    if not poster.is_configured():
        _update_log(conn, log_id, status="skipped", error_message="not configured")
        conn.commit()
        return

    # ── 1) ابنِ قائمة شرائح الكاروسيل ─────────────────────────────
    slides: list[str] = []
    if image_url:
        slides.append(image_url)

    # شريحة «كيف تستخدم» — مولَّدة فقط لو Cloudinary مهيّأ.
    # نُرسل اسم المتجر والكود؛ الدالة تُرجع None لو شي فشل بدلاً من رفع استثناء.
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

    # ── 2) انشر Feed (Carousel لو ≥2 شريحة، single لو 1) ──────────
    try:
        if len(slides) >= 2:
            result = poster.post_carousel(post_text, slides)
        else:
            result = poster.post(post_text, slides[0] if slides else None)

        if result.error:
            _update_log(conn, log_id, status="failed", error_message=result.error)
            conn.commit()
            return  # لا نشر Story لو الـFeed فشل (نتجنّب story-only without context)

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

    # ── 3) Story (24h) — انكشاف إضافي بنفس البوستر ───────────────
    story_log_id = _insert_log(
        conn, master_id=master_id, store_id=store["store_id"],
        platform="instagram_story", post_text=post_text, image_url=image_url,
    )
    conn.commit()
    try:
        # Story لا تقبل caption — نمرّر البوستر الأصلي (mod-square كافٍ؛
        # Instagram يُكيّفه تلقائياً لـ9:16 بهامش).
        story_result = poster.post_story(image_url) if image_url else PostResult(
            error="no image for story"
        )
        if story_result.error:
            _update_log(conn, story_log_id, status="failed",
                        error_message=story_result.error)
        else:
            _update_log(conn, story_log_id, status="sent",
                        platform_post_id=story_result.platform_post_id or "")
    except Exception as e:
        _update_log(conn, story_log_id, status="failed",
                    error_message=f"{type(e).__name__}: {e}")
        print(f"[social] instagram story crashed: {traceback.format_exc()}")
    finally:
        conn.commit()

    # ── 4) Batch Reel — بعد كل بث ناجح، افحص قائمة الانتظار:
    #    لو وصلنا 6+ متاجر منتظرين → ينتج Reel متعدّد (6 متاجر/5 ثوان لكل)،
    #    لو 12 منتظرين → 2 ريلز متتاليين، لو <6 → لا شي (ينتظر السادس بصبر).
    try:
        produced = run_pending_batches(conn)
        if produced:
            print(f"[social] reels_batch produced {produced} reel(s)")
    except Exception as e:
        # فشل الـbatch لا يجب أن يُلغي نجاح الـFeed/Story — نلوغ ونمشي
        print(f"[social] reels_batch crashed: {type(e).__name__}: {e}")


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
