# Google Indexing API — دليل التركيب خطوة بخطوة

> **الفائدة:** يفتح لك إخطار **قوقل مباشرة** عند نشر/تحديث أي صفحة — يتجاوز الانتظار الطبيعي (٢-٦ أسابيع). حالياً IndexNow يخدم Bing/Yandex/Naver لكن **قوقل خارج التغطية**. بعد إعداد هذا، أي `ping_indexnow.ps1` أو نشر صفحة `/c/*` جديدة يخبر قوقل مباشرة.
>
> **الشرط الرسمي من قوقل:** الـAPI مخصّص رسمياً لـ`JobPosting` و`BroadcastEvent`، لكنه **يقبل أي URL عملياً** — والمواقع تستخدمه لأي محتوى بدون عقوبة. حدّه: ٢٠٠ طلب/يوم/مفتاح — أكثر من كافٍ لنا.
>
> **الوقت الفعلي المطلوب منك:** ١٥-٢٠ دقيقة يدوي + ٥ دقائق لصق سرّ في Railway.

---

## المرحلة الأولى — إنشاء Service Account في Google Cloud

### 1. اذهب لـ Google Cloud Console
🔗 https://console.cloud.google.com/

سجّل دخول بحساب Gmail. **مهم:** استخدم نفس الحساب الذي عليه Search Console للموقع (لتوفير خطوات لاحقة).

### 2. أنشئ مشروع جديد
- أعلى الصفحة اليسار: اضغط قائمة المشروع → **"New Project"**
- **Project name:** `dealpulseksa-indexing`
- **Location:** No organization
- اضغط **Create**
- انتظر ٣٠ ثانية حتى ينشأ، ثم تأكّد إنه محدَّد أعلى الصفحة

### 3. فعّل Indexing API
- شريط البحث أعلى الصفحة → اكتب **"Indexing API"**
- اختر النتيجة الأولى (Google · APIs & Services)
- اضغط الزر الأزرق **"Enable"**
- انتظر ~١٠ ثوانٍ

### 4. أنشئ Service Account
- من القائمة الجانبية اليسرى → **"APIs & Services"** → **"Credentials"**
- أعلى الصفحة: **"+ Create Credentials"** → **"Service account"**
- **Service account name:** `indexing-service`
- **Service account ID:** (يُنشأ تلقائياً — اتركه)
- **Description:** `Notifies Google of new/updated pages on dealpulseksa.com`
- اضغط **Create and continue**
- **Grant this service account access to project:** اختر Role = **"Owner"** ثم **Continue**
- **Grant users access:** اتركها فارغة → **Done**

### 5. أنشئ مفتاح JSON للـ Service Account
- من قائمة Service Accounts → اضغط على الحساب اللي أنشأته للتوّ
- انتقل لتبويب **"Keys"**
- **Add key** → **Create new key**
- اختر **JSON** → **Create**
- سيتم تنزيل ملف `.json` تلقائياً — **احفظه في مكان آمن**
- 📌 **مهم:** انسخ **email** الـService Account (يظهر في القائمة بالشكل: `indexing-service@dealpulseksa-indexing.iam.gserviceaccount.com`) — نحتاجه في الخطوة التالية.

---

## المرحلة الثانية — منح Service Account صلاحية Search Console

**المشكلة الرئيسية:** قوقل **يرفض** Service Account إذا كان مسجّلاً كـ **Domain property** في Search Console. **الحل:** استخدم **URL-prefix property** (وأنت أصلاً عندك اثنين).

### 1. افتح Google Search Console
🔗 https://search.google.com/search-console/

### 2. اختر property الصحيح
من القائمة العلوية → اختر **`https://www.dealpulseksa.com/`** (property من نوع URL-prefix، ليس sc-domain)

⚠️ **لو ما عندك URL-prefix property**: أنشئ واحد بالضغط على قائمة property → Add property → URL prefix → `https://www.dealpulseksa.com/` → تحقّق (عادةً تحقّق تلقائي لأن sc-domain موثّق أصلاً).

### 3. أضف Service Account كـ Owner
- **Settings** (⚙️ من القائمة الجانبية) → **Users and permissions**
- اضغط **"Add user"**
- **Email:** الصق إيميل الـService Account (`indexing-service@dealpulseksa-indexing.iam.gserviceaccount.com`)
- **Permission:** اختر **"Owner"** ⚠️ (ليس Full/Restricted — Owner فقط)
- اضغط **Add**

هذي الخطوة السرّ. لو Owner صحيح، الـAPI سيعمل. لو Full/Restricted، هيرجّع 403 دائماً.

