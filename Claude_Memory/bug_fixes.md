---
name: Bug Fixes Log
description: All bugs fixed in the project, what they were, and the solution — so they're never reintroduced
type: project
originSessionId: 3eb16deb-09fb-42ac-aa86-1b1afa492099
---
## Fixed Bugs (June 2026)

### 17. صفحة /blog تتجاوز سقف زحف Googlebot (2MB) + رابطان داخليان 404 (dealpulseksa-web)
- **What (تدقيق Ahrefs 2026-06-29):** أخطاء حمراء جديدة — «Page size exceeds 2MB» + «HTML file size too large» على `/blog` (كان **2.75MB**)؛ و«404 page»×2 + «Page has links to broken page»×2.
- **Why:** (1) `app/blog/page.tsx` يجلب `getAllPosts()` ويمرّر **كائنات BlogPost كاملة** (فيها `body` ضخم لكل مقال) إلى `BlogList` وهو **كومبوننت عميل ('use client')** — فكل ما يُمرَّر لكومبوننت عميل يُسلسَل داخل HTML/RSC payload؛ 110 مقالاً × body = 2.75MB، مع أن البطاقات تعرض العنوان/المقتطف/التصنيف فقط. (2) رابطان في «روابط ذات صلة» داخل `lib/blog.ts` يشيران لـ slugs خاطئة: `aliexpress-car-devices-accessories-guide` (الصحيح `-hub`) و`aliexpress-seat-steering-covers-guide` (الصحيح بلا `-guide`).
- **Fix (web commit d88ec10):** page.tsx يمرّر حقول البطاقة فقط (`slug/title/excerpt/category/readTime/date` + _en) بلا `body` → /blog أقل من 2MB بكثير. وتصحيح الـslugين.
- **Lesson:** أي كائن يُمرَّر كـprop لكومبوننت `'use client'` يُسلسَل بالكامل في الصفحة — مرّر فقط الحقول المعروضة، لا الكائن الخام (خاصة حقول النص الطويل). الروابط الداخلية يجب أن تطابق slugs المقالات الفعلية حرفياً. للعثور على الصفحات الثقيلة/الروابط المكسورة: ازحف `sitemap.xml` وقِس الأحجام واستخرج الروابط برمجياً (لا تخمّن). يرتبط بـ [[seo_indexation_status]] و[[content_programmatic_strategy]].

### 16. رفع صور الثيمات/الشعار في الداشبورد يفشل (أيقونة خطأ حمراء) خلف بروكسي Railway (.streamlit/config.toml)
- **What:** في صفحة «➕ أضف ثيماً» (dashboard.py ~14196) يظهر خطأ أحمر على الملف **داخل أداة `st.file_uploader` نفسها — قبل الضغط على «احفظ الثيم»** (ملف 1.4MB صغير، PNG، أقل بكثير من سقف 200MB). لا علاقة له بكود النموذج ولا بـ Cloudinary (رفع Cloudinary يجري بعد submit فقط).
- **Why:** نقطة رفع الملفات في Streamlit `/_stcore/upload_file` محميّة بتوكن XSRF. خلف بروكسي Railway يفشل تطابق/تنتهي صلاحية التوكن → الرفع يُرفض → «فشل الرفع». الملفّ لا يصل الخادم أصلاً.
- **Fix (commit cb27b9f):** في `.streamlit/config.toml` ضبط `enableXsrfProtection = false` مع إبقاء `enableCORS = true` (إبقاء CORS يمنع «التحذير الأحمر» الذي يظهر فقط عند CORS=false، ويحافظ على حماية cross-origin). يلزم إعادة نشر خدمة الداشبورد على Railway ليسري. **مقايضة مقبولة بقرار صريح من المستخدم**: الداشبورد للمشرف فقط فخطر XSRF منخفض. **لا تُعِد تفعيل `enableXsrfProtection` ولا تضع `enableCORS=false`.**
- **Lesson:** أيقونة الخطأ الحمراء على ملف في `st.file_uploader` = فشل وصول الملف للخادم (نقطة الرفع)، لا حجم/نوع. على Streamlit المستضاف خلف بروكسي، الشكّ الأول = XSRF.

