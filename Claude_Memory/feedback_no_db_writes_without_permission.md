---
name: Never Write to DB Without Explicit Permission
description: INSERT/UPDATE/DELETE on the discounts_engine PostgreSQL DB requires explicit user approval per statement. Reading is fine; writing is not.
type: feedback
originSessionId: 0fe41f94-3ccf-43d5-8719-71266c3cf888
---
لا تكتب أي INSERT / UPDATE / DELETE على قاعدة `discounts_engine` (سواء master أو أي جدول ثاني) بدون إذن صريح للعملية تحديداً.

**Why:** المستخدم انفعل بشدة (٢٠٢٦-٠٦-٢٦) لما أدخلت ٣ ستورات أفلييت جديدة (هواوي/ايرالو/فوغا كلوزيت) في `master` بعد ما قال "يلا نبدا هذي ايميلات جديده". اعتبرها استهبال — "يلا نبدا" يعني نبدأ الحوار/التحليل، مو إذن كتابة. القاعدة إنتاج، أي إدخال غير مرغوب نفاية يصعب تنظيفها.

**How to apply:**
- على إيميلات أفلييت / كوبونات جديدة: اعرض البيانات المنظّمة (جدول/نص) + قل صراحة "أبي إذنك أدخلها بـ INSERT".
- "يلا نبدا" / "ابدأ" / "شوف" = افحص واعرض، **مو** اكتب.
- نفّذ كتابة فقط بعد رسالة واضحة من نوع: "أدخلها"، "احفظها بالقاعدة"، "سوّ INSERT"، "أضف". أي شيء أقل من ذلك = توقّف واسأل.
- إذا حصل خطأ كتابة، امسح فوراً بـ DELETE بدون جدل واعتذر باختصار.
