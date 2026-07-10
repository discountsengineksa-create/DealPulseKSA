---
name: seo-pr-blitz-kit
description: seo/pr_blitz_kit.md شُحن 2026-07-08 — playbook إطلاق كامل لترويج /calendar (Reddit×4 + Quora AR×3 + X ثريد + إيميلات مدوّنين ×5)
type: project
originSessionId: bf501e24-1a22-42b8-8227-c51a7b2dd362
---
**متى:** 2026-07-08 (commit d2a53d6).

**الحقيقة:** أصل الاستشهاد `/calendar` (شُحن 2026-07-03 web 303c744) كان **منشوراً بلا ترويج** — لهذا صار `backlink_targets.md` يعتمد على أدلة B (nofollow) والطبقة D الأقوى معطّلة. الحزمة الجديدة تفكّ هذا الاختناق.

**ماذا يحوي:**
- ٤ منشورات Reddit جاهزة (r/saudiarabia + r/saudi + r/khaleej + r/UAE) بحيل خاصة لكل مجتمع
- ٣ إجابات Quora AR كاملة (الجمعة البيضاء + أفضل الأوقات + كيف تعرف الخصم الحقيقي)
- ثريد X بـ٨ تغريدات (٧ محتوى + ١ للرابط في النهاية)
- ٥ إيميلات ترويج (مدوّن تسوّق + صانع تيك توك + صحفي + قناة تيليجرام + guest post)
- جدول متابعة بـ13 بند
- قواعد أمان (ما لا يجب فعله)
- مقاييس نجاح واقعية (٦ أسابيع → 5-8 روابط عالية القيمة + AS من 0 → 8-12)

**قواعد ملزَمة داخل الحزمة:**
- كل نص صادق ومفيد فعلاً (لا سبام، لا drop-and-run)
- تخصيص لكل منصّة (نفس المحتوى منسوخاً حرفياً = footprint سبام)
- 9:1 قيمة مقابل رابط (Reddit خصوصاً)
- سقف ٣/يوم للحدّ من الظهور القسري

**التتبّع:** GSC → Links + web_visits (traffic sources) + Ahrefs + action_logs.referrer.

**السلاح المُصاحب:** أمر PowerShell لإطلاق IndexNow يدوياً على /calendar قبل الترويج (يستدعي `/admin/seo-resubmit-url` — endpoint موجود في api/routers/admin.py:1501).

**الفارق عن `seo/community_outreach_kit.md`:** الأخير قوالب ردود قصيرة عامّة (Q&A). هذي حملة إطلاق كاملة بتوقيت وترتيب وتتبّع لأصل واحد محدّد.

يخدم: [[seo_indexation_status]] (فكّ 244 المكتشفة غير المفهرسة عبر باكلينك) · [[domain_authority_plan]] · [[seo_white_hat_only]].
