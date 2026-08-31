---
name: Maqalat OG Image Generation Pitfalls
description: Three real gotchas hit while wiring @vercel/og for Arabic OG images on Next.js 16 — variable fonts, phantom config keys, and font loading in edge vs nodejs runtimes.
type: reference
originSessionId: 14a723a5-c3b8-4b2e-9b1e-b55d65dd193f
---
بناء ديناميكي لصور OG بـ`next/og` (@vercel/og + satori داخلياً) لـmaqalat.org — ٣ فخاخ حقيقية دفعنا ثمنها ساعة+، هذا التلخيص لتجنّبها لاحقاً.

## ١) satori لا يدعم Variable Fonts
- Cairo على Google Fonts الآن **variable font واحد** (`Cairo[slnt,wght].ttf`) — الـstatic files أُزيلت من الريبو.
- تحميلها في `ImageResponse.fonts` يفشل بـ:
  ```
  TypeError: Cannot read properties of undefined (reading '256')
  at satori/... in @vercel/og
  ```
- الرمز `'256'` هو محاولة قراءة font table غير موجود في structure الـVF.
- **الحل:** استخدم static TTF. `Tajawal-Bold.ttf` + `Tajawal-ExtraBold.ttf` من `ofl/tajawal/` (٦٠KB لكل واحد) ممتازة للعربي وتشتغل مباشرة.

## ٢) `outputFileTracingIncludes` يكسر البناء في Next.js 16
- كتبتها كـtop-level config عشان أُجبر Vercel يحزم `.ttf` مع serverless function → **البناء فشل بصمت** (Deployment: Error).
- الأمان: احذفها. لو تحتاج ملفات في bundle، استخدم `fetch` من `public/` بدل `readFileSync`.

## ٣) Edge runtime + fetch = 0 bytes صامتاً
- على `runtime = "edge"` مع `fetch("https://cdn.jsdelivr.net/...")` من داخل الـroute، الاستجابة كانت `HTTP 200` لكن `Content-Length: 0` — يعني ImageResponse أكمل بلا خطأ، لكن الصورة فارغة.
- **الحل:** استخدم `runtime = "nodejs"` (يتعامل مع fetch بشكل عادي وموثوق).

## النمط النهائي الشغّال
```tsx
// app/og-default.png/route.tsx
import { ImageResponse } from "next/og";
import { SITE_URL, SITE_NAME_AR } from "@/lib/seo";

export const runtime = "nodejs";

async function loadFont(filename: string): Promise<ArrayBuffer | null> {
  try {
    const res = await fetch(`${SITE_URL}/fonts/${filename}`, { cache: "force-cache" });
    return res.ok ? await res.arrayBuffer() : null;
  } catch { return null; }
}

export async function GET() {
  const [bold, extraBold] = await Promise.all([
    loadFont("Tajawal-Bold.ttf"),
    loadFont("Tajawal-ExtraBold.ttf"),
  ]);
  const fonts = [
    ...(bold ? [{ name: "Tajawal", data: bold, weight: 700 as const, style: "normal" as const }] : []),
    ...(extraBold ? [{ name: "Tajawal", data: extraBold, weight: 800 as const, style: "normal" as const }] : []),
  ];
  return new ImageResponse(<div>...</div>, {
    width: 1200, height: 630,
    fonts: fonts.length > 0 ? fonts : undefined,
    headers: { "cache-control": "public, immutable, no-transform, max-age=31536000" },
  });
}
```

- Font stored at `public/fonts/Tajawal-*.ttf` (ships with static assets).
- Route lives at `app/og-default.png/route.tsx` → served at `/og-default.png` (stable URL for manual references in `lib/seo.ts` JSON-LD + per-page metadata).
- Favicons: use file-based `app/icon.tsx` + `app/apple-icon.tsx` — auto-detected by Next.js, no manual metadata needed.

## للتحقّق من نجاح OG بعد deploy:
```bash
curl -sI "$SITE_URL/og-default.png"      # expect HTTP 200 + image/png
curl -s   "$SITE_URL/og-default.png" | file -   # expect PNG image data, 1200 x 630
```
