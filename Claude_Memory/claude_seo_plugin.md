---
name: claude_seo_plugin
description: إضافة claude-seo (١٨ agent + ٢٥ skill) مثبَّتة على مستوى الريبو لا الجهاز — تصل الجهازين والسحابة بـgit؛ لكن السحابة محجوبة عن dealpulseksa.com فالتدقيق شغل ترمنال
metadata:
  type: project
---

**المصدر:** [`AgriciDaniel/claude-seo`](https://github.com/AgriciDaniel/claude-seo) · MIT · **v2.2.4**.
**عُدّ حيّاً ٢٠٢٦-٠٨-٠٩:** `ls agents/ | wc -l` = **١٨** agent · `ls skills/ | wc -l` = **٢٥** skill · ٥٣ سكربت بايثون.

## التثبيت — على الريبو لا على الجهاز (هذا هو الدرس)

الجذر الذي عالجناه: المهارات تُثبَّت افتراضياً في `~/.claude/` وهي **محلية لكل جهاز** — فتولد
الجلسة السحابية بلا أي مهارة، ويتباين الجهازان ([[skills_install_manifest]]: ٢٣٨ مقابل ١٧).
المكان هو العلّة، لا نقص التثبيت.

الحل في **`.claude/settings.json` المتتبَّع بـgit** — يرثه كل جهاز وكل جلسة سحابية بنفس آلية
`Claude_Memory/` ([[memory_sync_junction]] · [[claude_code_cloud_sessions]]):

```json
{
  "extraKnownMarketplaces": {
    "agricidaniel-claude-seo": { "source": { "source": "github", "repo": "AgriciDaniel/claude-seo" } }
  },
  "enabledPlugins": { "claude-seo@agricidaniel-claude-seo": true }
}
```

⚠️ **الشكل خريطة لا مصفوفة.** ملخّص التوثيق أعطاني مصفوفة `[{...}]` وكان **خطأ**؛ الشكل الصحيح
انتُزع بترك الـCLI يكتبه: `claude plugin install claude-seo@agricidaniel-claude-seo --scope project`.
القاعدة: لا تكتب إعدادات بالتخمين — شغّل الأمر الذي يولّدها.

**الإثبات (لا ادّعاء):** أُفرغت `~/.claude/settings.json` إلى `{}` ثم بقي
`claude plugin marketplace list` يحلّ `agricidaniel-claude-seo`، و`claude plugin list` يعرض
`claude-seo v2.2.4 · Scope: project · enabled` — من إعدادات الريبو وحدها.

**ما زال لكل جهاز مرّة واحدة:** لو أبلغ Claude Code أن الإضافة «غير مثبّتة»، شغّل
`claude plugin install claude-seo@agricidaniel-claude-seo`. وللمحرّك البايثوني وPlaywright:
`/seo setup` ثم `/seo doctor` (لم يُشغَّلا في الجلسة السحابية — بلا قيمة هناك).

## 🚧 السقف — السحابة لا تستطيع تدقيق الموقع إطلاقاً

بوّابة الخروج في البيئة السحابية **تحجب `dealpulseksa.com`**. مُثبَت بمخرَجين:
`curl` أعطى `CONNECT tunnel failed, response 403`، و`$HTTPS_PROXY/__agentproxy/status` سجّل
`connect_rejected … dealpulseksa.com:443`. وWebFetch ردّ `EGRESS_BLOCKED`.

⇒ **كل تدقيق فعلي شغل ترمنال** (كما أن عدّ الجداول شغل ترمنال — نفس منطق [[claude_code_cloud_sessions]]).
البديل الوحيد: تعديل سياسة الشبكة للبيئة السحابية لتسمح بالنطاق. السحابة تصلح للتخطيط
وقراءة الكود وكتابة الذاكرة، لا للزحف.

## خريطة المطابقة — أي agent يستحق وقتاً على «نبض»

الترتيب مبني على عنق الزجاجة الموثّق في [[seo_page_portfolio_verdict]] (٧١٠ من ٧٦٤ صفحة صفر نقرة؛
صفحات المتاجر نيّة تنقّل ميتة؛ ٧٠٠ مقال ترتيبها ١–٤ بظهور ١–٢ = **مشكلة اختيار كلمات**؛
التجميع/المناسبات هو النمط الوحيد المُثبت):

| الأولوية | الـagent | لماذا يخصّنا تحديداً |
|---|---|---|
| ١ | **seo-sxo** | «لماذا تفشل صفحة محسّنة في الترتيب» + كشف عدم تطابق نوع الصفحة مع النيّة — هذا **حرفياً** تشخيص الدلو ١ (بيلاس: ٣٩٨ ظهوراً، م 5.7، صفر نقرة) |
| ٢ | **seo-cluster** | تجميع بتداخل SERP الفعلي + هَب-وأذرع + مصفوفة ربط داخلي — يعالج جذر الدلو ٢ (اختيار الكلمات) وينسخ نمط التجميع الرابح |
| ٣ | **seo-content** | E-E-A-T + رقّة المحتوى + جاهزية الاستشهاد — على `/calendar` (الرافعة الأعلى: م 6.3 → 2–3 = مضاعفة ترافيك الموقع) وعلى ١٥٦٤ مقالاً |
| ٤ | **seo-backlinks** | Moz + Bing Webmaster + Common Crawl **مجاناً** — والسلطة هي السقف المعلن في [[seo_authority_building]] |
| ٥ | **seo-google** | GSC + CrUX + GA4 ببيانات حقيقية؛ حساب خدمة `gsc-indexer` موجود أصلاً (`GSC_SA_JSON`) فالتوصيل قصير |
| ٦ | **seo-drift** | لقطة أساس + كشف الانحدار — الوقاية من صنف بق «light-AR 500 أفرغ الخريطة صامتاً» ([[seo_deep_audit_fixes]]) |
| ٧ | seo-technical · seo-schema · seo-sitemap | نظافة دورية؛ ولـ`/c/` تحديداً انتبه لفخّ ISR ([[seo_c_store_cannibalization]]) |
| — | **صفر فائدة** | `seo-local` و`seo-maps` (لا فرع فعلي) · `seo-hreflang` (القرار «عربي فقط لا /en») · `seo-ecommerce` (لسنا تاجراً) · `seo-dataforseo` (مدفوع) |

## الأمان والتكلفة — فُحصت قبل التبنّي

- **بلا تتبّع.** `PRIVACY.md`: لا telemetry، والنواة لا تنادي طرفاً ثالثاً افتراضياً. الامتدادات
  المدفوعة (DataForSEO/Ahrefs/SE Ranking/Profound) اختيارية وغير مفعّلة.
- **متوافق مع الحائط ٤ (White-Hat).** `seo-programmatic` نفسه يفرض بوّابات ضد المحتوى الرقيق
  و«mad-libs» وتضخّم الفهرس — يعزّز [[seo_white_hat_only]] ولا يخالفه.
- ⚠️ **hook يعترض التعديلات.** `PostToolUse` على `Edit|Write` يشغّل `validate-schema.py`.
  يُصفّي نفسه (يفحص فقط ملفاً فيه `<script type="application/ld+json">`) لكنه **يرجع كود ٢
  فيحجب التعديل** عند خطأ حرج. يخصّ ريبو الويب لا هذا الريبو.
- **ضريبة سياق دائمة:** ٢٥ وصف skill + ١٨ وصف agent في كل دور. مفتاح الإطفاء عند العمل
  على البوت/الداشبورد: `/plugin disable claude-seo@agricidaniel-claude-seo`.
