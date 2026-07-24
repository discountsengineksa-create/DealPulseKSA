# تقرير الفحص الأمني — DealPulse KSA

**التاريخ:** 2026-07-24 · **الفاحص:** مراجعة دفاعية (Claude) بتفويض المالك · **النطاق:** الويب (Next.js/Vercel) + الـAPI (FastAPI/Railway) + القاعدة (PostgreSQL) + المصادقة (JWT/bcrypt) + رؤوس الأمان.

> **المنهج:** مراجعة كود ثابتة + فحص إعدادات حيّة (رؤوس، CORS، كشف مسارات) — **بلا** هجوم فعّال أو DoS على الإنتاج.

---

## 1) الخلاصة التنفيذية

**التقييم العام: قويّ. 🟢** الموقع مبنيّ بوعي أمني حقيقي — لا توجد ثغرة حرجة أو عالية الخطورة مرصودة. كل فئات الهجوم الكبرى (حقن SQL، تجاوز المصادقة، IDOR، تسريب الأسرار، XSS من المستخدم) **مغلقة**. أُصلحت الثغرة الوحيدة القابلة للاستغلال (كشف توثيق الـAPI)، وبقيت توصيتان دفاع-عميق اختياريتان.

| # | المجال | النتيجة | الخطورة |
|---|---|---|---|
| 1 | CORS + الوسطاء | ✅ محكم | — |
| 2 | المصادقة (JWT/bcrypt) | ✅ سليم | — |
| 3 | مصادقة الأدمن (X-Admin-Secret) | ✅ سليم | — |
| 4 | حقن SQL | ✅ بارامتري بالكامل | — |
| 5 | IDOR / التفويض | ✅ الهوية من التوكن | — |
| 6 | تحديد المعدّل (Rate limiting) | ✅ شامل (Redis) | — |
| 7 | رؤوس الأمان | ✅ مكتملة | — |
| 8 | تسريب الأسرار | ✅ لا شيء للواجهة | — |
| 9 | XSS | ✅ لا مدخلات مستخدم | — |
| 10 | الاعتماديات (CVEs) | ✅ حديثة/مرقّعة | — |
| 11 | كشف `/docs` + `/openapi.json` | 🔧 **أُصلح** | منخفضة |
| 12 | CSP (وضع التنفيذ) | 🔧 **نُشِر** (قيد اختبار المتصفّح لصفحة الدخول) | متوسطة (إعلامية) |
| 13 | Trusted Types | ⛔ غير موصى (يكسر JSON-LD) | — |

---

## 2) التفاصيل

### 2.1 CORS + الوسطاء ✅
- `allow_origins` مقفول على قائمة صريحة (لا `*`)، مع فحص وقت-تشغيل يرفض `*` مع `allow_credentials=True`.
- `X-Admin-Secret` **غير** ضمن `allow_headers` — سرّ الأدمن لا يُستخدم cross-origin أبداً.
- طرق محدّدة، رؤوس محدّدة. أصل `"null"` مسموح عمداً لـTelegram WebApp (تنازل واعٍ، خطر منخفض).

### 2.2 المصادقة ✅
- **JWT: `HS256` مع `algorithms=[HS256]` صريح في decode** → هجوم `alg=none` **مرفوض**، ولا الْتباس خوارزميّة.
- `JWT_SECRET` **إلزامي** (يرفع خطأ لو غائب)، وتحذير لو < 32 محرف.
- كلمات المرور بـ **bcrypt** (gensalt، one-way).
- `get_current_user` يشتقّ الهوية من **حمولة التوكن الموقّعة** فقط.

### 2.3 مصادقة الأدمن ✅
- `X-Admin-Secret` يُقارَن بـ **`secrets.compare_digest`** (مقاوم لهجمات التوقيت). كل endpoints الأدمن محميّة + محدودة المعدّل.

### 2.4 حقن SQL ✅
- **138 استعلاماً — كلها بارامترية (`%s` / `%(name)s`)**؛ صفر `execute(f"…")` بمدخلات مستخدم.
- الـf-string SQL (في `coupons.py`) يُقحِم فقط قيماً **مُتحكَّماً بها من الخادم** (جملة SELECT ثابتة، `lang` من `Literal["ar","en"]`، شرط القناة من مقارنة ثابتة)؛ مدخلات المستخدم (slug/channel/limit/q) تمرّ **بارامترياً**.

### 2.5 IDOR / التفويض ✅
- endpoints بيانات المستخدم كلها `/me/...` وتشتقّ `web_user_id = user["id"]` **من التوكن**، لا من الطلب. لا يوجد أي endpoint يقبل مُعرّف مستخدم من الطلب. المستخدم يصل/يعدّل بياناته فقط.

### 2.6 تحديد المعدّل ✅
- **slowapi + Redis** (يشتغل عبر كل نسخ Railway). تغطية شاملة: register/login/forgot/reset/change-password/delete-account/verify، admin، go-redirect، social-ingest، وكل track (search 30/دق، request-code 5/دق، report 3/دق…). دفاع فعّال ضد التخمين والإغراق وتضخيم العدّادات.

