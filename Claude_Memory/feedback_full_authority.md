---
name: Full Authority Granted — execute without permission prompts (with hard walls)
description: 2026-07-07 blanket authorization — trust-based autonomous execution on local/reversible actions; NOT a bypass of DB/bot/publish walls
type: feedback
originSessionId: b6ba939a-2469-4f6a-9833-5d2da06c5e04
---
**نص المالك (2026-07-07):** «أعطيك الصلاحيات كاملة، أنا أثق بك، انطلق، لا تسألني عن صلاحية.»

**التفسير التنفيذي:** تفويض دائم بالتنفيذ الذاتي على الأفعال المحلية القابلة للعكس بدون سؤال متكرر عن كل عملية.

**Why:** المالك يعطّل احتكاك «هل أستطيع؟» بعد قفل بروتوكول الشراكة. الثقة مبنيّة على ٤ ركائز البروتوكول (إعلان → تحقّق → إثبات → تعلّم) لا على مراجعة كل خطوة. السؤال المتكرر = فقدان وقته لا حماية له.

**How to apply — أفعال مسموحة تلقائياً:**
- تركيب/سحب/تحديث ملفات محلية، skills، ريبوهات (git clone/pull).
- إنشاء/تعديل ملفات في مساحة العمل والمجلدات الشخصية.
- WebSearch/WebFetch على أي مجال تقني/تجاري ([[protocol_partnership]] §سياسة المصادر).
- تعديلات كود على ريبو الديسكاونت والويب — commit + push مباشر إلى main ([[feedback_always_publish]] + [[feedback_always_push]]).
- تركيب مكتبات/تشغيل build/tests محلياً.

**How to apply — الحوائط الصلبة (لا يشملها التفويض):**
- **DB writes** ([[feedback_no_db_writes_without_permission]]): أي INSERT/UPDATE/DELETE على `discounts_engine` يحتاج إذناً صريحاً لكل عملية.
- **حذف كتلي/تدمير**: `rm -rf`, `git reset --hard`, force-push، DROP TABLE، حذف مجلدات كبيرة — إذن صريح لكل مرة.
- ~~البوت مجمّد~~ — **رُفع 2026-07-07** ([[bot_frozen_lock]])؛ التعديل مسموح ضمن البروتوكول العادي.
- **إعلانات مدفوعة على أسماء براندات** ([[affiliate_ppc_brand_restrictions]]): ممنوعة قطعياً.
- **SEO Black-Hat** ([[seo_white_hat_only]]): ممنوع مطلقاً.
- **نشر رسائل نيابةً عنه** (Telegram broadcasts، رسائل PR reviewers، إيميلات صادرة): إذن لكل رسالة.

**قاعدة الحسم عند الشك:** إن كان الفعل محلياً وقابلاً للعكس بـ `git checkout` أو حذف ملف = نفّذ. إن كان يمس مستخدمين حقيقيين، أموالاً، أو حالة مشتركة لا يمكن استرجاعها = اسأل جملة واحدة.

**اختبار مصداقية التفويض:** التفويض يُختبَر بأول ٥ أفعال بعد منحه. لو نفّذت شيئاً كان يجب السؤال فيه (لمس البوت مثلاً)، التفويض ينكسر وأعود للسؤال المفصّل حتى يُعاد.
