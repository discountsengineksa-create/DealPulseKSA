---
name: web_login_gate_model
description: نموذج بوّابة دخول الويب — الموقع مفتوح حالياً، والستوري/المفضلة للمسجّلين فقط
metadata: 
  node_type: memory
  type: project
  originSessionId: 536cdd44-338f-4363-a3bd-17fc763857f8
---

بوّابة دخول الموقع يتحكّم بها الأدمن عبر `web_login_gate_enabled` في
`platform_settings` (داشبورد → «إدارة الموقع»؛ يقرأها الويب من
`/coupons/site-flags`).

**الحالة الحالية في الإنتاج (Railway): مُطفأة = `0` (الموقع مفتوح)** — ضُبطت
2026-06-22 بطلب المستخدم «افتح الموقع للكل».

النموذج بعد إعادة التشكيل في [lib/auth-gate.tsx]:
- **الكود/الزيارة** = مكشوف لو (مسجّل **أو** البوّابة مطفأة). المنطق:
  `requireAuth`/`promptAuth`/`isLoggedIn`(=codeUnlocked).
- **الستوري** = «للمسجّلين فقط» دائماً، لا تتأثّر بفتح الموقع. المنطق المنفصل:
  `isAuthed`/`requireLogin`/`promptLogin`. القرار: **الستوري محجوبة بالكامل** —
  النقر على الحلقة بلا تسجيل يفتح نافذة الدخول (لا مشاهدة بلا حساب).
- **المفضلة** = للمسجّلين فقط عبر مصادقة حقيقية مستقلة في [lib/favorites.tsx]
  (`useAuth().user`)، غير مرتبطة بالبوّابة أصلاً.
- صفحات الدخول/التسجيل وزر الدخول في الهيدر **تبقى متاحة دائماً** حتى مع فتح
  الموقع (الستوري/المفضلة تحتاجها). أُزيل `useRedirectIfGateOff` نهائياً.
- إغلاق موديال auth-gate التلقائي يعتمد `authed` لا `codeUnlocked` (وإلا تُغلق
  نافذة الستوري فور فتحها عند فتح الموقع).

حركات الزائر المجهول تُحتسب تلقائياً: `/track` و`/track/category-view`
و`/track/visit` تقبل `user_id=NULL` مع `visitor_id`، وعدّادات master تتحدّث
للأحداث عالية الجودة بلا اشتراط تسجيل. مرتبط بـ [[web_visits_tracking]]
و[[data_trust_geo_device]] و[[feedback_zero_friction]].
