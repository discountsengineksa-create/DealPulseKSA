"""
تشغيل ملف مايقريشن على قاعدة الإنتاج — بديل psql.

psql غير مثبّت على أجهزة المالك، وأوامر بايثون الطويلة في سطر واحد تنكسر في
PowerShell بسبب الاقتباسات المتداخلة. هذا السكربت يحلّ الاثنين.

الاستخدام:
    python run_migration.py migration_069_season_reminders.sql
    python run_migration.py --check season_reminders

الاتصال من DATABASE_URL في .env — لا يُمرَّر أي سرّ في سطر الأوامر.
"""
from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv


def _connect():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("❌ DATABASE_URL غير موجود في .env")
    conn = psycopg2.connect(url)
    conn.autocommit = True  # DDL لا يحتاج معاملة صريحة
    return conn


def check(table: str) -> None:
    """يعرض حالة جدول: هل هو موجود، وكم عموداً وصفاً فيه."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                (table,),
            )
            cols = cur.fetchall()
            if not cols:
                print(f"❌ الجدول «{table}» غير موجود")
                return
            print(f"✅ الجدول «{table}» موجود — {len(cols)} عموداً:")
            for name, dtype in cols:
                print(f"   • {name} — {dtype}")

            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            print(f"   الصفوف: {cur.fetchone()[0]}")

            cur.execute(
                "SELECT indexname FROM pg_indexes WHERE tablename = %s", (table,)
            )
            idx = [r[0] for r in cur.fetchall()]
            print(f"   الفهارس ({len(idx)}): {', '.join(idx)}")
    finally:
        conn.close()


def apply(path: str) -> None:
    if not os.path.exists(path):
        sys.exit(f"❌ الملف غير موجود: {path}")

    with open(path, encoding="utf-8") as fh:
        sql = fh.read()

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        print(f"✅ طُبِّق: {os.path.basename(path)}")
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"❌ فشل التطبيق: {exc}")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "--check":
        if len(sys.argv) < 3:
            sys.exit("الاستخدام: python run_migration.py --check <table>")
        check(sys.argv[2])
    else:
        apply(sys.argv[1])
