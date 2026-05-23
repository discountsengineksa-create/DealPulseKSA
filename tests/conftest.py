"""
pytest fixtures مشتركة لجميع الاختبارات.

النمط:
    - يستخدم TEST_DATABASE_URL (قاعدة بيانات منفصلة عن الإنتاج).
    - يُنشئ FastAPI TestClient واحد لكل جلسة اختبار (session scope).
    - يُعيد المستخدمين/البيانات إلى حالة نظيفة قبل كل test (function scope).
    - يُعطّل الـ rate limiter في الاختبارات تلقائياً (وإلا تفشل في CI).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# ─── ضبط متغيرات البيئة قبل أي import للتطبيق ─────────────────────────────────
# JWT_SECRET لازم يكون موجود وإلا api/auth_utils.py يرفض الاستيراد.
# نضمن طوله ≥ 32 byte لإسكات تحذير InsecureKeyLengthWarning من PyJWT.
os.environ.setdefault(
    "JWT_SECRET",
    "test-secret-only-do-not-use-in-prod-" + "x" * 64,
)
os.environ.setdefault("ADMIN_SHARED_SECRET", "test-admin-secret-xxxx")
# لو فيه TEST_DATABASE_URL نستخدمه بدلاً من DATABASE_URL الإنتاج
if os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
# تعطيل الـ workers في الاختبارات (لا يحتاج Redis ولا scheduler)
os.environ.setdefault("DISABLE_WORKERS", "1")
# مسار الجذر — حتى نتمكن من import bot_app, api, deal_pulse_bot
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ─── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def db_available() -> bool:
    """يتحقق من وجود قاعدة بيانات اختبار صالحة. لو غير موجودة، يُخطّى الاختبار."""
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        return False
    try:
        import psycopg2  # type: ignore
        # postgres:// → postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url, connect_timeout=5)
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ TEST_DATABASE_URL غير متاح: {e}")
        return False


@pytest.fixture(scope="session")
def client(db_available):
    """
    FastAPI TestClient لـ api/main.py (الـ entrypoint الأنسب للاختبارات لأنه
    لا يتطلب BOT_TOKEN أو WEBHOOK_SECRET، خلافاً لـ bot_app.py).
    """
    if not db_available:
        pytest.skip("TEST_DATABASE_URL غير متاح — تخطّي اختبارات الـ DB")
    from fastapi.testclient import TestClient
    from api.main import app
    # تعطيل rate-limiter في الاختبارات (وإلا فشل اختبار التسلسل السريع)
    from api.utils.rate_limit import limiter
    limiter.enabled = False
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_conn(db_available):
    """اتصال DB مباشر للاختبارات التي تحتاج SQL خام (cleanup, fixtures)."""
    if not db_available:
        pytest.skip("TEST_DATABASE_URL غير متاح")
    from api.db import get_pool
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try: conn.autocommit = False
        except Exception: pass
        pool.putconn(conn)


@pytest.fixture
def clean_users(db_conn):
    """ينظّف جدول web_users + password_reset_tokens قبل وبعد كل اختبار."""
    # نستخدم example.com لأن EmailStr يرفض .local (RFC 6761 reserved TLD)
    sql = """
        DELETE FROM password_reset_tokens WHERE user_id IN (
            SELECT id FROM web_users WHERE email LIKE 'pytest_%@example.com'
        );
        DELETE FROM web_users WHERE email LIKE 'pytest_%@example.com';
    """
    with db_conn.cursor() as cur:
        cur.execute(sql)
    db_conn.commit()
    yield
    with db_conn.cursor() as cur:
        cur.execute(sql)
    db_conn.commit()


@pytest.fixture
def sample_store(db_conn):
    """يُنشئ متجراً تجريبياً لـ tests الـ track/go ثم يحذفه."""
    sid = "pytest_sample_store"
    slug = "pytest-slug"
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM master WHERE store_id = %s", (sid,))
        cur.execute(
            """
            INSERT INTO master (store_id, name_en, affiliate_link, cloaked_slug,
                                public_coupon, store_tags)
            VALUES (%s, 'Pytest Store', 'https://example.com/?ref=pytest', %s,
                    'PYTESTCODE', '{test,sample}')
            """,
            (sid, slug),
        )
    db_conn.commit()
    yield {"store_id": sid, "slug": slug}
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM action_logs WHERE store_id = %s", (sid,))
        cur.execute("DELETE FROM master WHERE store_id = %s", (sid,))
    db_conn.commit()
