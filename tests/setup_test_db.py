"""
سكربت تهيئة قاعدة بيانات الاختبار.

يطبّق المهاجرات الـ16 بالترتيب على القاعدة المحدّدة في TEST_DATABASE_URL.

الاستخدام:
    # 1. عيّن المتغير (PowerShell)
    $env:TEST_DATABASE_URL = "postgresql://..."

    # 2. شغّل السكربت
    python tests/setup_test_db.py

    # 3. (اختياري) لإعادة التهيئة من الصفر (يمسح كل الجداول!)
    python tests/setup_test_db.py --reset

الناتج المتوقع:
    ✅ Connected to: postgres-q8mb.railway.internal:5432/railway
    📋 Applying migration_001_action_logs_user_id.sql ... OK
    📋 Applying migration_002_web_support.sql ... OK
    ...
    📋 Applying migration_016_crosscutting.sql ... OK
    ✅ All 16 migrations applied successfully.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# قاعدة: لا نستورد api/ هنا لأننا نريد السكربت يعمل بلا أي حالة محملة
try:
    import psycopg2
except ImportError:
    print("❌ psycopg2 غير مثبّت. شغّل: pip install psycopg2-binary")
    sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent


def _connect(url: str):
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, connect_timeout=10)


def _reset_schema(conn) -> None:
    """يمسح كل الجداول العامة (للبدء من نظافة كاملة)."""
    print("⚠️  --reset مُفعّل: مسح schema 'public' وإعادة إنشائها...")
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE;")
        cur.execute("CREATE SCHEMA public;")
        cur.execute("GRANT ALL ON SCHEMA public TO PUBLIC;")
    conn.commit()
    print("   ✅ Schema reset.")


def _ensure_base_tables(conn) -> None:
    """
    قاعدة الاختبار قد تكون فارغة تماماً. المهاجرات تفترض وجود جداول أساسية
    مثل master, action_logs, bot_users, direct_search... الموجودة في
    db_export.sql (غير المتعقّب). نُنشئ الحد الأدنى منها هنا لو غير موجودة.

    ⚠️ هذا تبسيط متعمَّد: ننشئ الأعمدة الأساسية فقط؛ بقية الأعمدة تُضاف
    بواسطة المهاجرات. لا يحاكي 100% schema الإنتاج لكن يكفي للاختبارات.
    """
    print("📦 إنشاء جداول الأساس (لو غير موجودة)...")
    base_sql = """
    -- master: جدول المتاجر الرئيسي
    CREATE TABLE IF NOT EXISTS master (
        id              SERIAL PRIMARY KEY,
        store_id        TEXT UNIQUE NOT NULL,
        name_en         TEXT,
        affiliate_link  TEXT,
        public_coupon   TEXT,
        extra_offer     TEXT,
        store_bio       TEXT,
        store_tags      TEXT,
        my_coupon       TEXT,
        priority_score  INTEGER DEFAULT 0,
        discount_value  TEXT,
        first_time      TIMESTAMP DEFAULT NOW(),
        last_time       TIMESTAMP,
        total_link_clicks    INTEGER DEFAULT 0,
        total_coupon_copies  INTEGER DEFAULT 0,
        total_search_hits    INTEGER DEFAULT 0,
        copy_clicks     INTEGER DEFAULT 0,
        link_clicks     INTEGER DEFAULT 0,
        click_count     INTEGER DEFAULT 0,
        total_clicks    INTEGER DEFAULT 0,
        is_trending     TEXT DEFAULT 'عادي',
        performance_status TEXT,
        visit_categorie TEXT,
        target_category TEXT
    );

    -- action_logs: سجل أحداث المستخدمين
    CREATE TABLE IF NOT EXISTS action_logs (
        id              BIGSERIAL PRIMARY KEY,
        store_id        TEXT,
        action_type     TEXT,
        action_time     TIMESTAMP DEFAULT NOW(),
        details         TEXT
    );

    -- bot_users: مستخدمو تيليجرام
    CREATE TABLE IF NOT EXISTS bot_users (
        telegram_id     BIGINT PRIMARY KEY,
        first_name      TEXT,
        username        TEXT,
        first_seen      TIMESTAMP DEFAULT NOW(),
        last_seen       TIMESTAMP,
        manual_favorites TEXT[],
        fav_store_inferred TEXT,
        device_type     TEXT,
        deleted_at      TIMESTAMPTZ NULL    -- PDPL (migration_017)
    );

    -- direct_search: سجل كلمات البحث
    CREATE TABLE IF NOT EXISTS direct_search (
        id              SERIAL PRIMARY KEY,
        search_keyword  TEXT NOT NULL,
        store_id        TEXT,
        user_found      BOOLEAN DEFAULT FALSE,
        platform        TEXT,
        name_en         TEXT,
        user_id         BIGINT,
        user_email      TEXT,
        searched_at     TIMESTAMP DEFAULT NOW()
    );

    -- unavailable_codes_requests: طلبات أكواد متاجر غير موجودة
    CREATE TABLE IF NOT EXISTS unavailable_codes_requests (
        id              SERIAL PRIMARY KEY,
        brand_name      TEXT NOT NULL,
        user_email      TEXT,
        user_id         BIGINT,
        requested_at    TIMESTAMP DEFAULT NOW()
    );

    -- sent_coupon_messages: ربط رسائل تيليجرام بالمتاجر
    CREATE TABLE IF NOT EXISTS sent_coupon_messages (
        chat_id     BIGINT NOT NULL,
        message_id  BIGINT NOT NULL,
        store_id    TEXT NOT NULL,
        user_id     BIGINT,
        sent_at     TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (chat_id, message_id)
    );

    -- Extensions يحتاجها بعض المهاجرات
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    """
    with conn.cursor() as cur:
        cur.execute(base_sql)
    conn.commit()
    print("   ✅ جداول الأساس جاهزة.")


def _apply_migrations(conn) -> tuple[int, int]:
    """يطبّق ملفات migration_*.sql بالترتيب الرقمي. يرجع (مُنفَّذ, متخطّى)."""
    files = sorted(ROOT.glob("migration_*.sql"))
    if not files:
        print("⚠️  لا توجد ملفات migration_*.sql في الجذر.")
        return 0, 0

    applied, skipped = 0, 0
    for path in files:
        sql = path.read_text(encoding="utf-8")
        print(f"📋 {path.name} ...", end=" ", flush=True)
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            print("OK")
            applied += 1
        except psycopg2.Error as e:
            conn.rollback()
            # كثير من المهاجرات idempotent (IF NOT EXISTS) لكن بعضها
            # قد يفشل لو طُبّق مرتين. نسجّل ونكمل.
            msg = str(e).splitlines()[0][:120]
            print(f"⚠️  تخطّى ({msg})")
            skipped += 1
    return applied, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="تهيئة قاعدة بيانات اختبار Deal Pulse KSA.")
    parser.add_argument("--reset", action="store_true",
                        help="مسح schema 'public' كاملاً قبل تطبيق المهاجرات (⚠️ مدمّر)")
    args = parser.parse_args()

    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        print("❌ TEST_DATABASE_URL غير معرّف. عيّنه أولاً:")
        print('   $env:TEST_DATABASE_URL = "postgresql://..."')
        return 1

    try:
        conn = _connect(url)
    except psycopg2.OperationalError as e:
        print(f"❌ فشل الاتصال: {str(e).splitlines()[0]}")
        print("   تأكّد أن TEST_DATABASE_URL يستخدم DATABASE_PUBLIC_URL (وليس .railway.internal)")
        return 2

    # طبع host:port/db فقط (بدون كلمة السر)
    host_info = url.split("@")[-1] if "@" in url else url
    print(f"✅ Connected to: {host_info}")

    try:
        if args.reset:
            _reset_schema(conn)

        _ensure_base_tables(conn)
        applied, skipped = _apply_migrations(conn)
        print()
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"✅ المُنفَّذ: {applied}   ⚠️ المتخطّى: {skipped}")
        print()
        print("الآن شغّل: pytest tests/ -v")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
