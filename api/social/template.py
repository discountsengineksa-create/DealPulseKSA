"""قالب موحّد لمنشورات السوشيال — صامت، بدون إيموجيز، كما حدّده المالك."""
from __future__ import annotations


def build_post_text(store: dict) -> str:
    """
    يبني نص المنشور الموحّد من صف master.

    المتوقّع في `store`:
      store_id, name_en, public_coupon, discount_value, extra_offer,
      last_time, description, affiliate_link
    الحقول الاختيارية تُحذف من النص لو ناقصة.
    """
    name        = (store.get("store_id") or "").strip()
    name_en     = (store.get("name_en") or "").strip()
    coupon      = (store.get("public_coupon") or "").strip()
    discount    = (store.get("discount_value") or "").strip()
    extra       = (store.get("extra_offer") or "").strip()
    last_time   = store.get("last_time")
    # النبذة = store_bio أولاً (وصف المتجر — المالك يكتبها هنا عادة)،
    # وإن لم توجد نسقط على description (تفاصيل العرض).
    bio         = (store.get("store_bio") or "").strip()
    description = (store.get("description") or "").strip()
    nbthah      = bio or description
    link        = (store.get("affiliate_link") or "").strip()

    # last_time قد يكون date أو str — نحوّله لنص قصير
    if last_time is None or str(last_time).strip() == "":
        last_time_str = "—"
    else:
        last_time_str = str(last_time)[:10]  # YYYY-MM-DD

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
    if last_time_str and last_time_str != "—":
        lines.append(f"تاريخ انتهاء الكوبون: {last_time_str}")
    if extra:
        lines.append(f"عرض إضافي: {extra}")
    if nbthah:
        lines.append("")
        lines.append(f"نبذة: {nbthah}")
    lines.append("")
    lines.append("استفد من العرض من خلال الرابط التالي:")
    lines.append(link or "—")

    return "\n".join(lines)