### -0.7. «الثيم يظهر على الجوال لا على الكمبيوتر» = كاش متصفّح قديم، لا عطل كود (dealpulseksa-web)
- **What:** بعد تفعيل ثيم مناسبة، تظهر خلفية الثيم على الجوال لا على سطح المكتب (يظهر الووترمارك الافتراضي/الشعار بدل الثيم).
- **Why:** لا عطل. فُحصت السلسلة كاملة وكلها سليمة: DB (is_active=True + 4 روابط)، الـAPI `/api/v1/coupons/site-theme` يرجّع 200 + الروابط، الصور PNG سليمة، `SiteThemeBackground.tsx` يضبط `data-site-theme="on"`+المتغيّرات على `<html>` بلا فرق جوال/سطح، والـCSS المنشور فعلاً صحيح (قاعدة سطح المكتب `--theme-desktop` **خارج أي media query**، الجوال داخل `@media(max-width:640px)`). الدليل: ظهور شعار DP المائي في صورة سطح المكتب = الافتراضي ما زال يُرسم = `data-site-theme` لم يُفعَّل على متصفّح الكمبيوتر (كاش قديم/إضافة حظر). حلّه تحديث قسري (Ctrl+Shift+R)/نافذة خفية — وقد حلّ فعلاً.
- **Lesson:** قبل تعديل كود الثيم/الواجهة، أثبت السلسلة (DB→API→صور→JS→CSS المنشور). فرق «جوال يعمل/سطح لا» مع قاعدة CSS لسطح المكتب خارج media query = مستحيل أن يكون CSS → بيئي (كاش/إضافة). لا تعديلات تخمينية — راجع [[feedback_regression_audit]] و[[feedback_no_dead_code]]. تفاصيل نظام الثيم في [[story_system_design]] (نفس مكوّن الخلفية/المتغيّرات).

### 15. كل صفحات الموقع فيها "schema.org validation error" (dealpulseksa-web/lib/seo/schema.ts)
- **What:** Ahrefs + Semrush رصدا «Structured data schema.org validation error» على **130 صفحة = كل الصفحات** (الـ@graph العام يُحقن بكل صفحة من app/layout.tsx). الجلسة السابقة (2026-06-21) ظنّتها **false-positive من Ahrefs** — كان استنتاجاً خاطئاً.
- **Why:** `localBusinessNode()` نوعها `'@type': 'OnlineBusiness'` — وهو ابن **Organization** لا LocalBusiness — لكنها كانت تحمل `priceRange: 'Free'` و `currenciesAccepted` وهما **خاصّتان معرّفتان حصرياً على LocalBusiness** (مؤكّد من schema.org/priceRange: "Used on these types: LocalBusiness"). خاصّية على نوع لا تنتمي إليه = خطأ تحقّق.
- **Fix (web commit 6a9d5ed):** حذف الخاصّتين من العقدة. إشارة المجانية محفوظة أصلاً في `softwareApplicationNode().offers.price=0`. النوع OnlineBusiness صحيح (منصّة أونلاين بلا فرع) فلا داعي لتغييره ولا لاختلاق عنوان شارع.
- **Rule:** لا تضع `priceRange`/`currenciesAccepted` (أو أي خاصّية LocalBusiness-only) على نوع ليس LocalBusiness. للتحقق من خطأ Schema استعمل **Google Rich Results Test / schema.org validator** لا اجتهاد Ahrefs. schema.ts راكم خطأين تحقّق (AggregateRating المصطنع سابقاً + هذا) — افحص نوع↔خاصّية قبل أي إضافة. يرتبط بـ [[seo_indexation_status]] و [[seo_white_hat_only]].

