# DealPulse Edge Enrichment Worker

يعترض كل طلبات `POST /api/v1/track*` على دومين `dealpulseksa.com`،
يُثريها بإشارات Cloudflare الجغرافية والشبكية، ويُحوّلها للسيرفر على Railway.

## ماذا يُضيف للطلب؟

| Header | المصدر | الوصف |
|---|---|---|
| `x-dp-event-id` | UUID جديد لكل طلب | حماية idempotency |
| `x-dp-ip-hash` | SHA-256(IP + daily_salt) | عدّ زوّار فريدين بدون تخزين IP |
| `x-dp-ua-hash` | SHA-256(UA) | repeat-visitor stitching |
| `x-dp-country` | `cf.country` | ISO 3166-1 alpha-2 |
| `x-dp-region` | `cf.regionCode` | ISO 3166-2 |
| `x-dp-city` | `cf.city` | اسم المدينة |
| `x-dp-postal` | `cf.postalCode` | الرمز البريدي |
| `x-dp-lat` / `x-dp-lng` | `cf.latitude/longitude` | إحداثيات تقريبية |
| `x-dp-asn` | `cf.asn` | رقم BGP ASN |
| `x-dp-isp` | `cf.asOrganization` | اسم مزوّد الإنترنت |
| `x-dp-device` | تصنيف من User-Agent | mobile/desktop/tablet/bot |
| `x-dp-bot-score` | `cf.botManagement.score` | 0..100 (humans قرب 100) |
| `x-dp-verified-bot` | `cf.botManagement.verifiedBot` | 1 لو bot موثّق (Google, Bing) |

`cf-connecting-ip` و `x-real-ip` و `x-forwarded-for` تُحذف قبل التوجيه.

## النشر

```bash
# تثبيت wrangler مرة واحدة
npm install -g wrangler

# تسجيل الدخول
wrangler login

# إضافة salt للـ IP hashing (سرّي)
wrangler secret put IP_HASH_SALT
# (الصق سلسلة 32+ حرف عشوائي — مثلاً ناتج `openssl rand -base64 48`)

# تحديث account_id في wrangler.toml من Cloudflare dashboard
# ثم النشر:
wrangler deploy
```

## التحقق

بعد النشر، نفّذ طلب فعلي على دومين الإنتاج:

```bash
curl -sS -X POST https://dealpulseksa.com/api/v1/track \
  -H "Content-Type: application/json" \
  -d '{"store_id":"نون","action":"click_link","source":"web"}' \
  -i | head -20
```

في لوجات Railway للـ api service، يجب أن ترى INSERT بقيم geo (country=SA إن كنت في السعودية).

## فحوصات أمان مهمّة

- لا تعدّل `IP_HASH_SALT` مرتين في نفس اليوم — هذا يكسر عدّ الـ uniques.
- `cf.botManagement` يحتاج Cloudflare Bot Management الذي قد يكون paid على الـ Pro Plan،
  لكن `cf.botManagement.score` متاح بدرجات معينة حتى على Free Plan.
- لو `wrangler deploy` فشل بسبب `account_id`، أضف السطر `account_id = "..."` في `wrangler.toml`.
