# تدقيق استشهادات المدوّنة بالمتاجر

> **الحالة: المرحلة ١ — لم يُنفَّذ أي حذف من هذه القائمة بعد.**
> بُنيت ٢٠٢٦-٠٨-٢٧ بأمر، لا بالتقدير. المُنفَّذ حتى الآن: مقال واحد فقط
> (`home-furniture-mattress-memory-foam-guide-saudi-arabia`, commit `c417901`).

## لماذا

قالبٌ ألصق بند «متجر + نسبة خصم» في نهاية مقالات كثيرة اعتماداً على **وسوم**
المتجر في `master` لا على ما يبيعه فعلاً. النتيجة: متجر ستائر يُرشَّح لشراء
المراتب، ومتجر تخزين يُرشَّح لشراء LEGO وبنوك الطاقة.

الضرر مركّب: الزائر يُساق لمتجر لا يبيع ما يريد، والاستشهاد الكاذب يدخل
«صفقات تهمّك» فيُعيد اقتراح المتجر الخطأ، ومحرّكات البحث تقرأ صفحة تَعِد بما
لا تفي به.

## نطاق الفحص

- **1617 مقالاً** فُحصت (كل `slug` في `lib/blog.ts`).
- **58 متجراً** في الكتالوج، **57** مستشهد به في المدوّنة.
- **47 متجراً** حُلّ نطاقه الحقيقي من رابط الأفلييت.

## قاعدة الحكم

**يُحذف البند حين يوحي بأن المتجر يبيع موضوع المقال وهو لا يبيعه.**

ويبقى في ثلاث حالات:

1. **داخل الكتالوج** — موضوع المقال ضمن ما يبيعه فعلاً.
2. **تجميعة متاجر** — المقال فهرس متاجر/أكواد، والمتجر مذكور بصفته الصحيحة
   لا بمنتَج. (تصحيح على أول تمرير: كان يحذف سيدار من «أفضل المتاجر» رغم أن
   وصفه هناك دقيق — ذلك إفقار لا تصحيح.)
3. **مصرَّح بأنه مُكمّل** — البند يقول «أدوات تنظيم تكمّل مطبخك» ولا يدّعي بيع
   الثلاجة.

---

## سيدار

**النطاق:** `sedarglobal.com`

**ما يبيعه فعلاً:** ستائر · مظلات داخلية · ورق جدران · بيت ذكي وستائر محرّكة · أبواب قابلة للطي · مظلات خارجية وبرقولا · مفروشات (وسائد) · تنجيد

وصفه في `master` يقول الشيء نفسه: «متخصّص في الستائر والمفروشات وتجهيزات النوافذ».

**يبقى في 21 مقالاً · يُحذف من 49.**

### يبقى

| المقال | السبب |
|---|---|
| `best-saudi-online-stores-2026` | تجميعة متاجر |
| `home-shopping-guide-saudi-arabia` | تجميعة متاجر |
| `home-furniture-outdoor-umbrella-pergola-saudi-arabia` | داخل الكتالوج |
| `home-furniture-gazebo-pergola-guide-saudi-arabia` | داخل الكتالوج |
| `home-furniture-outdoor-umbrellas-large-guide-saudi-arabia` | داخل الكتالوج |
| `tools-home-blinds-curtains-guide-saudi-arabia` | داخل الكتالوج |
| `sedar-curtains-guide-saudi` | داخل الكتالوج |
| `sedar-blackout-thermal-curtains-saudi` | داخل الكتالوج |
| `sedar-sheer-panel-curtains-saudi` | داخل الكتالوج |
| `sedar-blinds-guide-saudi` | داخل الكتالوج |
| `sedar-roller-roman-blinds-saudi` | داخل الكتالوج |
| `sedar-wooden-vertical-blinds-saudi` | داخل الكتالوج |
| `sedar-smart-home-motorization-guide-saudi` | داخل الكتالوج |
| `sedar-motorized-curtains-app-control-saudi` | داخل الكتالوج |
| `sedar-smart-scenarios-integration-saudi` | داخل الكتالوج |
| `sedar-wallpaper-guide-saudi` | داخل الكتالوج |
| `sedar-wallpaper-patterns-rooms-saudi` | داخل الكتالوج |
| `sedar-cushions-furnishings-decor-saudi` | داخل الكتالوج |
| `sedar-folding-doors-guide-saudi` | داخل الكتالوج |
| `sedar-outdoor-shades-pergolas-saudi` | داخل الكتالوج |
| `sedar-measurement-installation-service-saudi` | داخل الكتالوج |

