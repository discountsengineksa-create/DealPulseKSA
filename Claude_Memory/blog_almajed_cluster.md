---
name: blog_almajed_cluster
description: عنقود الماجد للعود ٢٠٢٦-٠٩-٠٥ — ١٥ مقالاً (١٤ almajed-* + مقال محايد mabsous-vs-maamoul-vs-dukhoon-saudi)؛ المبسوس والمعمول لم يكن لهما شرح مستقل قبل اليوم؛ web c58c55d؛ blog_bridge --write معلّق على إذن المالك
metadata: 
  node_type: memory
  type: project
  originSessionId: ee0d5060-4ded-42a4-876b-1b33520809e4
  modified: 2026-09-05T19:45:45.038Z
---

**المتجر:** `الماجد للعود` — `store_id='الماجد للعود'` (حيّ في coupons API، **آخر صفّ، شعبية ٠**)،
كود **`AR196`** (١٠٪ بلا حد أدنى، أساسي) + **`AS196`** (٣٠ ريال عند سلة ٣٠٠+، موسمي/عرض إضافي).
tags: `عود و بخور` · `عطور` · `هدايا`. عمولتنا ٣٪ CPS بلا سقف. المنصّة **بوستيني** (مدير الحساب
Nadeen Moataz). `/store/الماجد للعود` = `/store/%D8%A7%D9%84%D9%85%D8%A7%D8%AC%D8%AF%20%D9%84%D9%84%D8%B9%D9%88%D8%AF` (٢٠٠ حيّ).
تأسست ١٩٥٦، تصنيع عود وعطور، أقسام الموقع: عود · دخون · مبسوس · معمول · المباخر · الفحم ·
دهن عود/وود · عطور (رذاذ رجالي/نسائي/للجنسين) · عطور جسم/شعر · معطّرات · وود وايت.

**الفجوة:** `grep "مبسوس"` قبل اليوم = صفر صفحة شرح مستقلّة (كلمات داخل عنقود `oudroyal-*` فقط).
المبسوس والمعمول منتجان مميّزان للماجد بلا تغطية.

**التحقّق (لا فبركة):** `sa.almajed4oud.com` محجوب Cloudflare (403 على curl/WebFetch/sitemap) —
مثل ماكس/بوما ([[blog_maxfashion_puma_clusters]]). التحقّق تمّ عبر: مقارنة متخصّصة
(`bohalteeb.com` — بخور/معمول/مبثوث/دهن)، مقتطفات goldenscent/faces لأصناف الماجد، وصور المالك.
**المفاهيم المؤكّدة:** المبسوس = رقائق عود منقوعة بدهن العود وخلطة عطرية (مبثوث اسم مرادف عند
بعض المتاجر) · المعمول = عود مطحون يُعجن بالزيوت ومواد رابطة ويُخمّر أسبوع–شهر · الدخون = خشب خام
يُحرق مباشرة (كمبودي/هندي/معتّق) · دهن العود = زيت مقطّر على الجلد. صفر هرم نفحات مخترع لمنتج،
صفر سعر رقمي. وود وايت (عطر): برغموت+جريب فروت / توابل+لافندر / كراميل+زعفران+جلد — من مقتطف goldenscent.

**العنقود (web `c58c55d`، ١٥ مقالاً، بادئة `almajed-`، تصنيف «عود وبخور» = slug `oud` قائم):**
hub `almajed-guide-saudi` · `almajed-mabsous-guide-saudi` · `almajed-maamoul-guide-saudi` ·
`almajed-mabsous-vs-maamoul-saudi` · `almajed-oud-vs-bakhoor-forms-saudi` ·
`almajed-dukhoon-oud-guide-saudi` · `almajed-dahn-oud-guide-saudi` · `almajed-wood-white-guide-saudi` ·
`almajed-mabkhara-charcoal-guide-saudi` · `almajed-home-daily-fragrance-saudi` ·
`almajed-majalis-occasions-scent-saudi` · `almajed-gifts-guide-saudi` · `almajed-perfumes-guide-saudi` ·
`almajed-coupon-offers-saudi` · **محايد** `mabsous-vs-maamoul-vs-dukhoon-saudi` (متعدّد المتاجر).

**قرار مكافحة التكاذُب:** عود رويال (`HIIPP`) وعبدالصمد القرشي (`ADM63`) شريكان حيّان — **لم تُلمس
عناقيد `oudroyal-*` ولا `asq-*`**. التقاطع بين متاجر العود يتمّ في المقال المحايد فقط
(الماجد + عود رويال + عبدالصمد القرشي + بنت الشيخ + في للعطور + نون) وعبر تحديث هَبَّين محايدين
(`oud-bukhoor-guide-saudi-arabia` + `maamoul-bukhoor-guide-saudi-arabia`) — روح الحائط ٥
([[feedback_never_publish_competing_codes]] · [[blog_nazih_cluster]] · [[seo_c_store_cannibalization]]).

**التحقّق:** `next build` كامل **EXIT=0** (٢٠٨٢/٢٠٨٢ صفحة) بعد محاولتين فشلتا على
**جلب خطوط Google في Turbopack** (`@vercel/turbopack-next/internal/font/google/font` — عطل شبكة
عابر، لا علاقة له بالتعديل؛ **اقرأ `EXIT=` من السجل لا إشعار المهمة**). + `tsc -p` على
`blog.ts`+`blog/[slug]/page.tsx`+`sitemap.ts` صفر خطأ + esbuild bundle نظيف + عدّاد slug
1708→1723 + backtick زوجي. FAQPage مُصدَرة على المقالات المفحوصة (٣–٤ Question).

**معلّق:**
- **`blog_bridge --write`** (كتابة DB، حائط ١) — التجربة الجافّة: `1484→1499` صفّاً، `65→66`
  متجراً (الماجد أُضيف). الأمر: `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -m scripts.build_blog_bridge --write`.
  **لم يُنفَّذ — ينتظر إذن المالك الصريح.**
- **إعادة الفهرسة:** بعد نزول Vercel، ادفع الـ١٥ رابطاً + الهَبَّين المحدَّثين +
  `/store/الماجد للعود` إلى `api.dealpulseksa.com/api/v1/admin/reindex-urls` **بعد التأكّد أنها ٢٠٠**
  ([[seo_bulk_reindex_ops]] · قاعدة نزيه: لا تدفع رابطاً قبل ٢٠٠).
- صفحات `/c/` للماجد: يولّدها كرون ٣ص ما دام `seo_enabled=true` (فُعّل في الفورم).

يكمّل [[blog_maxfashion_puma_clusters]] · [[voice_bible]] · [[content_guardrails_playbook]] ·
[[feedback_verify_catalog_before_claim]] · [[boostiny_publisher_channel]] · [[search_intelligence_layer]].
