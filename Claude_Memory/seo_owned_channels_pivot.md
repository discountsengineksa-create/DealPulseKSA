---
name: seo-owned-channels-pivot
description: 2026-07-08 قرار التخلّي عن Reddit/Quora/مدوّنين والتركيز على القنوات المملوكة (X + Telegram + Instagram) + دليل Google Indexing API
type: project
originSessionId: bf501e24-1a22-42b8-8227-c51a7b2dd362
---
**متى:** 2026-07-08 (commit 043d908).

> 🔄 **نُقض جزئياً ٢٠٢٦-٠٨-١٤:** المالك طلب Guest Post على مواقع سعودية ⇒ **بند «لا مدوّنين
> خارجيين» لم يعد سارياً**. Reddit/Quora باقيان مرفوضين. القائمة المؤكَّدة والرسائل الجاهزة في
> [[seo_authority_building]] وريبو الويب `seo/guest_post_targets_ksa.md`.

**قرار المالك (صريح):** لا Reddit، لا Quora، لا مدوّنين خارجيين. أسباب:
- Reddit/Quora يحتاجون بناء كرمة/سمعة (استثمار وقت غير مباشر لعائد غير مؤكّد)
- مدوّنون خارجيون بلا قائمة أسماء مسبقة → بحث برمجي مكلف + معدّل ردّ منخفض
- **الأصل الحقيقي:** ٢٤٠ مستخدم تيليجرام + حسابات X/IG تحت سيطرته الكاملة

**القنوات المفعّلة الآن (٣):**
1. **Telegram Bot Broadcast** — عبر `📢 مركز الإشعارات` في الداشبورد (`broadcast_logs`, `broadcast_tracking` جاهزين). ٢٤٠ مستخدم. أسرع دفعة ترافيك ممكنة.
2. **X @dealpulseksa** — الحساب موجود، نفس إيميل/سرّ IG، API مدفوع فما ربطناه بالداشبورد. النشر يدوي. ثريد ٩ تغريدات جاهز في `owned_channels_launch_kit.md`.
3. **Instagram @dealpulseksa** — الحساب موجود، ٥ متابعين، engine ريلز مبنيّ لكن متوقّف (غير مُشخَّص). Story + Reel للـ`/calendar` جاهزون.

**الملفات المشحونة:**
- `seo/owned_channels_launch_kit.md` — كامل playbook للثلاث قنوات + جدول متابعة + مقاييس نجاح
- `seo/google_indexing_api_setup.md` — دليل خطوة بخطوة لإعداد Google Indexing API (المالك بحث عنها = مهتم)
- `seo/pr_blitz_kit.md` — الحزمة السابقة (Reddit/Quora/بلوغرز/إيميلات) محفوظة كمرجع fallback لو تغيّرت الاستراتيجية

**Google Indexing API:** لو المالك أكمل الإعداد، `ping_indexnow.ps1` ينضاف قوقل كخامس محرك مُخطَر (بدل ٤ الحالية). يقلّل وقت اكتشاف قوقل من أسابيع → ساعات.

**السؤال المفتوح لجلسة قادمة:**
- إذن broadcast /calendar للـ٢٤٠ مستخدم تيليجرام (توقيت + رسالة نهائية).
- قرار إعادة تشخيص IG reels engine (متوقّف غير مُشخَّص) أم اعتماد النشر اليدوي.

يخدم: [[seo-indexation-status]] · [[seo-pr-blitz-kit]] (الحزمة السابقة).
