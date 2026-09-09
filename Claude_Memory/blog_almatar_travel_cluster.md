---
name: blog_almatar_travel_cluster
description: عنقود المطار للسفر — 44 مقالاً (طيران + تأجير سيارات + وجهات السعودية + وجهات العالم حسب الفصل + عمرة/تأشيرات/وثائق + أدلّة دبي/تركيا/جورجيا) لـ master.id=86 كود M31 7%؛ فتح فئة «سفر وسياحة»؛ صفر رقم ريال مفبرك
metadata:
  node_type: memory
  type: project
  originSessionId: 3b177687-1150-4a44-96a1-4e703647f3fa
---

**٢٠٢٦-٠٩-٠٩** — المالك أرسل لقطات almatar.com/ar وطلب سيو عن «السفر والسياحة والطيران وتأجير السيارات + وجهات السعودية + وجهات العالم حسب الفصل + نصائح حجز التذاكر»، ونبّه: **بيد إن روم بالسعودية فقط** و«لا تنسَ إيرالو واللي مثله».

## المتجر المحوري — المطار (Al Matar)

- `master.id=86` · `store_id='المطار'` · `name_en='Al Matar'` · كود العملاء **M31** · خصم **7%** · `store_tags={فنادق,سفر,طيران}` · `affiliate_link=almatar.com`.
- **كان مربوطاً من صفر مقال** قبل هذه الجلسة (تحقّق: `grep -c "/store/المطار" lib/blog.ts` = 0 → 87 بعدها).
- `/store/%D8%A7%D9%84%D9%85%D8%B7%D8%A7%D8%B1` يرجع **200** (عنوان «كود خصم المطار 7% فعّال 2026»). **الترميز الصحيح** `%D8%A7%D9%84%D9%85%D8%B7%D8%A7%D8%B1` (بلا مسافة زائدة، بخلاف روملس).
- **حقائق مؤكّدة** (لقطات المالك + WebFetch almatar.com/ar): طيران (+500 شركة) · فنادق (+2M) · تأجير سيارة · تتبّع الرحلة · برنامج ولاء **جوّاك (Jawwak)** نقاط+محفظة · دفع مدى + **تابي + تمارا** · دعم 24/7 هاتف **92 000 55 11** + واتساب · تطبيق 4.8★ · عملة SAR.
- **لم يُتحقّق فلا يُدّعى:** تأشيرات، تأمين سفر، جولات/أنشطة، eSIM من المطار، أسماء شركات تأجير سيارات محدّدة.

## المتاجر المكمّلة

| المتجر | id | كود | ترميز `/store` | الدور |
|---|---|---|---|---|
| بيد إن روم | 55 | sc86 | `%D8%A8%D9%8A%D8%AF%20%D8%A5%D9%86%20%D8%B1%D9%88%D9%85` | فنادق **السعودية فقط** — لا يُربط لوجهات خارجية |
| إيرالو | 51 | ADM | `%D8%A5%D9%8A%D8%B1%D8%A7%D9%84%D9%88` (**بهمزة إ**) | eSIM باقات |
| روملس | 79 | ARABY05 | `%D8%B1%D9%88%D9%85%D9%84%D8%B3` | eSIM PAYG |

⚠️ **بق أُصلح:** ٤ روابط `/store/ايرالو` (بلا همزة، `%D8%A7%D9%8A...`) كانت تُرجع **404** — صُحّحت لـ`%D8%A5%D9%8A...`. الصحيح ٣٦ رابطاً، والخطأ كان ٤. **الترميز الصحيح لإيرالو يحمل الهمزة `إ`.**

## الـ44 مقالاً (5 دفعات، commit+build+push لكلٍّ)

- **ط1 `5e7aa30` — طيران (10):** `almatar-travel-booking-guide-saudi` (المحوري) · `almatar-flight-booking-guide-saudi` · `when-to-book-flights-cheapest-saudi` · `best-time-to-fly-cheapest-day-season-saudi` · `refundable-vs-nonrefundable-tickets-saudi` · `flight-baggage-rules-saudi-airlines-guide` · `domestic-flights-saudi-when-cheapest` · `layover-vs-direct-flights-worth-it-saudi` · `almatar-installments-tabby-tamara-flights` · `jawwak-loyalty-almatar-guide`
- **ط2 `21adfb1` — تأجير سيارات (7):** `car-rental-saudi-guide` (محوري فرعي) · `car-rental-insurance-cdw-saudi` · `car-rental-airport-vs-city-saudi` · `international-driving-license-saudi-travelers` · `car-rental-abroad-tips-saudi` · `road-trip-saudi-planning-guide` · `car-rental-vs-taxi-vs-own-car-saudi`
- **ط3 `a151695` — وجهات السعودية (9):** `saudi-destinations-guide` (محوري فرعي) · `riyadh-travel-guide-best-time` · `jeddah-travel-guide-best-time` · `abha-taif-summer-travel-guide` · `alula-travel-guide-best-time` · `tabuk-neom-red-sea-travel-guide` · `eastern-province-travel-guide-saudi` · `saudi-winter-destinations-guide` · `saudi-summer-escapes-guide`
- **ط4 `fbc956f` — وجهات العالم حسب الفصل (8):** `best-countries-to-visit-by-season-from-saudi` (محوري فرعي) · `summer-travel-destinations-from-saudi` · `winter-travel-destinations-from-saudi` · `spring-travel-destinations-from-saudi` · `autumn-travel-destinations-from-saudi` · `cheapest-international-destinations-from-saudi` · `family-travel-planning-guide-from-saudi` · `travel-abroad-internet-esim-guide-saudi`
- **ط5 `6938b87` — عمرة/تأشيرات/وثائق + أدلّة وجهات (10):** `umrah-trip-planning-guide-saudi` · `flight-delay-cancellation-rights-saudi` (لائحة GACA، الرقم 1929) · `travel-insurance-guide-saudi` · `schengen-visa-guide-saudi` (VFS + تأمين ٣٠ألف يورو، «تحقّق من القنصلية») · `airport-guide-checkin-security-saudi` · `passport-guide-saudi-travelers` (قاعدة ٦ أشهر، تجديد أبشر) · `travel-packing-checklist-guide-saudi` · `dubai-travel-guide-best-time-from-saudi` · `turkey-travel-guide-best-time-from-saudi` · `georgia-travel-guide-best-time-from-saudi` (الثلاثة أعلى طلب سعودي خارجي)

