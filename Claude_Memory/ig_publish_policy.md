---
name: IG Publishing Policy (Stories Manual, Reels Auto-Every-6)
description: قرار 2026-06-19 — الستوري التلقائية ملغاة على إنستقرام، والريل يُنتَج تلقائياً بعد كل 6 بثّات
type: project
originSessionId: 8ad06fba-06cb-4d18-a88b-e16ec326d304
---
قرار 2026-06-19 لمحرّك نمو إنستقرام في DealPulseKSA:

**الستوري التلقائية ملغاة** — الكود محذوف من `api/social/dispatcher.py:_broadcast_to_instagram`. المالك ينشر الستوريات يدوياً من تطبيق إنستقرام بدل من البوسترات المربّعة الأوتوماتيكية.

**الريل التلقائي يبقى نشطاً** — بعد كل بث ناجح، يُعاد `master.last_reeled_at = NULL` للمتجر الحالي، ثم يُستدعى `run_pending_batches(conn)`. النتيجة: كل ٦ بثّات تراكمياً = ريل تلقائي واحد بـ٦ متاجر.

**Why:** المالك جرّب الستوري الأوتوماتيكية واكتشف:
- البوستر المربّع كان يخرج فاضي (أصلحناه لـ٩:١٦)
- حتى مع الإصلاح، يفضّل التحكّم اليدوي بمحتوى الستوري (نصوص/stickers/تفاعل)
- الريل الجماعي ذو القيمة الأعلى (٦ متاجر × 30 ثانية) يستحق الأتمتة

**How to apply:**
- لا تُعد إضافة `post_story` للـdispatcher التلقائي
- لو احتاج المالك ستوري تجريبية، الـendpoint `POST /api/v1/admin/social/test-story/{master_id}` يبقى متاحاً للاختبار اليدوي
- الـspec `instagram_story = 1080×1920` في `image_specs.py` يبقى للاستعمال اليدوي عبر الـendpoint
- لا تُغيّر منطق إعادة `last_reeled_at=NULL` في dispatcher — هو اللي يضمن استمرار «كل 6 = ريل»
