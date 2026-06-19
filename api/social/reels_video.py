"""توليد رابط فيديو Reels من البوستر — مسارات متعدّدة بترتيب الموثوقية.

استراتيجية ثلاث طبقات:

1) `master.reels_video_url` يدوي → أعلى موثوقية، أفضل جودة (يرفعه المالك).
2) Cloudinary URL transform (image → mp4 ثابت لـ5 ثوان) → بدون أي تثبيت،
   يعمل على الخطة الحالية. النتيجة: فيديو يعرض البوستر الثابت — صالح لـIG
   تقنياً (≥3s) لكن ليس Reels حقيقي. مفيد كـbaseline حتى يجهز Ken Burns.
3) Ken Burns auto (imageio-ffmpeg) → يتطلّب dependency جديدة + Dockerfile.
   غير مُفعَّل افتراضياً — راجع `generate_kenburns_mp4()` للتفعيل اليدوي.

الـdispatcher يستدعي `resolve_reel_video_url()` التي تختار أعلى طبقة متاحة.
"""
from __future__ import annotations

import re


def cloudinary_static_mp4(poster_url: str | None, duration: int = 5) -> str | None:
    """يحوّل رابط Cloudinary لصورة → رابط mp4 يعرض الصورة لمدة `duration` ثانية.

    التحويل: استبدال الامتداد بـ.mp4 وإضافة `du_{duration}` بعد `/upload/`.
    Cloudinary يقبل هذا على معظم الخطط (transformation أساسي).

    Returns:
        رابط mp4 جاهز للنشر، أو None لو الرابط ليس Cloudinary.
    """
    if not poster_url or "/upload/" not in poster_url:
        return None
    if "res.cloudinary.com" not in poster_url:
        return None
    # 1) استبدل امتداد الصورة بـ.mp4
    new_url = re.sub(r"\.(jpg|jpeg|png|webp)(\?|$)", r".mp4\2",
                     poster_url, flags=re.IGNORECASE)
    # 2) أضف transform الـduration بعد /upload/
    transform = f"du_{int(duration)},q_auto,f_mp4"
    new_url = new_url.replace("/upload/", f"/upload/{transform}/", 1)
    return new_url


def generate_kenburns_mp4(*_args, **_kwargs) -> str | None:
    """مولّد Ken Burns حقيقي (zoom + pan) من البوستر — غير مُفعَّل افتراضياً.

    التفعيل يتطلّب:
      pip install imageio==2.* imageio-ffmpeg==0.*

    ثم استبدل الـbody بـالمنطق التالي (~50 سطر) ووصل النتيجة بـCloudinary:
      - حمّل البوستر كـnumpy array بـimageio.imread
      - أنشئ 150 frame (5s × 30fps) مع تكبير تدريجي 1.0→1.4 (Ken Burns)
      - اكتب MP4 بـimageio.mimsave(..., fps=30, codec='libx264')
      - ارفع إلى Cloudinary بـresource_type='video'
      - أرجع secure_url

    لا أُفعّلها الآن لتجنّب dependency hidden + تعديل Dockerfile دون موافقتك.
    """
    return None


def resolve_reel_video_url(store: dict) -> str | None:
    """يختار أعلى طبقة فيديو متاحة للمتجر. يُرجع None لو لا شي متاح
    (الـdispatcher يتخطّى نشر Reel ويكتفي بـFeed + Story)."""
    # 1) رابط يدوي من admin له الأولوية المطلقة
    manual = (store.get("reels_video_url") or "").strip()
    if manual:
        return manual

    # 2) Cloudinary static mp4 من البوستر (fallback آمن)
    poster = store.get("social_poster_url") or store.get("logo_url")
    auto = cloudinary_static_mp4(poster)
    if auto:
        return auto

    # 3) Ken Burns — معطّل افتراضياً
    return None
