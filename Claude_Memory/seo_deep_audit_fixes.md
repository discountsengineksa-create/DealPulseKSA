---
name: seo-deep-audit-fixes
description: تدقيق SEO عميق 2026-07-07 — كشف بق light-AR 500 (أفرغ الخريطة/المتاجر/llms صامتاً) + تنظيف ادعاءات متاجر مفبركة؛ دروس الهجرة والتشعّب
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f539881-da98-4e78-aa1a-629208bf7e77
---

جلسة «اشتغل بعمق على السيو» (2026-07-07) — تدقيق تقني حيّ + كود كشف بقّين كبيرين:

**🐛 (1) بق light-AR 500 أفرغ صفحات الإيراد صامتاً (backend commit 4d1d4e8):** الـendpoint `GET /api/v1/coupons/?view=light&lang=ar` كان يرجّع **HTTP 500**. السبب الجذري: هجرة `is_trending BOOLEAN + priority_score SMALLINT` (600ea3a) حدّثت **٣ من ٤** جُمل SELECT في `api/routers/coupons.py` لتُرجع `is_trending_bool AS is_trending, priority_score_int AS priority_score`، لكن **نسِيت جملة light العربية** (بقيت تُرجع النص الخام `is_trending`). ولأن `StoreResult.is_trending` صار `bool`، رفض pydantic النص 'عادي'/'ترند 🔥' → 500. (light-EN وfull-AR/EN كانت محدّثة فتعمل — لهذا AR فقط 500.) **الأثر الصامت:** `getStores` في الويب يبلع الأخطاء كـ`[]`، فأفرغ: **الـsitemap (كل المتاجر + التصنيفات) + صفحة /stores + llms.txt + /ig** — كلها تستهلك `view=light&lang=ar`. **الإصلاح:** جعل جملة light-AR تطابق الثلاث الأخرى. تأكّد حيّاً: 200 + 45 متجراً + is_trending=boolean، وllms.txt رجع 103 سطر متجر.
- **درس معماري:** أي هجرة تغيّر عمود يجب أن تحدّث **كل** جُمل الـSELECT (٤ هنا: full/light × ar/en)؛ ابحث عن كل مواضع العمود.
- **درس التشعّب (مهم):** مستودع الباك-إند (Discounts_Engine) كان **٩ كوميت خلف origin** فكنت أقرأ كوداً بائتاً (schema يقول is_trending: str بينما المنشور bool). **اسحب الباك-إند قبل تشخيص أي سلوك منشور.** [[git-sync-workflow]] [[reconcile-web-repo-separately]].
- **درس مرونة (web commit 1dc7c12):** الابتلاع الصامت `[] on error` أخفى العطل ساعات. أضفت fallback في `getStores`: إن فشل/فرغ `light` → أعِد المحاولة بـ`full` (يعمل، والكتالوج صغير) فتتدهور تغطية الخريطة برشاقة وتُشفى ذاتياً.

**🚫 (2) تنظيف ادعاءات متاجر مفبركة (web commit a30963f):** الكتالوج **٤٥ متجراً فقط**، لكن نصوص الموقع ادّعت «**آلاف الكوبونات**» وسمّت متاجر **غير موجودة**: أمازون/Amazon SA + 6th Street + Ounass + Carrefour + حنين. نفس صنف الادعاء الذي طهّره المالك سابقاً من llms.txt (انظر [[seo-indexation-status]]). **أُصلح بمتاجر الكتالوج الحقيقية** (نون، نمشي، شي إن، H&M، سيدار، علي اكسبرس، ماماز آند باباز، فوغا كلوسيت) في: `app/layout.tsx` (وصف الرئيسية + keywords) · `app/faq/data.ts` (عربي+إنجليزي، يغذّي FAQPage JSON-LD) · `app/deals/page.tsx` (keywords) · `lib/translations.ts` (فقرة «من نحن»). **إبقاء:** ذِكر منتجات Amazon الحقيقية في أدلة الشراء (Fire Kids/Echo) — حقيقة لا فبركة. يخدم [[content-guardrails-playbook]] (صفر فبركة) وE-E-A-T.

**✅ سليم في التدقيق:** robots.txt (Allow/Disallow صحيح) · schema المتجر (Breadcrumb+Offer+OnlineBusiness، **بلا Product/AggregateRating** — لا مخالفة) · الرئيسية تربط كل الهَبات (/stores ×6، /categories، /blog، /deals، /trending، /calendar) · canonical/title/og سليمة عبر أنواع الصفحات. يكمّل [[blog-internal-link-deorphan]] و [[seo-indexation-status]].