### يُحذف

| المقال | البند الملفّق |
|---|---|
| `home-furniture-buying-guide-saudi-arabia` | توفّر **تركيب وتوصيل مجاني**، وغيرها يحمّلك رسوماً. السعر النهائي = سع |
| `home-furniture-sofa-majlis-guide-saudi-arabia` | **تركيب وتوصيل مجاني** — قيمة كبيرة لأن نقل الكنب وتركيبه في الشقق العليا مكلف. |
| `home-furniture-bed-mattress-guide-saudi-arabia` | **بتركيب وتوصيل مجاني**. |
| `home-furniture-dining-guide-saudi-arabia` | **بتركيب وتوصيل مجاني** — يوفّر كثيراً في السعر النهائي. |
| `home-furniture-wardrobe-guide-saudi-arabia` | غرف نوم كاملة **بتركيب وتوصيل مجاني** — الدولاب كبير الحجم فتركيبه على المتجر يوفّر كثيراً |
| `home-furniture-outdoor-guide-saudi-arabia` | جلسات خارجية كاملة **بتركيب وتوصيل مجاني**. |
| `home-furniture-sofa-leather-vs-fabric-saudi-arabia` | كنب متعدّد الخيارات **بتركيب وتوصيل مجاني**. |
| `home-furniture-sofa-sectional-modular-saudi-arabia` | كنب زاوية بتصاميم متنوّعة **مع تركيب وتوصيل مجاني** — التركيب الاحترافي للـSectional حاسم. |
| `home-furniture-bed-frame-headboard-guide-saudi-arabia` | **بتركيب وتوصيل مجاني** — التركيب الاحترافي مهمّ |
| `home-furniture-dining-chairs-ergonomic-saudi-arabia` | أطقم سفرة كاملة **بتركيب وتوصيل مجاني**. |
| `home-furniture-buffet-sideboard-guide-saudi-arabia` | أطقم سفرة كاملة **بتركيب وتوصيل مجاني**. |
| `home-furniture-sliding-door-wardrobe-saudi-arabia` | يضمن الاستواء و |
| `home-furniture-walk-in-closet-planning-saudi-arabia` | تصاميم مخصّصة **مع تركيب وتوصيل مجاني** — التركيب الاحترافي لـWalk-in معقّد ويستحقّ. |
| `home-furniture-poolside-lounger-guide-saudi-arabia` | أطقم مسبح كاملة **بتركيب وتوصيل مجاني**. |
| `home-furniture-home-office-guide-saudi-arabia` | مكاتب وأثاث مكتبي **بتركيب وتوصيل مجاني**. |
| `home-furniture-ergonomic-chair-guide-saudi-arabia` | كراسي مكتبية أرغونومية **بتركيب وتوصيل مجاني**. |
| `home-furniture-standing-desk-guide-saudi-arabia` | مكاتب مكتبية **بتركيب وتوصيل مجاني**. |
| `home-furniture-side-tables-guide-saudi-arabia` | أثاث + تركيب وتوصيل مجاني. |
| `home-furniture-coffee-tables-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-console-tables-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-bar-stools-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-bar-cabinets-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-wine-storage-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-kids-bedroom-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-kids-desk-play-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-nursery-baby-room-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-hammocks-swings-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-outdoor-benches-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-outdoor-daybed-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-bookshelves-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-storage-cabinets-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-shoe-cabinets-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-vanity-dressing-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-hotel-hospitality-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-restaurant-cafe-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-office-institutional-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-kitchen-island-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-kitchen-cabinets-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-pantry-organization-guide-saudi-arabia` | تركيب مجاني. |
| `home-furniture-media-tv-guide-saudi-arabia` | تركيب مجاني. |
| `tools-home-doors-guide-saudi-arabia` | تركيب مجاني. |
| `tools-home-windows-guide-saudi-arabia` | تركيب مجاني. |
| `tools-home-flooring-guide-saudi-arabia` | تركيب مجاني. |
| `tools-home-carpet-rugs-guide-saudi-arabia` | تركيب مجاني. |
| `tools-home-fireplaces-guide-saudi-arabia` | تركيب مجاني. |
| `vogacloset-home-decor-guide-saudi` | أفضل بكثير — راجعي [دليل شراء الأثاث](/blog/home-furniture-buy |
| `vogacloset-bedroom-bathroom-essentials-saudi` | واذهبي إلى [س |
| `vogacloset-home-accessories-decor-saudi` | . |
| `hm-home-guide-saudi` | — راجعي [دليل الأثاث الشامل](/blog/ho |

## بيتي شوب

**النطاق:** `bayteshop.com`

**ما يبيعه فعلاً:** سلات وصناديق تخزين · رفوف · خزائن أحذية · خزائن وعلاّقات ملابس · أغطية كنب · إكسسوارات حمّام · مستلزمات تقديم وتخزين طعام · أطقم أكواب وسيراميك · موزّعات صابون

`sitemap-1.xml` و`sitemap-2.xml` معاً: **صفر** ألعاب، **صفر** إكسسوارات جوّال، **صفر** فراش.

**يبقى في 29 مقالاً · يُحذف من 152.**

### يبقى

| المقال | السبب |
|---|---|
| `online-shopping-savings-guide-saudi-arabia` | تجميعة متاجر |
| `best-saudi-online-stores-2026` | تجميعة متاجر |
| `how-to-use-coupon-code-saudi` | تجميعة متاجر |
| `kids-shopping-guide-saudi-arabia` | تجميعة متاجر |
| `home-shopping-guide-saudi-arabia` | تجميعة متاجر |
| `best-coupons-saudi-arabia-2026` | تجميعة متاجر |
| `ramadan-deals-guide` | تجميعة متاجر |
| `refrigerator-buying-guide-saudi-arabia` | مصرَّح بأنه مُكمّل |
| `kitchen-appliances-guide-saudi-arabia` | مصرَّح بأنه مُكمّل |
| `home-furniture-wardrobe-guide-saudi-arabia` | داخل الكتالوج |
| `home-furniture-sliding-door-wardrobe-saudi-arabia` | داخل الكتالوج |
| `home-furniture-walk-in-closet-planning-saudi-arabia` | داخل الكتالوج |
| `tools-home-storage-organization-guide-saudi-arabia` | داخل الكتالوج |
| `bayteshop-kitchen-organization-guide-saudi` | داخل الكتالوج |
| `bayteshop-bedroom-wardrobe-organization-saudi` | داخل الكتالوج |
| `bayteshop-bathroom-organization-saudi` | داخل الكتالوج |
| `bayteshop-kids-home-essentials-saudi` | داخل الكتالوج |
| `bayteshop-innovative-storage-saudi` | داخل الكتالوج |
| `bayteshop-transparent-containers-saudi` | داخل الكتالوج |
| `bayteshop-drawer-organizers-saudi` | داخل الكتالوج |
| `bayteshop-spice-organizers-saudi` | داخل الكتالوج |
| `bayteshop-fridge-organization-saudi` | داخل الكتالوج |
| `bayteshop-closet-hangers-saudi` | داخل الكتالوج |
| `bayteshop-shoe-storage-saudi` | داخل الكتالوج |
| `bayteshop-bath-shower-storage-saudi` | داخل الكتالوج |
| `bayteshop-vacuum-storage-bags-saudi` | داخل الكتالوج |
| `bayteshop-under-bed-storage-saudi` | داخل الكتالوج |
| `bayteshop-cord-cable-organizers-saudi` | داخل الكتالوج |
| `pressure-cooker-buying-guide-saudi-arabia` | مصرَّح بأنه مُكمّل |

### يُحذف

| المقال | البند الملفّق |
|---|---|
| `home-furniture-buying-guide-saudi-arabia` | مستلزمات منزل شاملة بخصم ١٠٪. |
| `home-furniture-sofa-majlis-guide-saudi-arabia` | قطع صغيرة وإكسسوارات بخصم ١٠٪. |
| `home-furniture-bed-mattress-guide-saudi-arabia` | ملايات ووسائد وإكسسوارات بخصم ١٠٪. |
| `home-furniture-dining-guide-saudi-arabia` | إكسسوارات ومفارش سفرة بخصم ١٠٪. |
| `home-furniture-outdoor-guide-saudi-arabia` | ديكور خارجي وإضاءة حديقة بخصم ١٠٪. |
| `home-furniture-sofa-leather-vs-fabric-saudi-arabia` | إكسسوارات وأغطية بخصم ١٠٪. |
| `home-furniture-sofa-sectional-modular-saudi-arabia` | ملحقات وأغطية بخصم ١٠٪. |
| `home-furniture-bed-frame-headboard-guide-saudi-arabia` | إكسسوارات وشراشف بخصم ١٠٪. |
| `home-furniture-dining-chairs-ergonomic-saudi-arabia` | إكسسوارات ومناديل بخصم ١٠٪. |
| `home-furniture-buffet-sideboard-guide-saudi-arabia` | أواني عرض بخصم ١٠٪. |
| `home-furniture-outdoor-umbrella-pergola-saudi-arabia` | ديكور وإضاءة خارجية بخصم ١٠٪. |
| `home-furniture-poolside-lounger-guide-saudi-arabia` | إكسسوارات مسبح بخصم ١٠٪. |
| `home-furniture-home-office-guide-saudi-arabia` | إكسسوارات مكتبية بخصم ١٠٪. |
| `home-furniture-ergonomic-chair-guide-saudi-arabia` | إكسسوارات مكتبية بخصم ١٠٪. |
| `home-furniture-standing-desk-guide-saudi-arabia` | إكسسوارات مكتبية بخصم ١٠٪. |
| `kids-toys-buying-guide-saudi-arabia` | ألعاب ومنزل بخصم ١٠٪. |
| `kids-toys-stem-educational-guide-saudi-arabia` | ألعاب تعليمية بخصم ١٠٪. |
| `kids-toys-robotics-coding-guide-saudi-arabia` | ألعاب تعليمية بخصم ١٠٪. |
| `kids-toys-science-experiments-guide-saudi-arabia` | ألعاب تعليمية بخصم ١٠٪. |
| `kids-toys-plush-stuffed-guide-saudi-arabia` | حيوانات محشوة وإكسسوارات بخصم ١٠٪. |
| `kids-toys-plush-fashion-doll-guide-saudi-arabia` | ألعاب تجميع بخصم ١٠٪. |
| `kids-toys-baby-newborn-guide-saudi-arabia` | ألعاب رضّع بخصم ١٠٪. |
| `kids-toys-baby-teething-sensory-guide-saudi-arabia` | مستلزمات رضّع بخصم ١٠٪. |
| `kids-toys-baby-milestone-6-18m-guide-saudi-arabia` | ألعاب تعليمية أطفال بخصم ١٠٪. |
| `kids-toys-play-kitchen-guide-saudi-arabia` | ألعاب أطفال بخصم ١٠٪. |
| `kids-toys-play-food-utensils-guide-saudi-arabia` | ألعاب أطفال بخصم ١٠٪. |
| `kids-toys-tea-set-baking-guide-saudi-arabia` | ألعاب أطفال بخصم ١٠٪. |
| `kids-toys-role-play-guide-saudi-arabia` | ألعاب تعليمية بخصم ١٠٪. |
| `kids-toys-doctor-medical-kit-guide-saudi-arabia` | ألعاب أطفال بخصم ١٠٪. |
| `kids-toys-tools-workshop-guide-saudi-arabia` | ألعاب أطفال بخصم ١٠٪. |
| `kids-toys-arts-crafts-guide-saudi-arabia` | ألعاب تعليمية بخصم ١٠٪. |
| `kids-toys-crayons-markers-guide-saudi-arabia` | ألعاب تعليمية بخصم ١٠٪. |
| `kids-toys-playdough-clay-guide-saudi-arabia` | ألعاب تعليمية بخصم ١٠٪. |
| `kids-toys-gross-motor-outdoor-guide-saudi-arabia` | ألعاب أطفال بخصم ١٠٪. |
| `kids-toys-bikes-scooters-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-ride-on-guide-saudi-arabia` | ألعاب أطفال بخصم ١٠٪. |
| `kids-toys-baby-dolls-guide-saudi-arabia` | ألعاب أطفال بخصم ١٠٪. |
| `kids-toys-baby-doll-accessories-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-baby-doll-stroller-nursery-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-board-games-guide-saudi-arabia` | ألعاب أطفال بخصم ١٠٪. |
| `kids-toys-card-games-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-chess-strategy-guide-saudi-arabia` | ألعاب تعليمية بخصم ١٠٪. |
| `kids-toys-electronics-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-smartwatch-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-tablet-screen-time-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-dinosaurs-figures-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-sea-creatures-figures-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-language-literacy-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-kaleidoscope-optical-toys-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-dollhouse-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-dollhouse-furniture-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-sylvanian-calico-critters-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-lego-building-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-collectibles-themed-sets-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-magic-tricks-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-puppets-theater-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-storytelling-props-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-barbie-career-inspiration-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-pokemon-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-blind-boxes-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-plush-keychains-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-sanrio-hello-kitty-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-squishmallows-clip-guide-saudi-arabia` | ١٠٪. |
| `kids-toys-water-summer-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-buying-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-cases-magsafe-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-chargers-cables-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-wireless-chargers-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-power-banks-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-screen-protectors-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-selfie-sticks-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-wireless-earbuds-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-airpods-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-anc-headphones-guide-saudi-arabia` | ١٠٪. |
| `tools-home-buying-guide-saudi-arabia` | ١٠٪. |
| `tools-home-drills-guide-saudi-arabia` | ١٠٪. |
| `tools-home-saws-guide-saudi-arabia` | ١٠٪. |
| `tools-home-hand-tools-guide-saudi-arabia` | ١٠٪. |
| `tools-home-measuring-tools-guide-saudi-arabia` | ١٠٪. |
| `tools-home-painting-tools-guide-saudi-arabia` | ١٠٪. |
| `tools-home-wall-repair-guide-saudi-arabia` | ١٠٪. |
| `tools-home-plumbing-tools-guide-saudi-arabia` | ١٠٪. |
| `tools-home-electrical-tools-guide-saudi-arabia` | ١٠٪. |
| `tools-home-safety-gear-guide-saudi-arabia` | ١٠٪. |
| `tools-home-garden-tools-guide-saudi-arabia` | ١٠٪. |
| `tools-home-lawn-mower-guide-saudi-arabia` | ١٠٪. |
| `tools-home-outdoor-power-equipment-guide-saudi-arabia` | ١٠٪. |
| `tools-home-closet-organizers-guide-saudi-arabia` | ١٠٪. |
| `tools-home-kitchen-organizers-guide-saudi-arabia` | ١٠٪. |
| `tools-home-lighting-guide-saudi-arabia` | ١٠٪. |
| `tools-home-ceiling-fans-guide-saudi-arabia` | ١٠٪. |
| `tools-home-smart-home-guide-saudi-arabia` | ١٠٪. |
| `tools-home-bathroom-fixtures-guide-saudi-arabia` | ١٠٪. |
| `tools-home-shower-heads-guide-saudi-arabia` | ١٠٪. |
| `tools-home-locks-security-guide-saudi-arabia` | ١٠٪. |
| `tools-home-ac-cooling-guide-saudi-arabia` | ١٠٪. |
| `tools-home-air-purifiers-guide-saudi-arabia` | ١٠٪. |
| `tools-home-humidifiers-guide-saudi-arabia` | ١٠٪. |
| `tools-home-vacuum-cleaner-guide-saudi-arabia` | ١٠٪. |
| `tools-home-cleaning-supplies-guide-saudi-arabia` | ١٠٪. |
| `tools-home-water-filter-guide-saudi-arabia` | ١٠٪. |
| `tools-home-automotive-tools-guide-saudi-arabia` | ١٠٪. |
| `tools-home-cookware-guide-saudi-arabia` | ١٠٪. |
| `tools-home-knives-cutlery-guide-saudi-arabia` | ١٠٪. |
| `tools-home-small-kitchen-appliances-guide-saudi-arabia` | ١٠٪. |
| `tools-home-ladders-guide-saudi-arabia` | ١٠٪. |
| `tools-home-workbench-storage-guide-saudi-arabia` | ١٠٪. |
| `tools-home-fasteners-screws-guide-saudi-arabia` | ١٠٪. |
| `tools-home-washing-machine-guide-saudi-arabia` | ١٠٪. |
| `tools-home-dryer-guide-saudi-arabia` | ١٠٪. |
| `tools-home-dishwasher-guide-saudi-arabia` | ١٠٪. |
| `home-furniture-side-tables-guide-saudi-arabia` | ١٠٪. |
| `home-furniture-console-tables-guide-saudi-arabia` | ١٠٪. |
| `home-furniture-planters-plant-stands-guide-saudi-arabia` | ١٠٪. |
| `home-furniture-outdoor-planters-guide-saudi-arabia` | ١٠٪. |
| `home-furniture-vertical-garden-guide-saudi-arabia` | ١٠٪. |
| `home-furniture-hammocks-swings-guide-saudi-arabia` | ١٠٪. |
| `home-furniture-craft-hobby-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-bluetooth-speakers-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-smart-speakers-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-bluetooth-trackers-guide-saudi-arabia` | ١٠٪. |
| `tools-home-doors-guide-saudi-arabia` | ١٠٪. |
| `tools-home-carpet-rugs-guide-saudi-arabia` | ١٠٪. |
| `tools-home-wallpaper-paint-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-fitness-tracker-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-desk-setup-guide-saudi-arabia` | ١٠٪. |
| `tools-home-water-heater-guide-saudi-arabia` | ١٠٪. |
| `tools-home-solar-panels-guide-saudi-arabia` | — تصفّح العروض والكود الفعّال في صفحة المتجر. |
| `tools-home-insulation-guide-saudi-arabia` | ١٠٪. |
| `tools-home-pet-supplies-guide-saudi-arabia` | ١٠٪. |
| `tools-home-smart-thermostat-guide-saudi-arabia` | ١٠٪. |
| `phone-accessories-car-chargers-guide-saudi-arabia` | إكسسوارات جوّال منتقاة بخصم ١٠٪ — جيّد للعائلة. |
| `phone-accessories-bluetooth-fm-transmitter-guide-saudi-arabia` | إكسسوارات سيارة منتقاة بخصم ١٠٪. |
| `phone-accessories-cleaning-kits-guide-saudi-arabia` | إكسسوارات جوّال منتقاة بخصم ١٠٪. |
| `phone-accessories-screen-mirroring-adapters-guide-saudi-arabia` | إكسسوارات جوّال منتقاة بخصم ١٠٪. |
| `phone-accessories-digital-stylus-guide-saudi-arabia` | أقلام Logitech وESR وZagg بخصم ١٠٪. |
| `phone-accessories-gimbal-stabilizer-guide-saudi-arabia` | إكسسوارات جوّال وجيمبل منتقاة بخصم ١٠٪. |
| `thedeal-kids-designer-clothing-saudi` | . |
| `thedeal-babies-designer-outlet-saudi` | . |
| `thedeal-kids-gifts-outlet-saudi` | . |
| `vogacloset-kids-fashion-guide-saudi` | مستلزمات أطفال ومنزل. |
| `vogacloset-home-decor-guide-saudi` | . |
| `mamaspapas-strollers-guide-saudi` | مستلزمات أطفال ومنزل شاملة. |
| `mamaspapas-baby-clothing-guide-saudi` | مستلزمات أطفال متنوّعة. |
| `hm-kids-baby-guide-saudi` | مستلزمات أطفال شاملة. |
| `hm-kids-school-outdoor-saudi` | حقائب ومستلزمات مدرسية. |
| `hm-home-guide-saudi` | منزل وأطفال شامل. |
| `serving-trays-plates-guide-saudi-arabia` | تنظيم المطبخ وأدوات الترتيب التي تُكمل أدوات التقديم — خصم 10% بكود 6INJQ، وتف |
| `buffet-warmers-serving-carts-guide-saudi-arabia` | أدوات تنظيم وتجهيز المطبخ التي تسبق التقديم — خصم 10% بكود 6INJQ. |
| `frying-pans-nonstick-guide-saudi-arabia` | أدوات وتنظيم المطبخ — خصم 10% بكود 6INJQ. |
| `bakeware-oven-trays-guide-saudi-arabia` | تنظيم أدوات الخبز وحفظها — خصم 10% بكود 6INJQ. |
| `food-storage-containers-guide-saudi-arabia` | تنظيم الثلاجة والمطبخ — خصم 10% بكود 6INJQ، وتفصيله في [دليل تنظيم الثلاجة](/b |

---

## ما لم يُفحص بعد

**55 متجراً** من أصل 57. الأولوية للمتاجر ضيّقة الكتالوج واسعة الانتشار —
قياس التشتّت (عدد العناقيد الموضوعية لكل متجر) يرتّبها، لكن **الترتيب ليس
حكماً**: لا يصدر حكم على متجر قبل فتح موقعه وخريطته.

`نون` و`علي اكسبرس` أسواق شاملة، فانتشارهما الواسع متوقّع ولا يدلّ على خلل.