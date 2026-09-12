---
name: MDX v3 rejects HTML comments — use JSX comments
description: MDX v3 (next-mdx-remote-client, @next/mdx v3) treats <!-- --> as invalid HTML and errors with "Unexpected character `!` (U+0021)". Use {/* */} instead.
type: feedback
originSessionId: ba0ddc64-d7f5-4764-afa1-cce83b257794
---
**القاعدة:** لا تكتب `<!-- comment -->` داخل ملف `.mdx` أو أي محتوى يمرّ عبر مُحلّل MDX v3.
استخدم `{/* comment */}` (تعليق JSX).

**Why:** MDX v3 (كل نسخ Next.js ≥ 15 مع `@next/mdx@3` و `next-mdx-remote-client@2`)
تُطبّق مُحلّل MDX الصارم — HTML التقليدي يُعامَل كـmarkup مضغوط، والتعليقات `<!--` تفشل
بـ:
```
Unexpected character `!` (U+0021) before name, expected a character that can start a name,
such as a letter, `$`, or `_` (note: to create a comment in MDX, use `{/* text */}`)
```

**كلفة الدرس:** جلسة maqalat ٢٠٢٦-٠٩-١٢ — سكربت de-orphan آلي حقن `<!-- deorphan-auto -->`
في ٢٠ مقالاً كعلامة idempotency. البناء فشل على أوّل مقال إنجليزي فقط (تمويه: أظهر الخطأ
كأنّه رابط مكسور)، ثم فحص تسلسلي كشف الخطأ الحقيقي بعد ٣ محاولات بناء. الإصلاح جماعي:
```powershell
Get-ChildItem content/articles -Filter *.mdx | % {
  $c = Get-Content $_.FullName -Raw -Encoding UTF8
  if ($c -match '<!-- ') {
    [IO.File]::WriteAllText($_.FullName, ($c -replace '<!-- ([^-]*) -->', '{/* $1 */}'),
      (New-Object Text.UTF8Encoding $false))
  }
}
```

**How to apply:**
- أي سكربت يولّد MDX تلقائياً: استخدم `{/* */}` من البداية.
- أي علامة idempotency/marker داخل MDX: بصيغة JSX-comment.
- عند فحص أخطاء بناء غامضة على ملف MDX واحد فقط: افحص وجود `<!--` قبل أي شيء آخر.

مرتبط: [[project_maqalat]] · [[content_guardrails_playbook]]
