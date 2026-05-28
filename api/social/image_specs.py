"""
مقاسات الصورة المثالية لكل منصة + باني روابط Cloudinary.

الفكرة: نخزّن نسخة أساسية واحدة عالية الدقة على Cloudinary، ثم نشتقّ منها مقاس
كل منصة بمجرّد إدراج مقطع تحويل في الرابط بعد '/upload/'. لا رفع نسخ متعددة ولا
تخزين إضافي. الشعار يُوسَّط بخلفية بيضاء (c_pad,b_white) ولا يُقص أبداً.
"""
from __future__ import annotations

# المفاتيح تطابق BaseSocialPoster.name لكل منصة بالضبط.
PLATFORM_IMAGE_SPECS: dict[str, dict[str, int]] = {
    "facebook":  {"w": 1200, "h": 630},   # عرضي
    "instagram": {"w": 1080, "h": 1080},  # مربّع
    "threads":   {"w": 1080, "h": 1080},  # مربّع
    "telegram":  {"w": 1280, "h": 1280},  # مربّع (قناة)
    "discord":   {"w": 1024, "h": 1024},  # مربّع (embed)
    "x":         {"w": 1200, "h": 675},   # عرضي
    "pinterest": {"w": 1000, "h": 1500},  # طولي 2:3
    "linkedin":  {"w": 1200, "h": 627},   # عرضي
}

DEFAULT_SPEC: dict[str, int] = {"w": 1080, "h": 1080}


def cloudinary_variant(
    base_url: str | None,
    w: int,
    h: int,
    crop: str = "pad",
    bg: str = "white",
    fmt: str = "webp",
    quality: str = "auto",
) -> str | None:
    """يُدرج تحويل المقاس في رابط Cloudinary. غير-Cloudinary يُعاد كما هو."""
    marker = "/upload/"
    if not base_url or marker not in base_url:
        return base_url
    transform = f"c_{crop},w_{w},h_{h},b_{bg},f_{fmt},q_{quality}"
    return base_url.replace(marker, f"{marker}{transform}/", 1)


def platform_image_url(base_url: str | None, platform: str) -> str | None:
    """يُعيد رابط الشعار بمقاس المنصة المطلوبة (أو المقاس الافتراضي المربّع)."""
    spec = PLATFORM_IMAGE_SPECS.get(platform, DEFAULT_SPEC)
    return cloudinary_variant(base_url, spec["w"], spec["h"])
