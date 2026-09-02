---
name: Maqalat Admin Dashboard
description: /admin dashboard for maqalat.org — Firestore analytics + GitHub-API MDX editor + Vercel Blob uploads (2026-09-01)
type: project
---

بُنيت لوحة تحكم `/admin` لموقع maqalat.org في 2026-09-01. 3 تبويبات:
1. **كل الروابط** — زيارات + زوّار فريدون + نقرات + CTR لكل مسار (لمصالحة AdSense).
2. **الزوّار والمدن لكل رابط** — تفصيل مدن + قائمة زوّار أفراد + آخر ١٠٠ نقرة.
3. **محرّر المحتوى** — بحث المقال بالـ slug/العنوان/المسار، تحرير MDX مباشرة، حذف، رفع صور/فيديو (يُدرج snippet في مكان المؤشر).

**Why:** المالك طلب داش بورد لمعرفة أي روابط تجذب زيارات (تحضير AdSense)، أي مدن للاستهداف، وسرعة تحرير/حذف الصفحات.

**How to apply:**
- تعقّب الزيارات في Firestore (collections `pageviews` + `clicks`) عبر `PageViewTracker` client component في `app/layout.tsx` — يعمل تلقائياً على كل صفحة.
- الجيولوكيشن من Vercel edge headers (`x-vercel-ip-city/country/region`) — يعمل في الإنتاج فقط، محلياً يُظهر "غير معروف".
- تحرير الملفات: يكتب على القرص محلياً + commit تلقائي على GitHub (إن هُيّئ `GITHUB_TOKEN`). Vercel يُعيد النشر تلقائياً بعد الـ commit.
- رفع الوسائط: Vercel Blob (لا يعمل بدون `BLOB_READ_WRITE_TOKEN`).
- Auth: كلمة سر واحدة (`ADMIN_PASSWORD`) → JWT في HTTP-only cookie لمدّة ٧ أيام (`ADMIN_JWT_SECRET`).

**Env vars مطلوبة** (`.env.local` — الملف gitignored):
```
ADMIN_PASSWORD=<≥16 chars>
ADMIN_JWT_SECRET=<≥24 chars random>   # node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
GITHUB_TOKEN=<fine-grained PAT, Contents: read/write on maqalatorg/maqalat>
GITHUB_REPO=maqalatorg/maqalat
GITHUB_BRANCH=main
BLOB_READ_WRITE_TOKEN=<Vercel dashboard → Storage → Blob → create store>
```

**ملفات جديدة:**
- `lib/analytics.ts` — write + aggregate helpers
- `lib/admin-auth.ts` — JWT session cookie
- `lib/github.ts` — Contents API get/put/delete
- `app/api/track/route.ts` — public tracking endpoint (server-side geo enrichment)
- `app/api/admin/{login,logout}/route.ts`
- `app/api/admin/analytics/{pages,page}/route.ts`
- `app/api/admin/articles/{list,file}/route.ts`
- `app/api/admin/upload/route.ts`
- `components/PageViewTracker.tsx`
- `app/admin/{layout,page,login/page,AdminDashboard,tabs/*}.tsx`

**حدود مهمّة:**
- Firestore free tier: 20K writes/day → يكفي ~15K pageview/day. فوق ذلك يحتاج aggregation job.
- الجيولوكيشن صفر بدون Vercel (فقط في الإنتاج).
- تعديل ملف من الإنتاج بدون GitHub token يرجع `remoteCommit: false` مع تحذير — يجب تهيئة الـ token.
- Firestore rules: يجب فتح كتابة `pageviews` + `clicks` للـ public (writes تأتي من `/api/track` عبر client SDK بلا admin SDK) وقفل القراءة على owner فقط.
