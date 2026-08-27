"""
انتقال جلسة الويب من localStorage إلى كوكي HttpOnly.

**بلا قاعدة بيانات عمداً.** بقيّة اختبارات المصادقة تتخطّى نفسها حين يغيب
`TEST_DATABASE_URL` (١٩ من ٢٥ تتخطّى فعلياً)، وطبقة النقل التي تحمل الجلسة
أخطر من أن تعتمد على قاعدة قد لا تكون مُعدَّة. الاتصال يُستبدَل بمزيَّف،
والمُختبَر هو مسار HTTP الحقيقي: الـrouter والـdependency وسمات الكوكي.
"""
from __future__ import annotations

import os

# ⚠️ **قبل استيراد الـrouter، لا بعده.** `_COOKIE_SECURE` يُقرأ من البيئة **مرّة
# واحدة عند استيراد الوحدة**، وTestClient يخاطب `http://testserver` فلا يخزّن
# كوكي `Secure` على http. ضبطُه بعد الاستيراد لا يفعل شيئاً — كلّف اختباراً
# فاشلاً حتى تبيّن السبب. علَم الإنتاج (Secure=True) مغطّى في
# `test_secure_flag_set_when_enabled`.
os.environ["SESSION_COOKIE_SECURE"] = "false"

from contextlib import contextmanager  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.auth_utils import create_jwt_token, hash_password  # noqa: E402
from api.db import get_db  # noqa: E402
from api.routers import auth as auth_router  # noqa: E402
from api.routers.auth import SESSION_COOKIE  # noqa: E402

USER_ID = 4242
PASSWORD = "CorrectHorse!42"


def _fake_row() -> dict:
    return {
        "id": USER_ID,
        "display_name": "زائر تجريبي",
        "phone_number": "+966500000000",
        "email": "user@example.com",
        "password_hash": hash_password(PASSWORD),
        "city": None, "country": "SA", "lang": "ar", "gender": None,
        "birth_date": None, "telegram_username": None,
        "email_verified_at": None, "consent_at": None,
        "visited_clicks": 0, "store_copy_count": 0,
        "manual_favorites": [], "created_at": None,
    }


class _FakeCursor:
    def __init__(self, row): self._row = row
    def execute(self, *_a, **_k): return None
    def fetchone(self): return self._row
    def __enter__(self): return self
    def __exit__(self, *_a): return False


class _FakeConn:
    """يرجع نفس الصف لأي استعلام — الاختبار يخصّ النقل لا الاستعلامات."""
    def __init__(self, row): self._row = row
    @contextmanager
    def _cur(self): yield _FakeCursor(self._row)
    def cursor(self, *_a, **_k): return _FakeCursor(self._row)
    def commit(self): return None
    def rollback(self): return None


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api/v1")
    # الـrouter يحمل @limiter.limit — بلا state.limiter يرمي slowapi.
    from api.utils.rate_limit import limiter
    app.state.limiter = limiter
    limiter.enabled = False
    app.dependency_overrides[get_db] = lambda: _FakeConn(_fake_row())
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_cookie_jar(client):
    """TestClient واحد للوحدة كلّها ⇒ **جرّة كوكيز مشتركة**.

    بلا هذا التنظيف يرث اختبارُ «بلا اعتماد» كوكيَ اختبارِ الدخول فيرجع ٢٠٠
    ويمرّ كاذباً — وقع فعلاً: اختباران أخضران وهما لا يفحصان شيئاً.
    """
    client.cookies.clear()
    yield


def _valid_token() -> str:
    return create_jwt_token(USER_ID)


# ─── زرع الكوكي ──────────────────────────────────────────────────────────────
def test_login_sets_httponly_cookie(client):
    """الدخول يزرع الكوكي، وسماته الأمنية موجودة فعلاً في الترويسة."""
    res = client.post(
        "/api/v1/auth/login",
        json={"username": "user@example.com", "password": PASSWORD},
    )
    assert res.status_code == 200, res.text
    raw = res.headers.get("set-cookie", "")
    assert SESSION_COOKIE in raw
    assert "HttpOnly" in raw          # ← الغرض كلّه: JavaScript لا تقرأه
    assert "SameSite=lax" in raw.replace("samesite", "SameSite")
    assert "Path=/" in raw