### 2.7 رؤوس الأمان ✅ (حيّة على الإنتاج)
```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
Cross-Origin-Opener-Policy: same-origin-allow-popups     ← أُضيف في هذه المراجعة
```

### 2.8 تسريب الأسرار ✅
- الواجهة تستخدم `NEXT_PUBLIC_*` فقط — **صفر أسرار خادم** في حزمة العميل. رسائل الخطأ لا تسرّب stack traces (`/openapi.json` كان يردّ "Internal Server Error" عامّة).

### 2.9 XSS ✅
- كل `dangerouslySetInnerHTML` على **JSON-LD (بيانات خادم)** أو **محتوى مدوّنة مؤلَّف بالريبو** — **لا مدخلات مستخدم**. React يهرّب الباقي افتراضياً.

### 2.10 الاعتماديات ✅
- حديثة/مرقّعة: `python-multipart 0.0.28` (> CVE-2024-53981)، `starlette 1.0`، `PyJWT 2.x`، `cryptography 48`، `bcrypt 5`، `pillow 11.1`، `requests 2.32.3`.

---

## 3) الإصلاحات والتوصيات

### 🔧 أُصلح الآن — كشف `/docs` + `/openapi.json` (خطورة منخفضة)
كان Swagger UI (`/docs`) و`/openapi.json` مكشوفَين (200) — استطلاع مجاني لمخطّط كل الـendpoints. **الحل (منشور):** إغلاقهما بالإنتاج افتراضياً، ويُفتحان محلياً بـ`EXPOSE_DOCS=1`.

### 🔧 نُشِر — CSP في وضع التنفيذ (دفاع-عميق ضد XSS)
أُضيف CSP مفروض في `next.config.mjs` يحصر السكربت/الاتصال/الإطار/الصور/الفيديو على مصادر معروفة (API على `api.dealpulseksa.com`، Cloudinary، Firebase OTP/reCAPTCHA، Vercel Analytics)، مع `'unsafe-inline'/'unsafe-eval'` لسكربتات Next الداخلية (بلا nonce حفاظاً على التصيير الثابت/ISR).

**تحقّق آليّ (منجَز):** الرئيسية تُصيَّر 200، و**كل مورد `src=` من الموقع أو Cloudinary فقط — صفر مورد خارجي محجوب**. دومينات المتاجر/السوشال المرصودة كلها روابط `href` (لا يحجبها CSP).

**متبقٍّ — اختبار متصفّح يدوي واحد:** صفحة **تسجيل الدخول/OTP** (Firebase reCAPTCHA) — النطاقات القياسية (`*.firebaseapp.com` / `google.com` / `gstatic.com` / `googleapis.com`) مُدرَجة، لكن تأكيدها يحتاج فتح المتصفّح + Console. لو ظهر `Refused to … CSP` → يُضاف المصدر أو يُرجَع CSP.

### ⛔ غير موصى — Trusted Types
يتطلب `require-trusted-types-for 'script'` الذي **يكسر `dangerouslySetInnerHTML`** المستخدَم لحقن JSON-LD (سكيما SEO). المخاطرة > الفائدة.

### 🧱 «الجدار الناري» على الحافة — (يحتاج لوحات المالك، لا يُنفَّذ من الكود)
حماية التطبيق قوية؛ لطبقة حافة (WAF/DDoS) — مقسومة حسب المضيف:

**الويب (Vercel):** استخدم **جدار Vercel المدمج** (Security/Firewall) — بلا تعارض CDN مزدوج: Attack Challenge Mode + قواعد WAF مُدارة + Rate limiting. (Vercel يوفّر DDoS أساسي أصلاً.)

**الـAPI (`api.dealpulseksa.com` → Railway):** هنا Cloudflare يضيف قيمة حقيقية (Railway بلا WAF):
1. Cloudflare → `SSL/TLS = Full (Strict)` ⚠️ (وإلا redirect loop).
2. DNS → سجلّ `api` → السحابة **برتقالية (Proxied)**.
3. Security → WAF → **Managed Rules + OWASP Core Ruleset**.
4. Security → Bots → **Bot Fight Mode**.
5. Rate limiting rule (مثلاً >100/دقيقة/IP → تحدّي).

> الـAPI محمي أصلاً بـrate limiting شامل (slowapi+Redis)، فهذي طبقة إضافية لا ضرورة قصوى.

---

## 4) ملاحظات تشغيلية مستمرّة
- تأكّد أن `JWT_SECRET` و`ADMIN_SHARED_SECRET` كلاهما ≥ 32 محرفاً عشوائياً (لا يُشتقّان، لا يُعاد استخدامهما).
- راقب `security_blacklist` / `security_threats` (Cyber Shield) دورياً.
- حدّث الاعتماديات ربعياً (`pip list --outdated` / `npm audit`).
- لا تُفعّل `EXPOSE_DOCS=1` على الإنتاج.

**المحصّلة:** لا يوجد ما «ينهار» بسهولة — الأساس متين. أكبر ترقية متبقّية هي جدار Cloudflare على الحافة.