### -0.5. منتقيات التاريخ في كل أقسام التحليل تحبس عند UTC/آخر يوم بالبيانات (dashboard.py)
- **What:** بعد منتصف ليل الرياض لا تظهر بيانات اليوم في أقسام التحليل (مثال: نسخة زائر مجهول مسجّلة فعلاً 2026-06-22 00:18 لم تظهر في «تحليل المتاجر»)، و«تحليل الأقسام» يحبس المنتقي عند آخر يوم فيه حركة (16) فلا يمكن اختيار اليوم (22).
- **Why (سببان):** (1) معظم المنتقيات `max_value=date.today()` و`date.today()` ترجع توقيت **الخادم** = UTC على Railway = يوم 21 عند 00:20 الرياض، فبيانات الرياض (يوم 22، بعد التحويل بـ`_ksa_dt`/`AT TIME ZONE`) تطلع خارج الحد وتختفي. (2) «تحليل الأقسام» كان `max_value = df_views["adate"].max()` = أحدث تاريخ في البيانات لا اليوم.
- **Fix (commit a62d3eb):** مساعدان صريحان `ksa_today()`/`ksa_now()` (UTC+3 عبر `datetime.now(tz)`، مستقلّان عن منطقة الخادم والمنصّة) + تثبيت منطقة العملية `os.environ['TZ']='Asia/Riyadh'`+`tzset()` (Linux فقط) كشبكة أمان. كل منتقيات التحليل تعتمد `ksa_today()` للحدّ الأقصى؛ و«تحليل الأقسام» `max_value=ksa_today()` مع إبقاء بداية النطاق من أقدم تاريخ. تحقّق: `ksa_today()=2026-06-22` مقابل UTC=2026-06-21.
- **Rule:** في الداشبورد (يعمل على Railway=UTC) لا تستخدم `date.today()`/`datetime.now()`/`pd.Timestamp.today()` لأي حدّ/افتراضي تاريخ — استخدم `ksa_today()`/`ksa_now()`. ولا تجعل `max_value` = أقصى تاريخ في البيانات (يحبس اختيار اليوم) — اجعله اليوم (الرياض). يكمّل [[bug_fixes]] entry -1.5 (عرض الوقت) ويرتبط بـ [[web_login_gate_model]] (تتبّع الزائر المجهول كان سليماً — المشكلة في حدّ التاريخ لا التسجيل).

### -1. Story analytics showed copies/clicks as ZERO despite being tracked (dashboard.py, 🎬 تحليلات الستوري)
- **What:** «عدد_النسخ» و«عدد_الزيارات» = 0 لكل الصفوف رغم أن action_logs فيها أحداث copy_coupon/click_link مع story_view_id صحيح. التتبّع (web + miniapp) كان شغّالاً طول الوقت — العطل في عرض الداشبورد فقط.
- **Why:** الربط النهائي `agg LEFT JOIN acts USING (web_user_id, tg_user_id, store_id)`. صفوف الموقع فيها tg_user_id=NULL وصفوف الميني فيها web_user_id=NULL، و`NULL = NULL` ليس TRUE في SQL (USING يستخدم مساواة) → لا يطابق أي صف → COALESCE→0.
- **Fix:** استبدال USING بربط صريح `IS NOT DISTINCT FROM` على web_user_id و tg_user_id (+ store_id =). تحقّق حيّ: acts=12 نسخة/3 نقرات؛ الربط المكسور=0/0؛ بعد الإصلاح=12/3.
- **Rule:** أي JOIN على مفاتيح قد تكون NULL (هوية web XOR bot) استخدم `IS NOT DISTINCT FROM` لا USING/`=`. لا تشخّص «لا يُحسب» كعطل تتبّع قبل فحص استعلام العرض — راجع [[feedback_regression_audit]].
- **Also (نفس الجلسة):** miniapp story: نسخ الكود pointer-events:auto على .s-code، زيارة الستوري تفتح رابط الأفلييت مباشرة (لا صفحة المتجر)، إيقاف الفيديو عند الإغلاق، تأكيد نعم/لا لبلاغ الكود. الموقع: زر زيارة الستوري يفتح الأفلييت مباشرة. ملاحظة: الميني-ويب يُخزَّن بكاش تيليجرام بقوة — يلزم إغلاق/فتح كامل لرؤية التحديث.

