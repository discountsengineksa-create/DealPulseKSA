"""
8 اختبارات Auth — register, login, password policy, rate limit (معطّل في tests).

كل test يبدأ ببيانات نظيفة بفضل fixture `clean_users`.
"""
from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────────
#  Register
# ─────────────────────────────────────────────────────────────────────────────
def test_register_success(client, clean_users):
    """تسجيل ناجح يرجع JWT + بيانات المستخدم."""
    resp = client.post("/api/v1/auth/register", json={
        "display_name": "اختبار المستخدم",
        "phone_number": "0501234567",
        "email": "pytest_ok@example.com",
        "password": "SecurePass123",
        "city": "الرياض",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "token" in data and len(data["token"]) > 40
    assert data["user"]["email"] == "pytest_ok@example.com"
    assert data["user"]["phone_number"] == "+966501234567"


def test_register_duplicate_email(client, clean_users):
    """التسجيل بإيميل موجود يرجع 409."""
    payload = {
        "display_name": "أول",
        "phone_number": "0501111111",
        "email": "pytest_dup@example.com",
        "password": "SecurePass123",
        "city": "جدة",
    }
    r1 = client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    # نفس الإيميل، رقم مختلف
    payload2 = {**payload, "phone_number": "0502222222"}
    r2 = client.post("/api/v1/auth/register", json=payload2)
    assert r2.status_code == 409
    assert "إيميل" in r2.json()["detail"]


def test_register_invalid_phone(client, clean_users):
    """رقم جوال غير صحيح يرجع 422."""
    resp = client.post("/api/v1/auth/register", json={
        "display_name": "بدون رقم",
        "phone_number": "12345",  # غير صحيح
        "email": "pytest_badphone@example.com",
        "password": "SecurePass123",
        "city": "الدمام",
    })
    assert resp.status_code == 422


def test_register_weak_password_rejected(client, clean_users):
    """كلمة سر < 8 أحرف ترجع 422 (السياسة الجديدة بعد التعديل)."""
    resp = client.post("/api/v1/auth/register", json={
        "display_name": "كلمة سر ضعيفة",
        "phone_number": "0503333333",
        "email": "pytest_weak@example.com",
        "password": "abc12",  # فقط 5 أحرف
        "city": "الرياض",
    })
    assert resp.status_code == 422
    # Pydantic يرجع تفاصيل validation
    body = resp.json()
    assert any("password" in str(e).lower() for e in body.get("detail", []))


# ─────────────────────────────────────────────────────────────────────────────
#  Login
# ─────────────────────────────────────────────────────────────────────────────
def test_login_success(client, clean_users):
    """تسجيل دخول صحيح بعد إنشاء حساب."""
    client.post("/api/v1/auth/register", json={
        "display_name": "للدخول",
        "phone_number": "0504444444",
        "email": "pytest_login@example.com",
        "password": "MyPassword123",
        "city": "الرياض",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "pytest_login@example.com",
        "password": "MyPassword123",
    })
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_login_wrong_password(client, clean_users):
    """كلمة سر خاطئة ترجع 401 برسالة عامة (لا تكشف وجود الحساب)."""
    client.post("/api/v1/auth/register", json={
        "display_name": "للدخول",
        "phone_number": "0505555555",
        "email": "pytest_wrongpw@example.com",
        "password": "RightPassword123",
        "city": "الرياض",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "pytest_wrongpw@example.com",
        "password": "WrongPassword999",
    })
    assert resp.status_code == 401


def test_login_nonexistent_user(client, clean_users):
    """دخول بحساب غير موجود يرجع 401 بنفس الرسالة (لا enumeration)."""
    resp = client.post("/api/v1/auth/login", json={
        "username": "doesnotexist@example.com",
        "password": "anything12345",
    })
    assert resp.status_code == 401
    # نفس الـ detail كما في كلمة السر الخاطئة → ضمان عدم كشف وجود الحساب
    assert resp.json()["detail"] == "بيانات الدخول غير صحيحة"


def test_login_phone_format_normalization(client, clean_users):
    """الدخول بصيغ مختلفة لرقم الجوال (05xxx, 5xxx, +9665xxx) يعمل كلها."""
    client.post("/api/v1/auth/register", json={
        "display_name": "صيغ متعددة",
        "phone_number": "0506666666",   # يُحفظ كـ +966506666666
        "email": "pytest_phone@example.com",
        "password": "PhonePass123",
        "city": "الرياض",
    })
    # حاول الدخول بـ 3 صيغ
    for username in ["0506666666", "506666666", "+966506666666"]:
        resp = client.post("/api/v1/auth/login", json={
            "username": username,
            "password": "PhonePass123",
        })
        assert resp.status_code == 200, f"فشل دخول بـ {username}"
