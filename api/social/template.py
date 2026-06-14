"""قالب موحّد لمنشورات السوشيال — صامت، بدون إيموجيز، كما حدّده المالك."""
from __future__ import annotations

import re

# هشتاق البراند الثابت يتصدّر كل منشور.
BRAND_HASHTAG = "#نبض_الصفقات"

# هشتاقات اكتشاف ثابتة عالية البحث (تجلب جمهوراً جديداً لا يعرف المتجر).
# تُلحق بعد الهشتاقات الديناميكية (الاسم/الكود/الأقسام).
EVERGREEN_HASHTAGS = [
    "#كوبون",
    "#كوبونات",
    "#خصومات",
    "#عروض",
    "#تخفيضات",
    "#كود_خصم",
    "#السعودية",
]


def _hashtagify(value: str) -> str | None:
    """يحوّل نصاً إلى هشتاق واحد نظيف:
    يحذف الرموز/علامات الترقيم، ويستبدل الفراغات بشرطة سفلية.
    يبقي الحروف العربية واللاتينية والأرقام. يُرجع None لو خرج فارغاً."""
    if not value:
        return None
    text = value.strip().lstrip("#")
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)   # أزل الترقيم
    text = re.sub(r"\s+", "_", text.strip(), flags=re.UNICODE).strip("_")
    return f"#{text}" if text else None


def _parse_store_tags(raw: str | None) -> list[str]:
    """store_tags نصّ بصيغة array-literal '{a,b,c}'. نفكّكه إلى قائمة نصوص."""
    if not raw:
        return []
    inner = raw.strip().strip("{}")
    return [t.strip().strip('"') for t in inner.split(",") if t.strip()]


def _build_hashtags(store: dict) -> list[str]:
    """يبني هشتاقات ديناميكية من بيانات المتجر:
    البراند + اسم المتجر (عربي/إنجليزي) + الأقسام + هشتاقات اكتشاف ثابتة.
    لا نُهشتِق كود الخصم (بلا قيمة بحثية).
    يُزيل التكرار مع الحفاظ على الترتيب (case-insensitive)."""
    candidates: list[str | None] = [BRAND_HASHTAG]
    # اسم المتجر بالعربي ثم الإنجليزي (إن اختلف)
    candidates.append(_hashtagify((store.get("store_id") or "").strip()))
    candidates.append(_hashtagify((store.get("name_en") or "").strip()))
    # الأقسام/الفئات (عناية/أزياء/إلكترونيات... من store_tags)
    for tag in _parse_store_tags(store.get("store_tags")):
        candidates.append(_hashtagify(tag))
    # هشتاقات الاكتشاف الثابتة
    candidates.extend(EVERGREEN_HASHTAGS)

    seen: set[str] = set()
    result: list[str] = []
    for h in candidates:
        if not h:
            continue
        key = h.lower()
        if key not in seen:
            seen.add(key)
            result.append(h)
    return result


def build_post_text(store: dict) -> str:
    """
    يبني نص المنشور الموحّد من صف master.

    المتوقّع في `store`:
      store_id, name_en, public_coupon, discount_value, extra_offer,
      description, store_bio, store_tags, affiliate_link
    الحقول الاختيارية تُحذف من النص لو ناقصة.
    """
    name        = (store.get("store_id") or "").strip()
    name_en     = (store.get("name_en") or "").strip()
    coupon      = (store.get("public_coupon") or "").strip()
    discount    = (store.get("discount_value") or "").strip()
    extra       = (store.get("extra_offer") or "").strip()
    # النبذة = store_bio أولاً (وصف المتجر — المالك يكتبها هنا عادة)،
    # وإن لم توجد نسقط على description (تفاصيل العرض).
    bio         = (store.get("store_bio") or "").strip()
    description = (store.get("description") or "").strip()
    nbthah      = bio or description
    link        = (store.get("affiliate_link") or "").strip()

    # اسم المتجر: بالعربي + (الإنجليزي بين قوسين) لو موجود
    name_line = name + (f" ({name_en})" if name_en and name_en.lower() != name.lower() else "")

    lines = [
        "نبض الصفقات",
        "",
        f"المتجر: {name_line}",
    ]
    if discount:
        lines.append(f"نسبة الخصم: {discount}")
    if coupon:
        lines.append(f"كود الخصم: {coupon}")
    if extra:
        lines.append(f"عرض إضافي: {extra}")
    if nbthah:
        lines.append("")
        lines.append(f"نبذة: {nbthah}")
    lines.append("")
    lines.append("استفد من العرض من خلال الرابط التالي:")
    lines.append(link or "—")

    hashtags = _build_hashtags(store)
    if hashtags:
        lines.append("")
        lines.append(" ".join(hashtags))

    return "\n".join(lines)
