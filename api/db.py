"""
Connection Pool مستقل للـ FastAPI.
لا نستورد من dashboard.py لأن استيراده يُشغّل كود Streamlit كاملاً.
كلا التطبيقين يقرآن نفس .env ويتصلان بنفس قاعدة البيانات.
"""
import os
import threading
from collections.abc import Generator
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2 import extras
from dotenv import load_dotenv

load_dotenv()

_pool: pg_pool.ThreadedConnectionPool | None = None
_lock = threading.Lock()


def get_pool() -> pg_pool.ThreadedConnectionPool:
    """Singleton للـ Pool — يُنشأ مرة واحدة فقط طوال حياة السيرفر.

    الإنتاج (Railway/Render): يستخدم DATABASE_URL إذا توفّر.
    التطوير المحلي: يقع على المتغيرات المنفصلة DB_NAME/DB_USER/...
    """
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:   # double-checked locking لأمان الـ threads
                db_url = os.getenv("DATABASE_URL")
                if db_url:
                    # Railway يُعطي postgres:// لكن psycopg2 يحتاج postgresql://
                    if db_url.startswith("postgres://"):
                        db_url = db_url.replace("postgres://", "postgresql://", 1)
                    _pool = pg_pool.ThreadedConnectionPool(
                        minconn=2,
                        maxconn=20,
                        dsn=db_url,
                        # كل الأعمدة timestamptz → الجلسة بتوقيت الرياض تجعل القراءة/الكتابة
                        # والمقارنات الزمنية (now()/CURRENT_DATE) بتوقيت السعودية تلقائياً.
                        options="-c timezone=Asia/Riyadh",
                    )
                else:
                    _pool = pg_pool.ThreadedConnectionPool(
                        minconn=2,
                        maxconn=20,
                        dbname=os.getenv("DB_NAME"),
                        user=os.getenv("DB_USER"),
                        password=os.getenv("DB_PASSWORD"),
                        host=os.getenv("DB_HOST"),
                        port=os.getenv("DB_PORT"),
                        options="-c timezone=Asia/Riyadh",
                    )
    return _pool


def get_db() -> Generator:
    """
    FastAPI Dependency (via Depends).
    يسحب اتصالاً من الـ Pool، يُمرّره للـ endpoint،
    ثم يُعيده نظيفاً بعد انتهاء الطلب — حتى لو رُمي exception.
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        # إعادة الاتصال لحالته الافتراضية قبل إعادته للـ Pool
        # يمنع تسرّب autocommit=True أو transactions معلقة للطلب التالي
        try:
            conn.autocommit = False
            conn.rollback()
        except Exception:
            pass
        pool.putconn(conn)


@contextmanager
def get_db_context():
    """
    Context-manager للـ background workers (خارج FastAPI request).

    استخدام:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")

    يُؤكّد commit عند الخروج النظيف، rollback عند exception،
    ويُعيد الاتصال للـ Pool في كل الحالات.
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            conn.autocommit = False
            conn.rollback()
        except Exception:
            pass
        pool.putconn(conn)