## قرارات مثبّتة

- **صفر رقم ريال مفبرك (حائط ٣).** «الأسعار التقريبية» التي طلبها المالك نُفّذت كـ: مستويات وصفية (منخفضة/متوسطة/مرتفعة) + نسب مقارنة («أوروبا الغربية ٢–٣ أضعاف القاهرة في الموسم نفسه») + آليات نوافذ الحجز + «الأداة الحيّة هي الحكم». تحقّق: `grep -cE '[0-9٠-٩]+ ?(ريال|ر.س|SAR)'` على كل مقال = **0**. نمط [[voice_bible]] (جدول مقاسات مترو برازيل).
- **فئة جديدة:** `category: 'سفر وسياحة'` (44 مقالاً). أُضيف alias `'سفر وفنادق': 'travel'` و`'سفر وسياحة': 'travel'` في `CATEGORY_ALIASES` بـ`lib/blog.ts` — **أصلح يُتم 14 مقال بيد إن روم** كانت تسقط على `savings-guides` (الـfallback) لأن `سفر وفنادق` لم يكن ممُّاً.
- **بيد إن روم للسعودية فقط:** مقالات الوجهات الخارجية تربط الفنادق لـ**المطار** لا بيد إن روم.
- **قواعد الطيران محقّقة:** درجات أسعار flynas (Light/Value/Plus) وSaudia (Guest Saver/Basic/Semi-Flex/Flex) وأمتعتها من WebSearch؛ كُتبت **كهيكل** بلا أرقام كجم/ريال محدّدة (تتغيّر). الرخصة الدولية = **SATA** المُصدِر الرسمي الوحيد + تحذير من المواقع المزيّفة.
- **de-orphan:** كل الدفعات مربوطة من المحوري `almatar-travel-booking-guide-saudi` (أقسام: طيران/فنادق/تأجير/دفع/وجهات SA/سفر خارجي) + ربط المحوري من هَب بيد إن روم (14 مقالاً) وهَبَّي إيرالو/روملس.
- ⚠️ **غلطة أُمسكت بالاسم — «توسيع نطاق»:** أول de-orphan بـ`replace_all` أصاب **264 مقالاً** لا 5 (السطر footer شائع). رُوجِع بـ Python byte-replace (`removed 263`)، ثم de-orphan مستهدف. **الدرس: لا `replace_all` على سلسلة footer عامّة — احصر بسياق فريد.**

## التحقّق (لكل دفعة)

`NODE_OPTIONS=--max-old-space-size=8192 npx next build` كامل **EXIT=0** (إلزامي بعد لمس `blog.ts` — [[web_repo_verification_recipes]] §🔴). أعداد الصفحات: 2187 → 2194 → 2203 → 2211 → **2221**. كل الصفحات تُصيَّر بـ`FAQPage` schema وكود M31. صفر `\`\`\`` ثلاثية، صفر `${`، صفر رابط `/blog/` مكسور، صفر slug مكرّر. الإجمالي **1795 → 1839**. ⚠️ **بق كُتب وأُصلح في ط5:** «للأقدam» (خلط عربي/لاتيني) بمقال العمرة، و`passport-guide` طُبع بلا جدول — الفحص الآلي (`grep` لاتيني داخل عربي + عدّ `^\|`) يمسك الصنفين.

## معلّق (إذن المالك)

- **المالك (٢٠٢٦-٠٩-٠٩): «ولا عاد تسألني عن DB»** — لا تُبرز بند `blog_bridge` في كل ملخّص؛ إذن العملية الصريح يبقى حائط ١، فلا كتابة DB إلا بطلب مباشر.
- **`blog_bridge` لم يُعَد بناؤه** — `python -m scripts.build_blog_bridge --write` كتابة DB. 44 مقالاً جديداً + متجر المطار غير مربوطين في جدول البحث بعد. (نفس حالة [[blog_fnp_cluster]] و[[blog_almajed_cluster]].)
- **لا صفحات `/c/`** للمطار — أنبوب `/c/` أُزيل ([[seo_page_portfolio_verdict]] ٢٠٢٦-٠٩-٠٩)؛ يدوي فقط عبر `seo-seed-custom`.
- **الحالة الاستراتيجية (صُورِح بها المالك):** العنق يبقى سلطة الدومين، لكن هذا العنقود **أقوى دفاعاً** من عناقيد المتاجر: «متى أحجز تذكرة»/«تأجير سيارة السعودية»/«وجهات الصيف» لها طلب بحث سعودي حقيقي (بعكس «بوما مقاسات»). القيمة موزّعة: قناة الاستشهاد الذكي (قوائم + جداول مواسم + مقارنات = وقودها [[ai_citation_channel]]) + تمرير سلطة لصفحة `/store/المطار` الجديدة.

يكمّل [[blog_bedinroom_cluster]] · [[blog_maxfashion_puma_clusters]] (عنقود روملس/إيرالو) · [[content_guardrails_playbook]] · [[voice_bible]].
