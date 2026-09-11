---
name: Maqalat MDX2 Runtime Pitfalls (Binding)
description: Three patterns in Arabic prose that pass local parse but crash MDX runtime with 500 — learned 2026-09-05 from first Ahrefs audit; scan for these before publishing
type: feedback
originSessionId: 442cfa15-c621-4dae-a766-6b7ef6dde2d3
---
## Why

يوم 2026-09-05 كشف أوّل تدقيق Ahrefs لـmaqalat.org 9 صفحات تُرجع HTTP 500 مع كون الملفّات موجودة والبناء ناجح. الجذر: MDX2 يعامل بعض الأنماط في النثر العربي على أنّها JSX. بعضها يفشل عند التحليل، وبعضها يمرّ التحليل ثم يفشل runtime على Vercel — يعني أنّ التحقّق المحلّي بـ`@mdx-js/mdx compile` **لا يكفي** لالتقاطها.

## How to Apply

قبل نشر أيّ مقال جديد في `content/articles/`، امنع هذه الأنماط الثلاثة في النثر (أي **خارج** أسوار الكود ``` ``` والباكتك المفرد `):

### 1. `<` متبوعة برقم أو حرف صغير

MDX يقرأها كبداية عنصر JSX. مثال: `<10%`, `<100ms`, `<1%`, `<60 ثانية` كلّها تنسف الصفحة.

**الحل**: HTML entity `&lt;` — يُعرَض كـ `<` تماماً بلا كسر. مثلاً `&lt;10%`.

### 2. `{...}` عارية (قوس مجعد يفتح ولا يُغلق كتعبير JSX سليم)

مثال حقيقي كسر الصفحة: `"]}}[[]{ ####"` في نثر عربي. MDX يفتح تعبيراً عند `{` ولا يجد إغلاقاً مقبولاً.

**الحل**: لفّ السلسلة الكاملة في باكتك (inline code) — `` `]}}[[]{ ####` `` — أو استخدم `&#123;` `&#125;` للأقواس المفردة.

### 3. `{{IDENT}}` (قوسان مجعّدان)

هذا **الأخبث** — يمرّ التحليل بلا خطأ لأنّه صياغة JSX سليمة (object literal مختصر)، لكن runtime يفشل لأنّ `IDENT` غير معرَّف. مثال: `{{DOCTOR_NOTES}}` في blockquote أدّى لـ500 مع كون البناء ناجحاً محلّياً.

**الحل**: لفّ التعبير كاملاً في باكتك: `` `{{DOCTOR_NOTES}}` ``. أو استبدل بـ `&#123;&#123;IDENT&#125;&#125;`.

## سكربت الفحص قبل النشر

```bash
cd C:/Users/user/Desktop/maqalat && node -e "
const fs=require('fs'), matter=require('gray-matter');
(async()=>{
  const {compile}=await import('@mdx-js/mdx');
  const files=fs.readdirSync('content/articles').filter(f=>f.endsWith('.mdx'));
  for(const f of files){
    const src=fs.readFileSync('content/articles/'+f,'utf-8');
    const {content}=matter(src);
    // parse check
    try{ await compile(content,{format:'mdx'}); }
    catch(e){ console.log('❌ PARSE',f,'::',e.message.split('\n')[0].substring(0,80)); continue; }
    // runtime hazard scan (bare {{}} outside code)
    const lines=content.split('\n'); let inF=false;
    for(let i=0;i<lines.length;i++){
      if(/^\`\`\`/.test(lines[i])){inF=!inF;continue;}
      if(inF) continue;
      const stripped=lines[i].replace(/\`[^\`]*\`/g,'');
      if(/\{\{/.test(stripped)) console.log('⚠️ RUNTIME',f+':'+(i+1),lines[i].substring(0,80));
    }
  }
  console.log('done');
})();
"
```

استخدمه دائماً قبل `git push` لأي مقال جديد.

## المصدر
2026-09-05 حادثة 9 صفحات 500 على maqalat.org — Ahrefs أوّل تدقيق. الإصلاح في commit `0b17e2c` + `e3f7f60` تحت [project_maqalat_indexing_api.md](project_maqalat_indexing_api.md) الأخوة.
