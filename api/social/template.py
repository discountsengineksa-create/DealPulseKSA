"""قالب موحّد لمنشورات السوشيال — صامت، بدون إيموجيز، كما حدّده المالك."""
from __future__ import annotations


def build_post_text(store: dict) -> str:
    """
    يبني نص المنشور الموحّد من صف master.

    المتوقّع في `store`:
      store_id, public_coupon, last_time (str أو date), description, affiliate_link
    """
    name        = store.get("store_id") or ""
    coupon      = store.get("public_coupon") or "—"
    last_time   = store.get("last_time")
    description = (store.get("description") or "").strip() or "—"
    link        = store.get("affiliate_link") or ""

    # last_time قد يكون date أو str — نحوّله لنص قصير
    if last_time is None:
        last_time_str = "—"
    else:
        last_time_str = str(last_time)[:10]  # YYYY-MM-DD

    return (
        "نبض الصفقات\n\n"
        f"المتجر: {name}\n"
        f"كود الخصم الجديد: {coupon}\n"
        f"تاريخ انتهاء الكوبون: {last_time_str}\n"
        f"تفاصيل العرض: {description}\n\n"
        "يمكنكم الاستفادة من العرض وتصفح التفاصيل مباشرة عبر الرابط التالي:\n"
        f"{link}"
    )
