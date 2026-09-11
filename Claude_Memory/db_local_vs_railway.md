---
name: Local DB Is Detached From Railway Prod
description: psycopg2.connect(host='localhost') hits a stale local DB; the real data lives on Railway via .env DATABASE_URL. Always read .env first.
type: project
originSessionId: 0fe41f94-3ccf-43d5-8719-71266c3cf888
---
قاعدة `discounts_engine` المحلية على localhost:5432 موجودة لكنها **مهجورة** (تحتوي صفوف اختبار فقط مثل «نون»، «999»، «كلود1»). الإنتاج الفعلي (٤٢ متجر) في Railway عبر `DATABASE_URL` في `.env` (postgres@turntable.proxy.rlwy.net:18475).

**Why:** الداشبورد والبوت كلاهما يقرأ `DATABASE_URL` أولاً (موصول إنتاج). نمط `get_conn()` بـ `host='localhost', password='123456'` المذكور في CLAUDE.md = نمط dev local فقط، لا ينطبق على البيانات الحقيقية. مثال 2026-06-26: فحصت localhost على «فوغا/هواوي/ايرالو» وحصلت صفر، فظننتها مفقودة — بينما فوغا كلوسيت (id=12) موجود في إنتاج Railway منذ 2026-06-17.

**How to apply:**
- أي سكربت تشغّله للتحقق من بيانات المتاجر/الكوبونات لازم يقرأ `DATABASE_URL` من `.env` قبل psycopg2.connect:
  ```python
  url = next((ln.split('=',1)[1].strip() for ln in open('.env',encoding='utf-8')
              if ln.strip().startswith('DATABASE_URL=') and not ln.startswith('#')), None)
  c = psycopg2.connect(url) if url else psycopg2.connect(dbname='discounts_engine', host='localhost', ...)
  ```
- المرور بـ `host='localhost'` مع `password='123456'` (نمط CLAUDE.md) يعطي قاعدة dummy ولا يعكس الإنتاج. هذا النمط مفيد فقط للاختبار المعزول.
- قبل أي ادعاء «المتجر X غير موجود» — نفّذ الاستعلام على الإنتاج عبر DATABASE_URL.

---

## 🔴 ٢٠٢٦-٠٨-٢٧ — `pytest tests/` كان يضرب الإنتاج، والحارس كان الحظّ

`tests/conftest.py` كان فيه `os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")`.
و`TEST_DATABASE_URL` **غير مضبوط أصلاً** على هذا الجهاز. فمتى حُمّل `.env` — ويكفي أن
يستورد ملفُ اختبارٍ واحدٌ `api.db` — انقلب `db_available` إلى `True` وصارت حزمة الاختبارات
تشتغل على **Railway الإنتاج**: `clean_users` يحذف من `web_users`، و`sample_store` يكتب
ويحذف في `master` و`action_logs`.

**كيف يُكشف:** الحزمة كانت «١٩ متخطّى» ثم صارت «٣٣ نجحت / ٤ فشلت» بلا تغيير في الاختبارات
نفسها. **قفزة عدد الاختبارات المنفَّذة = إشارة أن القاعدة صارت متاحة — افحص أيّ قاعدة.**

**الأثر:** صفر. المرشّحات ضيّقة (`pytest\_%@example.com` · `store_id LIKE 'pytest%'`)
وأُثبت بالعدّ: صفر صفّ `pytest_`، ١١ في `web_users` (الأحدث id=12 من ٠٨-١٥)، ٥٨ في `master`،
صفر في `password_reset_tokens`.

**العلاج:** `db_available` صار **`TEST_DATABASE_URL` وحده بلا سقوط**، ويرفع `RuntimeError`
لو ساوى `DATABASE_URL`. → commit `95f985a`.

**الدرس الأوسع:** «الاختبارات لا تلمس الإنتاج» كان **افتراضاً** لا حاجزاً. أي سقوط
(`A or B`) على اعتماد إنتاج هو لغم — لا يعمل حتى تتغيّر بيئة التشغيل تحتك.
راجع [[feedback_no_db_writes_without_permission]].
