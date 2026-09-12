---
name: Maqalat AdSense Readiness Sweep
description: 2026-09-12 — التطبيق العملي لدروس DealPulse SEO/content على maqalat.org لتقصير مسار الموافقة على AdSense. صفحات ثقة مُقوّاة + de-orphan آلي + سكربتات مسح قابلة لإعادة التشغيل.
type: project
originSessionId: ba0ddc64-d7f5-4764-afa1-cce83b257794
---
## السياق

المالك طلب صراحةً (٢٠٢٦-٠٩-١٢): «استفيد من قدرات وعقل كلود الجهاز الأوّل في كل شيء بشرط
ما تأخذ أي شيء يخص مشروع نبض الصفقات… كل شي ينفع للغاية النهائية Google AdSense». أي نقل
**الأنماط** لا **الأعمال** — voice، guardrails، de-orphan tech، trust-page rigor.

## ما أُنجز (commit `60dc38d`)

**سكربتات المسح (قابلة لإعادة التشغيل):**
- `scripts/audits/adsense_readiness_scan.mjs` — offline scanner يفحص ٢٥٨ مقالاً على:
  passive-ratio، AI-tell openings/enders، human-signal density، missing-table، thin content،
  orphan pages، uncited YMYL numbers. يكتب JSON كامل في `adsense_readiness_report.json`.
- `scripts/audits/deorphan_low_link_articles.mjs` — يقرأ التقرير ويحقن قسم «مواضيع ذات
  صلة» في المقالات ذات <٣ روابط داخلية inline. Idempotent عبر علامة `{/* deorphan-auto */}`.

**نتائج المسح (٢٥٨ مقالاً، عربي+إنجليزي):**
- متوسط الروابط الداخلية inline: **٨.٦٤/مقال** (قريب من هدف DealPulse ٩-١٣) ✅
- ٢٢٥/٢٥٨ مقال ≥٦ روابط (٨٧٪) ✅
- **٤ مقالات بصفر رابط** + **١٦ بأقل من ٣** = ٢٠ فُعِل عليها de-orphan (+٤ لكل = ٨٠ رابطاً جديداً)
- **١٠٠ مقال بلا جدول** — لم يُعالَج (يدوي)
- **٢٧ مقالاً <٧٠٠ كلمة** — لم يُعالَج (يدوي)
- **٢١ مقال YMYL بأرقام inline غير موثّقة** — رُصد، لم يُعالَج (يدوي بأولوية عالية)
- **٠ مقال «نظيف»** (بلا أعلام) لأن مقياس human-signals عربي فقط فكل EN جاء human-0 خطأً — bug في الماسح لم يُصلَح بعد.

**تقوية صفحات الثقة:**
- `editorial-policy`: حُذفت Mayo Clinic من قائمة المصادر الطبية (تحجب الروبوتات، يفحصها Ahrefs
  ككسر — راجع [[health_citation_sourcing]]). أُبدلت بـHarvard Nutrition Source + WHO + NIH
  + CDC + ACOG + Cochrane. رُبطت `/author/founder` من قسم الشفافية. أُضيف mailto إلى قسم
  التصحيحات (كلا اللغتين).
- `about`: `whoBody` صار يربط `/author/founder` عبر `rel=author` (شكل rich-text عبر `<team>`
  tag في ملفات الرسائل).
- `pregnancy-calculator-guide.mdx`: نفس استبدال Mayo → ACOG + NICE.

## دروس نُقلَت من نبض الصفقات (بلا نقل أعمال)

- **صيغة قياس الجودة، لا القاعدة النظرية**: playbook §٦ («فريق مقالات» يقتل E-E-A-T) طُبِّق
  كـ**بنية** (سجل كتّاب، صفحة /author/founder، Person/Organization schema، ربط من الصفحات
  الثقة) لا كنقل محتوى.
- **De-orphan رياضي لا يدوي**: خوارزمية stride-sampling موجودة أصلاً في
  `lib/blog.ts::getRelatedArticles` — سلمت المقالات من «top-6 يُجوّع الذيل». المشكلة كانت
  فقط في inline body links (المتن)، لا في related-articles system.
- **مصادر ميتة عند الكراولر = ديْن**: Mayo Clinic أفرز نصائح عن «صحة الأسرة» بديلة (Harvard/
  WHO/NIH). القاعدة الجديدة: **قبل ذكر أي مصدر طبي في صفحات الثقة، فُحص هل يسمح للـcrawlers
  أم يعطي 403**.

## المتبقّي لـAdSense (يحتاج قرار المالك أو عمل يدوي)

- **١٠٠ مقال بلا جدول** — يحتاج تحرير محرّر لا سكربت.
- **٢٧ مقالاً رقيقاً (<٧٠٠ كلمة)** — إمّا حذف، أو توسّع.
- **٢١ مقال YMYL بأرقام غير موثّقة inline** — أولوية عالية: (gov cluster حكوماتيات) — يحتاج
  مراجعة inline citations. أعلى المخاطر: `saudi-government-salary-scale.en`،
  `driving-license-saudi-guide.en`، `zatca-vat-e-invoicing-guide.en`،
  `musaned-domestic-workers-guide.en`، `menstrual-cycle-calculator.en`.
- **AI cluster (١٧٨ مقالاً) نبرة نمطية**: قابلة للفحص لكن التحرير محرّر لا سكربت.
- **`ads.txt` + `app-ads.txt`**: لم يُنشآ. AdSense يتطلبهما بعد الموافقة (لا قبل).
- **عمر الدومين**: تسجّل ٢٠٢٦-٠٨-٢٩، اليوم ٢٠٢٦-٠٩-١٢ = ١٤ يوماً. الحدّ الأدنى لـAdSense
  الرسمي = ٦ أشهر بمناطق كثيرة، أو أسبوعان في السعودية/الخليج. **قابل للتقديم من الآن**.

## المسار المقترح (بلا تنفيذ)

١. المالك يشغّل الفهرسة (قال يفعلها بنفسه).
٢. تقديم AdSense.
٣. أثناء انتظار المراجعة (٢-٤ أسابيع): مراجعة يدوية للمقالات YMYL الـ٢١، وإضافة جداول للأولوية العليا.

مرتبط: [[project_maqalat]] · [[project_maqalat_writing_playbook]] · [[content_guardrails_playbook]] · [[voice_bible]] · [[health_citation_sourcing]] · [[feedback_mdx_v3_comments]]
