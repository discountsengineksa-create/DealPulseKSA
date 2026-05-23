# Tests — Deal Pulse KSA

اختبارات المسارات الحرجة (auth, track, go, JWT, LLM cache, Financial Guardian).

## التهيئة (مرة واحدة)

### 1. أنشئ قاعدة بيانات اختبار على Railway

من لوحة Railway:
1. **New Project** → **Provision PostgreSQL** (يمكنك إعادة استخدام نفس الـ workspace).
2. سمّي الخدمة: `dealpulse-test-db`.
3. انسخ `DATABASE_PUBLIC_URL` من tab **Variables**.

### 2. شغّل المهاجرات على قاعدة الاختبار

```powershell
# في PowerShell
$env:TEST_DATABASE_URL = "postgresql://..."

# تطبيق المهاجرات بالترتيب
Get-Content db_export.sql | psql $env:TEST_DATABASE_URL
foreach ($f in (Get-ChildItem migration_*.sql | Sort-Object Name)) {
    Write-Host "Running $($f.Name)..."
    Get-Content $f.FullName | psql $env:TEST_DATABASE_URL
}
```

> ملاحظة: `db_export.sql` غير متعقّب في git الآن، فإن لم يكن لديك،
> استخرجه من قاعدة الإنتاج: `pg_dump --schema-only $DATABASE_URL > db_export.sql`

### 3. عيّن متغيرات الاختبار

أنشئ `tests/.env.test`:
```env
TEST_DATABASE_URL=postgresql://postgres:xxx@xxx.railway.app:xxxxx/railway
JWT_SECRET=test-secret-for-jwt-tokens-only-xxxx-xxxx
ADMIN_SHARED_SECRET=test-admin-secret
REDIS_URL=
# اختياري — لو موجود تشتغل اختبارات الـ LLM cache فعلاً
GROQ_API_KEY=
```

أو صدّرها مباشرة في الـ session:
```powershell
$env:TEST_DATABASE_URL = "..."
$env:JWT_SECRET = "test-secret-xxxx"
$env:ADMIN_SHARED_SECRET = "test-admin"
```

## تشغيل الاختبارات

```bash
# جميع الاختبارات
pytest tests/ -v

# اختبارات Auth فقط
pytest tests/test_auth.py -v

# تجاهل الاختبارات البطيئة (تلك التي تتطلب DB حقيقي)
pytest tests/ -v -m "not slow"

# اختبار واحد
pytest tests/test_auth.py::test_register_success -v
```

## بنية المجلد

```
tests/
├── README.md            ← هذا الملف
├── conftest.py          ← fixtures مشتركة (client, db, مستخدم تجريبي)
├── test_auth.py         ← 8 اختبارات: register/login/JWT/password
├── test_jwt.py          ← 3 اختبارات: create/decode/expired
├── test_track.py        ← 5 اختبارات: track action + idempotency + rate limit
├── test_go.py           ← 3 اختبارات: cloaked redirect + bot challenge
├── test_llm_cache.py    ← 3 اختبارات: cache hit/miss/expired
└── test_financial.py    ← 3 اختبارات: precharge/over-budget/refund
```

**الإجمالي: 25 اختباراً تغطي ~80% من المخاطر بـ ~20% من الجهد.**

## في CI لاحقاً

أضف للـ `.github/workflows/tests.yml`:
```yaml
- name: Run tests
  env:
    TEST_DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}
    JWT_SECRET: ${{ secrets.JWT_SECRET }}
    ADMIN_SHARED_SECRET: test-secret
  run: pytest tests/ -v
```
