---
name: saashub-directory-listing
description: SaaSHub — رابط الدليل nofollow حتى تُوثَّق الملكية (قياس ٢٢ صفحة)؛ التوثيق مجاني بلا رابط متبادل فيعبر بوابة الأدلّة الباردة
metadata:
  type: project
---

**متى:** ٢٠٢٦-٠٨-٠٩ (دليل بدائل برمجيات، ٢٣٦ ألف منتج).

**الحالة الحقيقية:** المنتج **مرفوع ومُوثَّق** — `saashub.com/deal-pulse-ksa`، التوثيق تمّ
**٢٠٢٦-٠٧-٠٥** (ACTIVE، يُجدَّد كل ربع ⇒ ~٢٠٢٦-١٠-٠٥). **العائق `Not approved`:** الصفحة
تفتح 200 لكن **بلا أي رابط لنا**، وتعرض روابط منتجات أخرى (Preferred Patron / RetailMeNot).
العلاج = إكمال التبويبات الفارغة ثم `Verify`؛ **Competitors أولاً** (صفحة الإرسال تنصّ أن
الطلب بلا منافسين يُنزَل آخر الطابور).

**🔻 خطأ ارتكبتُه ويستحقّ التسجيل:** بحثتُ بـ`dealpulseksa` ملزوقة ⇒ صفر نتائج ⇒ أعلنتُ
«المنتج غير مُدرَج» وبنيتُ عليه خطوات رفع كاملة. الاسم هناك **`Deal Pulse KSA`** بمسافات
والـslug `deal-pulse-ksa`. **صفر نتائج لصيغة بحث واحدة ليست دليل عدم وجود** — جرّب الاسم
بمسافات والـslug المفصول، أو افتح لوحة الحساب مباشرة، قبل ما تعلن حالة.

## القاعدة القابلة للتعميم — قِس الـ`rel` قبل ما تصرف جهداً على أي دليل

الإدراج في دليل **لا يعني رابطاً يمرّر سلطة**. في SaaSHub القياس حسم الأمر:
عيّنة **٢٢** صفحة منتج في `/best-discount-codes-software`، بقراءة سمة `rel` على رابط الـhero:

- كل صفحة عليها `verified badge` ⇒ `rel=""` (**dofollow**) — ٦ منتجات.
- كل صفحة عليها `/verify/<slug>` ⇒ `rel="nofollow"` — ١٤ منتجاً، منها **honey وgroupon
  وcoupons.com وdealspotr وdontpayfull** (الكبار غير موثَّقين ⇒ nofollow؛ الحجم لا يشتري dofollow).
- الارتباط **١٠/١٠** في فحص مباشر، وثابت عبر ٣ عمليات جلب (لا A/B).

```bash
curl -sL -A "Mozilla/5.0" "https://www.saashub.com/<slug>" \
  | grep -oE '<a [^>]*data-ref="hero"[^>]*>' | grep -oE 'rel="[^"]*"'
```

⚠️ **مزلق:** `/<slug>-alternatives` تعطي `rel=""` بينما `/<slug>` تعطي `nofollow` لنفس المنتج
(تأكّد على honey). صفحة المنتج هي التي تُقاس.

## لماذا يعبر البوابة وSellWithBoost رسب

بوابة الأدلّة الباردة في [[seo_white_hat_only]]: **كيف يُدفَع ثمن الرابط؟** رابط متبادل منّا أو
دفع مقابل do-follow ⇒ Link Scheme ⇒ رفض. SaaSHub: الإدراج مجاني، والتوثيق مجاني بطريقتين
(**إيميل على نطاق المنتج** أو **HTML meta tag**)، والبادج المعروض `Show embed code` **ترويج
اختياري لا شرط**. ⇒ يعبر. الطريق العملي عندنا = **meta tag**، لأن Resend مربوط للإرسال فقط
فلا صندوق استقبال على النطاق.

## القيمة الواقعية — لا تضخّمها

إشارة كِيان + رابط dofollow واحد بعد التوثيق. **صفر ترافيك**: الجمهور إنجليزي/صانعو برمجيات،
لا متسوّق سعودي — نفس ملاحظة SellWithBoost. مكانه الطبقة ١ مع Trustpilot و[[domain_authority_plan]]،
لا أكثر. الفارق عن الأدلّة المرفوضة أن التصنيف مطابق فعلاً: eCommerce → Discount Codes
(فيه getcoupons.ae ونظائرها).

**المحتوى الجاهز للّصق + بروتوكول التوثيق + الأرقام المعدودة:** ريبو الويب
`seo/saashub_listing.md` (web `c26c834`)، والبند مسجَّل في `seo/authority_building_plan.md`.

**⚠️ أُصلح بنفس الدفعة:** بطاقة NAP في `authority_building_plan.md` كانت تحمل الهجاء الميّت
`dealpulesksa@gmail.com` — وهي البطاقة التي تُلصق حرفياً في كل دليل. الصحيح
`dealpulseksa@gmail.com` ([[contact_emails]] · [[domain_canonical_trap]]).

**المعلّق:** إكمال Competitors/Description/Features/Pricing/Platforms/Screenshots ثم `Verify`.
لا حاجة لـmeta tag ولا لصندوق بريد على النطاق — التوثيق مُنجَز.
(لو احتجناه مستقبلاً: النطاق على Cloudflare بلا سجلات MX ⇒ Email Routing المجانية تحلّها.)
