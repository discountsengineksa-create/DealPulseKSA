# إعداد Admitad Postback — إسناد إيرادات حقيقية لكل متجر

> الهدف: تحويل المنصّة من «عدّاد نقرات» إلى «مقياس إيرادات حقيقية لكل متجر» —
> نلتقط كل عملية بيع تحدث عبر روابطنا Admitad تلقائياً، لحظة تحوّل حالتها في
> نظامهم (pending → approved → declined)، بلا تدخّل يدوي. هذه إشارة الجودة
> الوحيدة التي يهتم بها المستثمرون (analysis_rebuild_strategy) والمعلنون —
> «نقرات» كمقياس وحيد غير كافٍ.

---

## ماذا بنيتُ (جاهز في الكود، ينتظر خطوتَي إعداد يدوية)

1. **`migration_064_affiliate_conversions.sql`** — جدول جديد يحفظ كل تحويل
   (action_id, master_id, subid, order_id, sale_amount, commission, status,
   raw_query جسم البوستباك كامل). UPSERT على (network, action_id) حتى تنعكس
   انتقالات الحالة على نفس الصف.
2. **`GET /api/v1/admin/pb-admitad`** — نقطة استقبال الـpostback من Admitad،
   مصادقة بـ URL token (لأن Admitad لا يدعم headers مخصّصة على S2S).
   تحلّل الماكرو (subid, order_id, order_sum, ...) وتـUPSERT الصف.
3. **حقن SubID في `/go/{slug}`** — عندما يكون رابط الأفلييت على نطاق Admitad
   (admitad.com / rzekl.com / wbbsv.com / gotolink.pro / mitgo.com)، نُلحق
   تلقائياً `subid={master_id}_{visitor_id_short}`. Admitad يعيدها في
   البوستباك فنربط البيع بالنقرة والمتجر بدقّة.

---

## الخطوات اليدوية المتبقّية (تنفّذها أنت، تستغرق ~٥ دقائق)

### ١) طبّق المايقريشن على Railway
```bash
python api/run_migration.py migration_064_affiliate_conversions.sql
```
(يستخدم `MIGRATION_DATABASE_URL` من `.env` — نفس نمط 060–063.)

### ٢) ولّد سرّ الـtoken وضعه في مكانين
```bash
openssl rand -hex 24
# مثال ناتج: 3f8a1c4e9b2d... (~48 حرفاً)
```
- Railway → **DEALPULSEKSA** → Variables → أضف `POSTBACK_ADMITAD_TOKEN=<القيمة>`.
- سيعمل بعد Redeploy تلقائي.

### ٣) اضبط Postback URL في لوحة Admitad
1. adfulseksa.mitgo.com → **My tools** → **Postback URL** (أو Websites → DealPulseKSA → Postback).
2. اختر: **Global Postback** (يشمل كل البرامج المقبولة).
3. Postback URL — ألصق **بالضبط** هذا (استبدل `<TOKEN>` بالقيمة من الخطوة ٢):

```
https://api.dealpulseksa.com/api/v1/admin/pb-admitad?token=<TOKEN>&action_id=[[[action_id]]]&order_id=[[[order_id]]]&offer_id=[[[offer_id]]]&subid=[[[subid]]]&status=[[[status]]]&type=[[[type]]]&currency=[[[currency]]]&order_sum=[[[order_sum]]]&payment_sum=[[[payment_sum]]]&reward_ready=[[[reward_ready]]]&click_time=[[[click_time]]]&conversion_time=[[[conversion_time]]]&action_ip=[[[action_ip]]]&user_agent=[[[user_agent]]]
```

4. HTTP method: **GET**. Trigger: **on every status change** (يرسل واحد pending
   لحظة البيع، ثم واحد approved/declined لاحقاً — النظام يـUPSERT على نفس
   `action_id`).
5. اضغط **Save**.

### ٤) اختبر
- Admitad توفّر زر «Test postback» بعد الحفظ — اضغطه، ثم في Railway logs يظهر
  صف واحد `{"ok":true,"action_id":"test-...",...}` من الـendpoint.
- أو من طرفك: افتح المتصفّح على الرابط أعلاه مع `action_id=manual-test-1&subid=48_abc&order_sum=250.00&currency=SAR&status=pending` → يظهر صفٌّ في جدول `affiliate_conversions` بـ `master_id=48`.

---

## ما بعد التفعيل

- كل بيعة → صف في `affiliate_conversions` مربوط بـ `master.id` عبر subid.
- استعلامات جاهزة (لعرضها في الداشبورد لاحقاً):
  ```sql
  -- إيرادات آخر 30 يوم لكل متجر (approved فقط)
  SELECT m.store_id,
         COUNT(*) AS sales,
         SUM(ac.payment_sum) AS gross_sar,
         SUM(ac.reward_ready) AS commission_sar
  FROM affiliate_conversions ac
  JOIN master m ON m.id = ac.master_id
  WHERE ac.network='admitad'
    AND ac.status='approved'
    AND ac.conversion_time > NOW() - INTERVAL '30 days'
  GROUP BY m.store_id
  ORDER BY commission_sar DESC;

  -- معدّل تحويل النقرة → البيعة لكل متجر (last 30d)
  SELECT m.store_id,
         SUM(CASE WHEN ac.status='approved' THEN 1 ELSE 0 END) AS sales,
         m.total_link_clicks AS clicks,
         ROUND(100.0 * SUM(CASE WHEN ac.status='approved' THEN 1 ELSE 0 END)
               / NULLIF(m.total_link_clicks, 0), 3) AS conv_rate_pct
  FROM master m
  LEFT JOIN affiliate_conversions ac
    ON ac.master_id = m.id
   AND ac.conversion_time > NOW() - INTERVAL '30 days'
  WHERE m.publish_channels IS NULL
     OR m.publish_channels ILIKE '%website%'
  GROUP BY m.id, m.store_id, m.total_link_clicks
  ORDER BY sales DESC;
  ```

## قنوات أخرى (تكمّلها لاحقاً بنفس النمط)

- **Salla**: يوفّر Webhook للطلبات (postback مختلف الحقول). نضيف
  `/pb-salla` لاحقاً بنفس البنية — `network='salla'` في نفس الجدول.
- **CodeMap** / **Impact**: نفس الشيء عند التفعيل.

## القيود

- **الجيو والـUA في البوستباك** = من طرف Admitad (البائع)، لا من طرفنا.
  تفيد للتدقيق فقط. الجيو الحقيقي عندنا هو `action_logs.city` وقت النقرة.
- **status='pending'** لا يعني بيعة مؤكّدة. لا تعرض إيرادات على الداشبورد
  إلا من `status='approved'`.
- Admitad قد يُقلّص السقف الزمني (default ~30 يوم مثلاً) بين نقرة وتحويل —
  إذا تجاوز، تصلنا بلا subid فيصير `master_id=NULL`. نفسّرها كـ«تحويل غير
  مُسند» في التحليلات.