### -2. الموقع: تصل المشاهدات وتُسقط النسخ/النقر (sendBeacon cross-origin)
- **What:** على الموقع، مشاهدات الستوري (logStoryView) تُسجَّل لكن copy_coupon/click_link لا تصل /track إطلاقاً.
- **Why:** `trackAction`/`trackCategoryView` كانت تستخدم `navigator.sendBeacon` بـ `Content-Type: application/json` عبر النطاقات (الموقع→api.dealpulseksa.com). JSON ليس content-type آمن لـ CORS فيتطلّب preflight، وsendBeacon لا يتعامل مع preflight → يُسقط الطلب بصمت. logStoryView كان يستخدم fetch+keepalive (لذا وصل).
- **Fix:** توحيد كل التتبّع على `fetch(..., {keepalive:true})` (lib/api.ts). القاعدة: لا sendBeacon لطلبات JSON عبر النطاقات — استخدم fetch+keepalive.

### -1.5. التوقيت يُعرض UTC بدل الرياض (+3)
- **What:** «آخر_مشاهدة» في تحليلات الستوري (وغيرها) تظهر متأخّرة 3 ساعات.
- **Why:** أعمدة `action_time`/`viewed_at` نوعها `timestamp without time zone` وتُخزَّن **UTC**؛ العرض الخام = UTC. (trend_snapshot.py يضيف +3 يدوياً — يؤكد العُرف.)
- **Rule:** كل العرض/الحساب الزمني للمستخدم بتوقيت الرياض = UTC + 3 (أو `AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Riyadh'`). التخزين يبقى UTC. لا تخلط (لا تخزّن الرياض في عمود وUTC في آخر).

### 0. Inflated "إجمالي العملاء" — linked user double-counted (dashboard.py, تحليل المستخدمين)
- **What:** tab «الأرقام الكبرى» showed `grand_total = bot_total + web_total`, double-counting every linked person (web user whose telegram_username matches a bot username). Also «المستفيدون فعلياً» did `COUNT(DISTINCT user_id)` mixing web.id and telegram_id namespaces.
- **Why:** A linked customer is ONE known person; counting twice = fake numbers that erode company trust.
- **Fix:** Built unified `df_persons` model (one row per canonical person) computed once before the tabs; every person-count (total/active/new/idle/beneficiaries/linked/web_only/bot_only/grand_unique) derives from it so tabs reconcile. Linked = 1, with a «القناة» column showing where they use us. joined=LEAST(first appearance), last_seen=GREATEST.
- **Rule:** NEVER `bot_total + web_total` for unique users, and NEVER `COUNT(DISTINCT user_id)` across mixed web/bot sources — always dedup via the linkage (web.telegram_username = bot.username).
- **Commit:** 0f56156 · verified live: 11 inflated → 10 unique.
- **Still pending (next steps):** Cohort denominator uses "active in month 0" not intake size (can exceed 100%); verify `action_logs.user_id` writer for web rows; tab still labeled «📈 LTV» though LTV removed; geo `نقرات*0.5` arbitrary coefficient.

## Fixed Bugs (May 2026)

### 1. NameError: IDLE_TIMEOUT_MINUTES (deal_pulse_bot.py:1644)
- **What:** Startup print statement referenced deleted variable
- **Why:** Variable renamed to IDLE_WARN_MINUTES + IDLE_KICK_MINUTES during two-stage idle refactor
- **Fix:** Updated print to use the two new variables
- **Commit:** 0d64488

### 2. Connection Leaks in Dashboard (dashboard.py — 36 call sites)
- **What:** `conn = get_conn()` called in 36 pages without `try/finally`
- **Why:** Exception mid-page skips `conn.close()`, connection never returns to pool
- **Fix:** Added `__del__` to `_PooledConn` as automatic safety net — GC returns connection to pool if `close()` is never called. Also added `_closed` flag (prevents double-return), and `__enter__`/`__exit__` for context manager support
- **Commit:** 6a70491

