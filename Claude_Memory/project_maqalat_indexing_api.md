---
name: Maqalat Google Indexing API Live
description: 2026-09-05 Google Indexing API فُعِّل بنجاح لـmaqalat.org؛ سكربت Node.js صفر تبعيات؛ آخر دفعة 2026-09-11 200/200 (سايت ماب 252 → 52 مؤجّلة لليوم التالي)
type: project
originSessionId: 442cfa15-c621-4dae-a766-6b7ef6dde2d3
---

## آخر دفعة — 2026-09-11
- سايت ماب production: **252 URL**
- دُفع اليوم: **200/200 كلها Google:200** (شمل AI cluster كامل + universities + static)
- **52 URL مؤجّلة لبكرة 2026-09-12** (تجديد الحصّة ~10م رياض)
- الرئيسية عاد ISR (X-Vercel-Cache HIT, Age 2743s, Prerender:1)

---

**متى:** 2026-09-05 بعد جلسة تركيب استغرقت ساعة.

**البنية النهائية:**
- Service Account: `gsc-indexer@maqalat-org.iam.gserviceaccount.com` (Owner مؤكّد على sc-domain:maqalat.org)
- Key ID: `e9981d64ca3283ae32920996cb65bee5084b93b0` (client_id: 108651895955601729419)
- Env في `.env.local`: `GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON` (JSON على سطر واحد)
- سكربت: [scripts/ping_google_indexing.mjs](scripts/ping_google_indexing.mjs) — صفر تبعيات (crypto مدمج لتوقيع RS256 JWT)
- الأمر: `npm run index:ping`
- الحصّة: 200 URL/يوم (Google قاعدة صارمة)

**دفعة اليوم — 200 صفحة كلها Google:200:**
- الصفحة الرئيسية + `/en`
- ~180 مقال AR (من أصل 203)
- ~20 مقال EN (من أصل 25)
- صفحات هيكلية (about, tools, methodology…)
- **52 URL مؤجَّلة** لبكرة (10 مساء رياض تقريباً — تجديد الحصّة)

**الفخّ الحاسم (الذي كلّفنا 30 دقيقة):**
Google في تحديث 2024/2026 ألغى خيار «Owner» من قائمة **Add User** في Search Console لكل الأنواع (Domain و URL prefix). "Full user" **غير كافٍ** لـIndexing API — يُرجع `403: Failed to verify the URL ownership`.

**الحل**: بوّابة التحقّق الكلاسيكية القديمة `https://www.google.com/webmasters/verification/` لا تزال تعمل. من هناك يمكن إضافة service account كـ**Owner** مباشرة (يظهر «المالك» في UI الحديث بعدها).

**الفخّ الثاني (الذي تجنّبناه):**
Domain properties (sc-domain:) لا يمكن حتى إضافة service account لها كـOwner عبر الواجهة الحديثة — يجب استخدام البوّابة القديمة. Verified via delegated ownership.

**الفخّ الثالث (المُنقَذ منه):**
`.env.local` يجب أن يكون تحت `.gitignore` (`.env*` كافي). قبل كتابة JSON السرّي فحصنا gitignore صراحة.

**اختبار قبل الاستهلاك:**
قبل استهلاك الحصّة، اختبرنا بضربة واحدة (`https://maqalat.org/`) → 403 = مشكلة صلاحية، 200 = جاهز للحصّة كاملة. هذا وفّر علينا استهلاك يوم كامل على أخطاء.

**الأثر المتوقّع:**
- 24-72 ساعة: تحرّك «مكتشفة لم تُفهرس» في GSC
- 4 URLs الطازجة (اللي فُتحت اليوم من project_maqalat_universities_cluster.md) تدخل الفهرس أول
- الحصّة اليومية 200 تكفي لتغطية كل sitemap (252) في يومين

**العلاقة مع DealPulse:**
نفس النمط بالضبط في [seo_google_indexing_live.md] لكن الفخّ الجديد (Owner من UI مش موجود) لم يكن هناك في يوليو 2026. Google شدّد الواجهة الحديثة بين يوليو-سبتمبر.

---

## IndexNow (Bing/Yandex/DuckDuckGo/Brave) — 2026-09-05

**البنية:**
- المفتاح: `a0b71d61d91d435587162a4cebcf1efe` (من Bing Webmaster → IndexNow → Generate)
- ملف التحقّق: [public/a0b71d61d91d435587162a4cebcf1efe.txt](public/a0b71d61d91d435587162a4cebcf1efe.txt)
- سكربت: [scripts/ping_indexnow.mjs](scripts/ping_indexnow.mjs)
- الأمر: `npm run indexnow:ping`
- الميزة: بلا حصّة يومية، 252 URL في POST واحد على `api.indexnow.org/IndexNow`

**الفخّ الجديد الذي كلّفنا 15 دقيقة:**
middleware في next-intl يعترض `/{hexkey}.txt` ويعيد 404 HTML. الحل: أضفنا `[a-f0-9]{32}\\.txt` لقائمة الاستثناءات في [middleware.ts:15](middleware.ts#L15).

**فخّ ثانٍ (متوقّع، ليس خطأ):**
أول استدعاء يُرجع `403 SiteVerificationNotCompleted` — Bing يحتاج 5-30 دقيقة ليزور ملف المفتاح ويتأكّد. إعادة التشغيل بعد نصف ساعة تنجح.

**اختلاف عن Google Indexing:**
- Google: 200/يوم صارمة، Owner-verified، تحمي من العبث
- IndexNow: بلا حصّة عملية، مفتاح واحد بسيط، عدة محركات دفعة واحدة
- Google **لا** يشارك في IndexNow (لهذا نستخدم الاثنين معاً)
