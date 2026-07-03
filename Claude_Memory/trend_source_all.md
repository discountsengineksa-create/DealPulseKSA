---
name: Trend Uses source='all' Everywhere
description: قاعدة البيانات واحدة — الترند يُحسب من إجمالي الحركات والمفضلة، لا تجزئة per-platform
type: project
originSessionId: ec283917-aedb-4547-b16e-a60f0d2e474d
---
كل واجهة (موقع، ميني، داشبورد) تستهلك `/trend/daily?source=all` و `/trend/weekly?source=all`.

**Why:** قاعدة بيانات واحدة. الحركات (`action_logs`) والمفضلة (`user_favorites`) تتجمّع من كل المصادر — البوت، الويب، الميني. الترند يجب أن يعكس الإجمالي. تجزئة `source=web/mini/bot` كانت تُنتج قوائم متضاربة بين القنوات (نفس المتجر ترند في الميني وعادي في الموقع) رغم أن DB واحد.

**How to apply:**
- أي fetch لـ `/api/v1/trend/{daily,weekly}` يجب أن يستخدم `?source=all`.
- لا تقترح إضافة فلاتر per-platform — قائمة `SourceLiteral` في `api/routers/trend.py` ما زالت تدعم all/bot/web/mini للاستخدام الإداري فقط، لا للواجهات.
- `_sa_trend_store_ids()` في الداشبورد هو المرجع الموحّد — أي واجهة يجب أن تطابق ناتجه.
- ملاحظة: لا توجد ستوري على البوت إطلاقاً — البوت يرسل رسائل تيليجرام فقط. الستوري حصرياً موقع + ميني-ويب.