### 3. _lang_cache No TTL (deal_pulse_bot.py)
- **What:** Language cache stored `lang` string with no expiry
- **Why:** User changes language → old value stays cached forever
- **Fix:** Cache now stores `(lang, timestamp)` tuple; TTL = 300s (5 min)
- **Commit:** 409fc22

### 4. _idle_warned/_idle_kicked Memory Leak (deal_pulse_bot.py)
- **What:** Sets grow forever — users who quit the bot remain in sets
- **Why:** Only discarded on new activity; users who never return accumulate
- **Fix:** Each `check_idle_users()` cycle computes `active_window = set(warn_ids) | set(kick_ids)` and prunes both sets to that window
- **Commit:** 409fc22

### 5. inferred_device Wrong Logic (deal_pulse_bot.py)
- **What:** `is_premium == True → 'iPhone'`, else → 'Android'`
- **Why:** Telegram Premium has no relation to device type; pollutes analytics
- **Fix:** Always store `'Telegram'` — honest neutral value
- **Commit:** 409fc22

### 6. Auth Router Not Registered (api/main.py)
- **What:** `/api/v1/auth/*` endpoints returned 404
- **Why:** `auth` router was imported but never added with `app.include_router()`
- **Fix:** Added `app.include_router(auth.router, prefix="/api/v1")`
- **Commit:** 12fc211

### 7. Website Analytics "server closed connection" (dashboard.py)
- **What:** All 5 tabs in "تحليل الموقع" page failed with PostgreSQL connection error
- **Why:** Single shared connection across tabs — one tab error corrupted the whole connection
- **Fix:** Each tab uses its own `_web_conn()` with `autocommit=True` in isolated `try/except/finally`
- **Session:** Previous conversation

### 8. Social broadcast: Meta platforms failed after logo-sizing change (api/social/image_specs.py)
- **What:** After adding per-platform Cloudinary logo sizing, Facebook/Instagram/Threads broadcasts started failing (HTTP 400) while Telegram/Discord still worked
- **Why:** `cloudinary_variant()` defaulted to `f_webp`. Telegram/Discord accept WebP but **Meta Graph API rejects WebP** (IG content-publish accepts JPEG only; FB `/photos` and Threads same). This was a regression — before the change the raw logo URL (PNG/JPG) was sent and Meta accepted it.
- **Fix:** Changed `fmt` default from `webp` to `jpg` — JPEG is accepted by every platform. **Do NOT reintroduce WebP** for image delivery to Meta platforms even to save bandwidth.
- **Commit:** d3dc77a
- **Note:** X failing separately = HTTP 402 CreditsDepleted (paid X API plan required, not a code issue).

### 9. City data was fake-default + mini-web clicks double-counted (analytics pipeline)
- **What:** Store analysis showed Telegram user city = "الرياض" for everyone; mini-web clicks were both double-logged and mis-tagged as "web".
- **Why (gotchas to remember):**
  - `bot_users.city` is a **language-default** ('الرياض' set on language pick, deal_pulse_bot.py ~1413), NOT the user's real city. Never present it as real geo.
  - **Real city comes only from IP** = `action_logs.city`, populated by the Cloudflare Worker (`x-dp-*` headers) at **click** time via the `/go/{slug}` redirect. Clicks → `/go` (carry geo); copies → `/track` (carry geo from webview). Bot copies (logged in-app via `log_action`) have NO geo.
  - Mini-web (`miniapp.html`) was firing BOTH `trackEvent('click_link')` (source `telegram_miniapp` via /track) AND opening `/go` (which logged again as 'web') → double count.
  - `go.py` collapsed every non-bot source to "web" (`source = "bot" if s=="bot" else "web"`).
- **Fix:** dashboard city = `action_logs.city` (geo) for all sources, resolved per-user from their geo-bearing (click) events; dropped `bu_city`. `go.py` now maps `s=miniapp → 'telegram_miniapp'` (+ challenge preserves `s`). `miniapp.html` `/go` link carries `?s=miniapp` and only `trackEvent`s clicks for non-`/go` (raw) links to avoid double count.
- **Bot city — SOLVED (the chosen method):** Telegram hides location, so bot user city is captured from **IP at link-click via `/go`**. The bot's open-store button now points to `{_GO_BASE}/go/{cloaked_slug}?s=bot&u={telegram_id}` (deal_pulse_bot.py `handle_link_click`), and `go.py` reads `u` → stores it as the click's `user_id` (was hardcoded `None`) so the IP-derived city attaches to the specific user. Removed the in-app `log_action('click_link')` + `increment_link_clicks` when routing via /go (they're done server-side) to avoid double-count; kept them only for the raw-link fallback (stores without cloaked_slug). `_GO_BASE` = `GO_BASE_URL` → `WEBHOOK_BASE_URL` → `API_BASE_URL`.
- **Operational dependency:** geo only fills if `_GO_BASE` resolves to the domain **behind the Cloudflare Worker** (same host the miniapp/website use for /go). Bot clicks now have user_id=telegram_id AND city; miniapp /go links also pass `&u={tgUserId}`.

### 10. CRITICAL GOTCHA — local dashboard reads a different DB than prod (localhost vs Railway)
- **What happened:** User reported a store («نمشي») they added wasn't showing in تحليل المتاجر, and جدول الكوبونات crashed with `column "source_platform" does not exist`. I connected to `localhost` directly and WRONGLY concluded "the add INSERT fails / store never saved". The user corrected me: «نمشي» was saved 6× and live everywhere (bot/mini/web/social).
- **Root cause (verified on prod):** The dashboard's `_get_pool()` (dashboard.py ~699) uses `DATABASE_URL` if set, else `DB_*` env vars. The local `.env` had **no `DATABASE_URL`** → dashboard read **localhost** = a STALE/test DB (16 dummy stores like '1','2','999','تجربة الترند'; `source_platform` column missing). The REAL data lives in **Railway prod** (`turntable.proxy.rlwy.net/railway`, held in `.env` as `MIGRATION_DATABASE_URL`): **25 stores incl. نمشي ×6, and `source_platform` EXISTS there** (so prod adds work fine — there was no add bug at all).
- **Fix applied:** set `.env` `DATABASE_URL` = the Railway URL (copied from `MIGRATION_DATABASE_URL`) so the local dashboard reads prod. Requires a **streamlit restart** (pool is `@st.cache_resource`). ⚠️ This means the local dashboard now writes to PRODUCTION directly. `.env` is gitignored (not committed).
- **The source_platform "fix" was real but local-only:** localhost genuinely lacked the column; `migration_023_source_platform.sql` (committed 1400d8f, `ADD COLUMN IF NOT EXISTS`) is harmless on prod (already exists). Not the cause of the user's issue.
- **LESSON (do this first next time):** before diagnosing "data missing", confirm WHICH database the running app actually uses — read `.env` (`DATABASE_URL` vs `DB_HOST`). Don't assume localhost. `MIGRATION_DATABASE_URL` = the Railway prod connection. Querying prod needs explicit user approval.

### 11. CRITICAL — local `python deal_pulse_bot.py` silently kills the production bot
- **What:** Whenever anyone ran `python deal_pulse_bot.py` on a dev machine (even just to "test"), the bot on Telegram instantly went dead — all buttons disappeared. Happened repeatedly this session.
- **Why:** The bot is ALREADY deployed on Railway as part of the **DealPulseKSA** service (root Dockerfile runs `uvicorn bot_app:app`; bot_app.py imports `deal_pulse_bot` and calls `bot.set_webhook(...)` at startup, line 160). There is no separate "bot" service — it's bundled. Running `deal_pulse_bot.py` locally enters its `__main__` block which calls `bot.remove_webhook()` (line 1827) → wipes the production webhook → Telegram stops delivering updates to the live bot. The old `RUN_MODE` guard defaulted to "polling" so it never blocked.
- **Fix (commit e04d003):** Replaced the broken guard with a hard one — requires explicit `ALLOW_LOCAL_POLLING=1` env to actually run. Without it, prints a loud warning and exits. The flag is for **local PowerShell only, when prod is intentionally stopped for maintenance**. NEVER set `ALLOW_LOCAL_POLLING` on the Railway DealPulseKSA service — it's irrelevant there (prod uses `bot_app:app`, not `__main__`).
- **Recovery if killed again:** Railway → DealPulseKSA → Redeploy → `bot.set_webhook()` runs at startup → webhook re-registered → bot back online in ~1-2 min.
- **Lesson for future-me:** if the user reports "البوت اختفت أزراره / واقف", the FIRST suspect is a local polling run that wiped the prod webhook. Solution = Redeploy DealPulseKSA + ensure no local bot. Don't deploy a separate bot service (would conflict with the webhook).

### 12. CRITICAL — bot buttons ALL freeze in webhook mode (telebot threaded worker deadlock)
- **What:** Every inline button in the live bot stopped responding ("اضغط الأزرار ما تفتح" — nothing at all). Service `/health` OK, webhook healthy (0 pending, no errors, callback_query in allowed_updates), all handlers run fine locally, callback_data within 64B, DB pool fine (14/100). Total paradox: service receives clicks, returns 200, but no handler fires.
- **Root cause (diagnosed 2026-06-02 by reproducing the FULL path `Update.de_json → bot.process_new_updates`):** telebot default `threaded=True` dispatches handlers via a worker pool. In `telebot/util.py` `WorkerThread.run`, when ANY handler raises, the worker stores the exception and **blocks forever on `continue_event.wait()`**. In polling, `bot.polling()` calls `clear_exceptions()` to release it; in **WEBHOOK mode nothing does** → after just 2 handler exceptions (pool has 2 workers) BOTH workers are frozen → all subsequent updates queue but never execute. Service still returns 200 → webhook looks healthy → buttons silently dead until a redeploy (which restarts/unfreezes, then re-freezes later).
- **NOTE vs bug #11:** Same symptom ("أزرار ما تشتغل") but DIFFERENT cause. #11 = local polling wiped the prod webhook (webhook would be EMPTY/erroring). #12 = webhook is HEALTHY but workers frozen. **Diagnostic split:** check `getWebhookInfo` — if url empty / last_error set → #11; if url set + 0 pending + no error but no response → #12.
- **Fix (commit c240238, bot_app.py):** `bot.threaded = False` (synchronous processing inside the existing `asyncio.to_thread(bot.process_new_updates,...)` — no worker pool to freeze) + a `bot.exception_handler` (subclass `telebot.ExceptionHandler`) that logs and returns `True` (handled) so a single crashing handler can't 500 the webhook → no Telegram retry storm. Verified end-to-end: crashing handler is caught, webhook returns normally, next button still fires (no freeze).
- **Lesson:** for pyTelegramBotAPI behind a webhook, ALWAYS run `threaded=False` + an exception_handler. The threaded worker pool is only safe under `bot.polling()`. To reproduce dispatch bugs, test the real `de_json → process_new_updates` path, not direct handler calls (direct calls bypass the worker pool and hide the freeze).
- **Follow-up: ~30s slowness + menu not appearing (same session, commit 1353901):** after the freeze fix, buttons worked but took ~30s, and `/start` showed the welcome photo but not the menu. Root cause: `telebot/apihelper.py` `READ_TIMEOUT = 30` + telebot stores `requests.Session` in **thread-local**. With `await asyncio.to_thread(bot.process_new_updates,...)` each webhook ran on a rotating executor thread → a fresh Session/cold TLS connection to Telegram every time; any stall hit the 30s read-timeout while the webhook **blocked** waiting (and Telegram retried). Measured: DB steps are fast on Railway (register_or_update_user ~5 round-trips); the 30s was outbound Telegram, not DB. **Fix:** replaced `asyncio.to_thread` with a **persistent worker pool** (4 daemon threads consuming a `queue.Queue`); the webhook now `put_nowait` + returns 200 in <1ms. Persistent threads = stable per-thread Session = Telegram connection reuse = fast; non-blocking webhook = no Telegram retries; each worker loop catches exceptions = no freeze. So the full correct webhook setup = `threaded=False` + `exception_handler` + own persistent queue/worker pool (NOT `asyncio.to_thread`).
- **⚠️ Test-on-prod hazard:** the `fav:`/`cfav:` handlers COMMIT to the DB. When reproducing handlers against prod, mock the Telegram calls but remember favorite-toggle writes real rows — clean up (I accidentally added store '5' + category 'اكسسوارات' to a real user and had to delete them).

### 13. SILENT — extra coupons never showed in the bot (`get_conn` undefined, deal_pulse_bot.py)
- **What:** Stores with additional codes in `store_extra_coupons` (e.g. نمشي5 → main `namshi5` + extra `nsmshi55`) showed only ONE code in the bot, while the mini-web showed both.
- **Why:** `get_store_extra_coupons()` called `get_conn()` — a function that **does NOT exist** in deal_pulse_bot.py (the bot uses pooled `get_db_connection()`/`release_conn()`; `get_conn` is the dashboard's helper). It raised `NameError`, caught by a bare `except: return []` → **silently returned empty every time**, so `extra_block` in `_card_text` was always empty. Killed the feature added in commit 624dbaa with zero error output.
- **Fix (commit 9a47cc1):** `get_conn()` → `get_db_connection()`, `conn.close()` → `release_conn()`, and the `except` now logs + rollbacks instead of swallowing silently.
- **Lesson:** the bot and dashboard have DIFFERENT connection helpers — bot = `get_db_connection()`/`release_conn()` (pool), dashboard = `get_conn()` (`_PooledConn`). Don't copy DB code between them without swapping the helper. Bare `except: return []` hid a NameError for an entire feature — prefer logging in excepts.
- **Follow-ups same session:** (a) bot card now shows ALL codes (main + extras) together under «الأكواد المتاحة» instead of hiding the main behind the copy button (commit e30d545); (b) the «نسخت الكوبون» view now lists every code with its own الكود/الخصم/عرض إضافي + a per-code one-tap `copy_text` button (commit 073cafd), since offers can differ per code.

### 14. Idle-notification system REMOVED entirely (deal_pulse_bot.py + bot_app.py)
- **What:** Per user request (pre-launch), the whole two-stage idle watcher was deleted — it proactively messaged users after 5min («غبت عنّا») and ended their session after 10min, which is too aggressive for early B2C (risk of blocks).
- **Removed:** `IDLE_*` constants, `_idle_warned`/`_idle_kicked` sets + lock, the discards in `register_or_update_user`, `idle_warn`/`idle_alert` TEXTS keys, `check_idle_users()` + `idle_watcher()`, and the thread starts + imports in both `__main__` and `bot_app.on_startup`.
- **Commit:** 9a47cc1. **NOTE:** This obsoletes bug-log entries #1 and #4 above (they reference idle vars/sets that no longer exist) — do not "restore" idle behavior from those.
- **Same commit also:** raised pool `maxconn` 8→16; `backfill_user_behavior` now runs in a background thread in `bot_app.on_startup` (was blocking startup + webhook registration).

---

## Known Remaining Issues (not yet fixed)

- `inferred_device` for existing rows in DB still shows old iPhone/Android data — would need a migration to backfill to 'Telegram'
- Dashboard pages still use raw `conn = get_conn()` pattern (protected by `__del__` safety net, but could be upgraded to `with get_conn() as conn:`)
- ~~Bot runs in polling mode on Railway~~ — OUTDATED: verified 2026-06-02 the bot runs via **webhook** (bot_app.py `set_webhook` + `/telegram/webhook/{secret}`), processed `threaded=False` (see fix #12). Local `deal_pulse_bot.py __main__` is the only polling path (guarded by ALLOW_LOCAL_POLLING).
