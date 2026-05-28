"""تطبيق ملف مايقريشن على قاعدة Railway.

الاستخدام:
    python api/run_migration.py migration_022_perf_and_cleanup.sql

الرابط يُقرأ من البيئة (لا تضع كلمة السر في الكود). ضعه في .env المحلي
(مُتجاهَل من git):
    MIGRATION_DATABASE_URL=postgresql://USER:PASS@HOST:PORT/DB   (رابط Railway الخارجي/proxy)
"""
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

# كونسول ويندوز (cp1256) يطيح على الإيموجي/العربي — أجبر UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

db_url = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
if not db_url:
    sys.exit("❌ ضع MIGRATION_DATABASE_URL في .env (رابط Railway الخارجي) قبل التشغيل.")

if len(sys.argv) < 2:
    sys.exit("الاستخدام: python api/run_migration.py <migration_file.sql>")
migration_file = sys.argv[1]

try:
    print(f"🔄 تطبيق {migration_file} على قاعدة Railway...")
    with open(migration_file, "r", encoding="utf-8") as f:
        sql_script = f.read()

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    cursor.execute(sql_script)
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ تم تطبيق {migration_file} بنجاح.")
except Exception as e:
    sys.exit(f"❌ خطأ أثناء التطبيق: {e}")