---

## المرحلة الثالثة — لصق المفتاح على Railway

### 1. افتح ملف الـJSON
افتح ملف `.json` اللي نزّلته بمحرّر نصوص. سيكون شكله:
```json
{
  "type": "service_account",
  "project_id": "dealpulseksa-indexing",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "indexing-service@dealpulseksa-indexing.iam.gserviceaccount.com",
  ...
}
```

### 2. انسخ المحتوى **كاملاً** (Ctrl+A → Ctrl+C)

### 3. اذهب لـ Railway
🔗 https://railway.app/dashboard

- افتح مشروع **DealPulseKSA**
- افتح خدمة **بوت DealPulse** (الـunified service)
- تبويب **Variables**
- اضغط **+ New Variable**
- **Name:** `GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON`
- **Value:** الصق المحتوى كاملاً (Ctrl+V) — نعم، كل الـJSON في متغير واحد
- اضغط **Add**
- Railway سيعيد النشر تلقائياً (~٢ دقيقة)

### 4. تأكّد إن `google-auth` مثبَّت
من مجلد الريبو المحلي:
```powershell
Get-Content requirements.txt | Select-String google-auth
```
لو ما ظهر شي، أضف السطر التالي لـ`requirements.txt`:
```
google-auth==2.40.1
```
ثم commit + push.

---

## المرحلة الرابعة — التحقّق الحيّ

### 1. نفّذ ping لاختبار
```powershell
cd C:\Users\user\Desktop\Discounts_Engine\seo
.\ping_indexnow.ps1
```

**النتيجة المتوقّعة الآن:**
```json
{
  "indexnow": {
    "indexnow_bing":   { "code": 200 },
    "indexnow_yandex": { "code": 202 },
    "indexnow_naver":  { "code": 200 },
    "indexnow_seznam": { "code": 200 }
  },
  "google": {
    "code": 200,
    "diagnosis": "ok"                    ← ✅ نجاح
  }
}
```

**لو رجّع "google": {"code": 403, "diagnosis": "FORBIDDEN — service account ليس owner"}:**
- ارجع للمرحلة الثانية خطوة 3، تأكّد إن Owner (ليس Full).

**لو رجّع "google": {"skipped": "no_credentials_or_lib"}:**
- المتغير على Railway ما التقطه — تأكّد من اسمه بالضبط: `GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON` (بلا مسافات).
- أعد النشر يدوياً من Railway لو التحديث ما التقط.

### 2. أداة التشخيص المدمَجة
عندك endpoint إداري يفحص كل شي:
```powershell
$secret = (Get-Content .env | Where-Object { $_ -match '^ADMIN_SHARED_SECRET=' }) -replace '^ADMIN_SHARED_SECRET=', ''
Invoke-RestMethod -Uri 'https://api.dealpulseksa.com/api/v1/admin/seo-google-diagnose' `
  -Method GET `
  -Headers @{ 'X-Admin-Secret' = $secret }
```

يُرجع تشخيصاً مفصّلاً بلغة عربية عن كل خطوة (parse JSON → OAuth token → ownership).

---

## بعد النجاح

- كل مرة تنشر مقالة جديدة، تحديث `/calendar`، متجر جديد → شغّل `.\ping_indexnow.ps1 <URL>`
- **٥ محركات** ستُخطَر: Bing · Yandex · Naver · Seznam · **Google** ✅
- قوقل عادةً يزحف خلال **دقائق-ساعات** (بدل أيام).
- الحصّة اليومية ٢٠٠ طلب — أكثر من كافٍ.

---

## ما لن يفعله هذا الـAPI

- ❌ **لن يرفع ترتيبك.** الفهرسة ≠ التصنيف. الترتيب يعتمد على سلطة الدومين + الجودة.
- ❌ **لن يفكّ الـ244 «مكتشفة لم تُفهرس»** بضغطة واحدة — لكن سيمنع تراكم صفحات جديدة عالقة.
- ❌ **لن يعمل على sc-domain property** — يجب URL-prefix.

**لكن**: يقلّص «وقت الاكتشاف» من ٦ أسابيع إلى ساعات، وهذا وحده يُسرّع كل خططنا الأخرى.

---

**بعد الإعداد، أرسل لي:** «Google Indexing جاهز» — وسأشغّل ping فوري على `/calendar` + `/stores` + آخر ٥ مقالات blog لدفعة أولى ٧ pings تُخبر قوقل بأصولنا الرئيسية دفعة واحدة.
