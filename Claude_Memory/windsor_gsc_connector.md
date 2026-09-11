---
name: windsor_gsc_connector
description: Windsor MCP فيه Search Console + Instagram موصولان، لكن الخطة المجانية تسمح بحساب واحد فتُحجب القراءة
metadata: 
  node_type: memory
  type: reference
  originSessionId: c62855b1-ac5e-43c8-b626-e7e183f2c621
  modified: 2026-08-01T07:18:13.503Z
---

## ✅ انفكّ الحجب — مؤكَّد ببيانات حقيقية ٢٠٢٦-٠٨-١٣

`get_data(connector="searchconsole", fields=["date","clicks","impressions","position"],
date_preset="last_28d")` رجّع **٢٧ صفّاً يومياً بأرقام حقيقية** — لا رسالة خطة ولا أصفار.
والفلترة تعمل أيضاً: `filters=[[["impressions","gte",25],"and",["position","lte",20]]]` مع
`fields=["query","clicks","impressions","position"]` أعطى ٢٥ استعلاماً في مسافة الضربة.

⇒ **المسار مفتوح لسحب بيانات البحث مباشرة بلا `GSC_SA_JSON` ولا لقطات من المالك.**
والقاعدة التي أنقذت الموقف هي المكتوبة أسفل هذا الملف: **اختبر بـ`get_data` فعلياً، لا
تفترض من ذاكرة عمرها أسبوعان.** (ما زال ينطبق: `date` للإجماليات، ولا تُجمع صفوف `query`.)

⚠️ **ما لا يعطيه Windsor/API إطلاقاً:** تقرير الروابط وتقرير `Crawl Stats` — كلاهما
واجهة GSC فقط، ويحتاج لقطة من المالك.

---

**Windsor.ai MCP** موصول بحسابين: `searchconsole` (`https://www.dealpulseksa.com/`) و
`instagram` (`17841444145819859` — كوبونات خصم نبض الصفقات).

**الحالة السابقة (٢٠٢٦-٠٨-٠١، متجاوَزة):**

**المطبّ:** الخطة المجانية تسمح بحساب واحد، فأي `get_data` يرجع **صفوفاً وهمية** نصّها
`"Uh-oh! You've connected more accounts than your Free plan allows"` مع أصفار — **لا يرجع
خطأ**. أي تحليل يبني على هذا الردّ بلا قراءته يخرج بأرقام صفرية كاذبة (تحقّقت 1 أغسطس 2026).

**⚠️ فكّ إنستغرام لم يكفِ (جُرِّب 1 أغسطس 2026):** ألغى المالك اختيار حساب إنستغرام، وواجهة
Windsor صارت `Data sources in use: 1/1`، و`get_connectors` رجّع **searchconsole وحده** —
ومع ذلك بقي `get_data` يرجّع رسالة تجاوز الخطة. أي بوّابة الخطة على مسار البيانات تتحقّق
من شيء غير قائمة الحسابات الظاهرة (كاش/تسجيل تاريخي). **لا تفترض أن اختفاء الموصِّل من
`get_connectors` يعني أن القراءة انفتحت — اختبر بـ`get_data` فعلياً.** المتبقّي: انتظار
انتشار، أو إعادة تسجيل دخول، أو ترقية.

حقول GSC المتاحة: `query`, `pagepath`, `clicks`, `impressions`, `position`, `country`,
`device`, `branded_vs_nonbranded`, `search_appearance` — استدعِ `get_fields` قبل `get_data`
دائماً. البديل القائم لبيانات البحث: صفحتا الداشبورد «📊 تقرير البحث» و«📈 أداء SEO».
