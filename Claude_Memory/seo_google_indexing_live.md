---
name: seo-google-indexing-live
description: 2026-07-08 Google Indexing API فُعِّل بنجاح؛ ٢٠٠ صفحة أُخطر عليها قوقل مباشرة في يوم واحد (استنزاف الحصّة اليومية كاملة)
type: project
originSessionId: bf501e24-1a22-42b8-8227-c51a7b2dd362
---
**متى:** 2026-07-08 (نهاية جلسة عمل مكثّفة).

**الإنجاز:** Google Indexing API الحيّ (خامس محرك بعد Bing/Yandex/Naver/Seznam) — قوقل يزحف الصفحات المُخطَر عليها خلال ساعات بدل أسابيع.

**البنية النهائية:**
- Service Account: `gsc-indexer@dealpulseksa-aab18.iam.gserviceaccount.com` (مالك موثّق على Search Console)
- Railway env: `GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON` = JSON صحيح لخدمة gsc-indexer
- Endpoint حيّ: `POST /api/v1/admin/seo-resubmit-url?url=<URL>`
- سكربت PowerShell: `seo/ping_indexnow.ps1`

**دفعة اليوم — ٢٠٠ صفحة كلها Google:200:**
- ٦ صفحات هَب: `/calendar`, `/stores`, `/blog`, `/trending`, `/deals`, `/`
- ٢٤ صفحة SEO landing (`/c/*` كاملة)
- ٣٣ صفحة تصنيف (`/category/*` كاملة)
- ١٣٧ مقالة blog (من ٦٨٦ الكلّي)

**الحصّة اليومية:** ٢٠٠ ping/يوم — استُهلكت كاملةً.

**دروس التركيب:**
1. **الفخّ الأول (parse_json):** JSON على Railway كان تالفاً — الحقل `client_email` مكتوب مرّتين. الاستبدال بـJSON نظيف حلّها.
2. **الفخّ الثاني (ownership):** Service Account على Railway كان `indexer-bot` بينما مالك Search Console `gsc-indexer` — عدم تطابق يسبب 403 حتى مع JSON صحيح. الحل: JSON لخدمة تطابق مالك Search Console.
3. **التشخيص:** `/api/v1/admin/seo-google-check` يُرجع 5 حالات محدّدة (`credentials/oauth/ownership/parse_json/ready`) — استخدمها قبل أي محاولة إطلاق.

**الأثر المتوقّع:**
- ٢٤-٧٢ ساعة: تحرّك أرقام «مكتشفة لم تُفهرس» في GSC (٢٤٤ → أقل).
- الحصّة اليومية ٢٠٠ ping تكفي لتغطية ٦٨٦ blog + ٢٤٤ عالقة في ~٥ أيام.

**سكربت الإطلاق اليومي (يُشغَّل يدوياً كل صباح):**
```powershell
# استخدم seo/ping_indexnow.ps1 <URL>
# أو batch عبر Invoke-RestMethod loop على sitemap
```

**قنوات مؤجَّلة بإذن المالك:**
- Telegram broadcast /calendar لـ٢٤٠ مستخدم — ينتظر «نعم»
- IG reels engine — يحتاج تشخيص العطل، ينتظر «نعم»
- GSC API per-query — يحتاج setup ١٠ دقائق من المالك
- ميزانية أدوات (Ahrefs/SEMrush/Apollo) — قرار مالي

يخدم: [[seo-ai-visibility-optin]] · [[seo-owned-channels-pivot]] · [[seo-indexation-status]] · [[seo-pr-blitz-kit]].

---

## ⚠️ ٢٠٢٦-٠٨-٢٦ — قناة قوقل ساقطة بـ403، والـIndexNow وحدها تعمل

عند دفع ٨ روابط جديدة (عنقود الضيافة + صفحة قصر الاواني + هَب التقسيط) عبر
`POST /api/v1/admin/reindex-urls`، رجع **كل رابط**:

- `indexnow_bing: 200` ✅
- `indexnow_yandex / naver / seznam: 422` (رفض، ليس 202)
- `google: 403` مع تشخيص الخادم نفسه: **«service account ليس owner على الـproperty
  في Search Console»**

يعني ملكية `gsc-indexer@dealpulseksa-aab18.iam.gserviceaccount.com` **سقطت** بعد أن
كانت موثّقة ٢٠٢٦-٠٧-٠٨. الحل المذكور في التشخيص: إعادة التوثيق بـDNS TXT أو ملف HTML
ثم إعادة إضافة الحساب مالكاً.

**الأثر العملي:** أي محتوى جديد يصل Bing فوراً ولا يصل قوقل إلا بالزحف الطبيعي.
وهذا يرفع من قيمة [[ai_citation_channel]] مؤقّتاً (Copilot يقرأ من فهرس Bing)،
لكنه يؤخّر النقر العضوي. **لا تفترض أن الدفع نجح — اقرأ `google.code` في الردّ.**