def test_login_still_returns_token_in_json(client):
    """حقل token يبقى في الرد — الميني-آب (origin: null) لا يستقبل كوكيز."""
    res = client.post(
        "/api/v1/auth/login",
        json={"username": "user@example.com", "password": PASSWORD},
    )
    assert res.status_code == 200
    assert res.json().get("token")


def test_secure_flag_set_when_enabled(client, monkeypatch):
    """إعداد الإنتاج: `SESSION_COOKIE_SECURE` غير مضبوط ⇒ Secure مفعّل.

    مغطّى صراحةً لأن بقيّة الملف يشتغل بـSecure مطفأ (قيد TestClient على http)،
    فبلا هذا الاختبار قد يسقط العلَم في الإنتاج ولا يمسكه شيء.
    """
    monkeypatch.setattr(auth_router, "_COOKIE_SECURE", True)
    res = client.post(
        "/api/v1/auth/login",
        json={"username": "user@example.com", "password": PASSWORD},
    )
    assert "Secure" in res.headers.get("set-cookie", "")


def test_remember_me_extends_cookie_life(client):
    """عمر الكوكي يتبع عمر التوكن: ٣٠ يوماً مع remember_me لا ١٤."""
    res = client.post(
        "/api/v1/auth/login",
        json={"username": "user@example.com", "password": PASSWORD,
              "remember_me": True},
    )
    assert "Max-Age=2592000" in res.headers.get("set-cookie", "")  # 30×86400


# ─── القراءة المزدوجة ────────────────────────────────────────────────────────
def test_me_accepts_cookie_only(client):
    """الكوكي وحده يكفي — بلا أي ترويسة Authorization."""
    res = client.get("/api/v1/auth/me", cookies={SESSION_COOKIE: _valid_token()})
    assert res.status_code == 200, res.text
    assert res.json()["id"] == USER_ID


def test_me_accepts_bearer_only(client):
    """مسار الميني-آب لم يُكسر."""
    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {_valid_token()}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["id"] == USER_ID


def test_cookie_wins_over_stale_header(client):
    """الكوكي **يسبق** الترويسة.

    السيناريو الحقيقي للترحيل: كوكي طازج صالح + توكن عتيق باقٍ في localStorage.
    لو طغت الترويسة لبقي المستخدم على المسار القديم إلى الأبد.
    """
    res = client.get(
        "/api/v1/auth/me",
        cookies={SESSION_COOKIE: _valid_token()},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["id"] == USER_ID


def test_no_credentials_is_401_not_422(client):
    """غياب الاثنين = ٤٠١. كانت الترويسة إلزامية فيرد ٤٢٢ (خطأ تحقّق)،
    والواجهة تعامل ٤٠١ وحدها كانتهاء جلسة."""
    assert client.get("/api/v1/auth/me").status_code == 401


def test_malformed_header_is_401(client):
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Token abc"})
    assert res.status_code == 401


def test_expired_cookie_rejected(client):
    """كوكي بتوقيع صالح لكنه منتهٍ لا يمرّ."""
    expired = create_jwt_token(USER_ID, expiry_days=-1)
    res = client.get("/api/v1/auth/me", cookies={SESSION_COOKIE: expired})
    assert res.status_code == 401


# ─── الخروج ─────────────────────────────────────────────────────────────────
def test_logout_clears_cookie_without_auth(client):
    """الخروج يمسح الكوكي، ويعمل بلا مصادقة — من انتهت جلسته أحوج ما يكون له."""
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 200, res.text
    raw = res.headers.get("set-cookie", "")
    assert SESSION_COOKIE in raw
    assert 'Max-Age=0' in raw or 'expires=Thu, 01 Jan 1970' in raw.lower()


def test_session_dead_after_logout(client):
    """دورة كاملة على عميل واحد: دخول ← /me ينجح ← خروج ← /me يرفض."""
    c = client  # الجرّة نُظّفت أصلاً بـ_clean_cookie_jar
    assert c.post(
        "/api/v1/auth/login",
        json={"username": "user@example.com", "password": PASSWORD},
    ).status_code == 200
    assert c.get("/api/v1/auth/me").status_code == 200
    assert c.post("/api/v1/auth/logout").status_code == 200
    assert c.get("/api/v1/auth/me").status_code == 401
