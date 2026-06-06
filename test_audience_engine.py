"""اختبار سريع لمحرّك الشرائح — على بيانات حقيقية في Railway."""
import os, sys, json
from dotenv import load_dotenv
import psycopg2

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from api.audience_engine import (
    build_sql, count_audience, count_audience_breakdown,
    fetch_audience, sample_audience,
    save_segment, load_segment, list_segments,
    list_stores, list_categories,
)

url = os.getenv("DATABASE_URL") or os.getenv("MIGRATION_DATABASE_URL")
conn = psycopg2.connect(url)
conn.autocommit = True


def ok(name, fn):
    try:
        result = fn()
        print(f"✅ {name}: {result}")
        return result
    except Exception as e:
        print(f"❌ {name}: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        return None


print("\n" + "═" * 70)
print("اختبار 1 — قائمة فارغة (يفترض = كل المستخدمين)")
print("═" * 70)
empty_rules = {"version": 1, "logic": "or", "groups": []}
ok("count(telegram, empty)", lambda: count_audience(conn, "telegram", empty_rules))
ok("count(email, empty)",    lambda: count_audience(conn, "email",    empty_rules))


print("\n" + "═" * 70)
print("اختبار 2 — Attribute: lang='ar'")
print("═" * 70)
rules = {"version": 1, "logic": "or", "groups": [{
    "logic": "and",
    "rules": [{"type": "attribute", "field": "lang", "op": "=", "value": "ar"}]
}]}
ok("count(telegram, lang=ar)", lambda: count_audience(conn, "telegram", rules))
ok("count(email, lang=ar)",    lambda: count_audience(conn, "email",    rules))


print("\n" + "═" * 70)
print("اختبار 3 — Attribute Bool: has_email = True (تيليجرام)")
print("═" * 70)
rules = {"version": 1, "logic": "or", "groups": [{
    "logic": "and",
    "rules": [{"type": "attribute", "field": "has_email", "op": "=", "value": True}]
}]}
ok("count(telegram, has_email)", lambda: count_audience(conn, "telegram", rules))


print("\n" + "═" * 70)
print("اختبار 4 — Attribute Special: favorite_store (نجلب أول متجر من القائمة)")
print("═" * 70)
stores = list_stores(conn)
print(f"عدد المتاجر: {len(stores)} — مثال: {stores[:3]}")
if stores:
    test_store = stores[0]
    rules = {"version": 1, "logic": "or", "groups": [{
        "logic": "and",
        "rules": [{"type": "attribute", "field": "favorite_store",
                   "op": "=", "value": test_store}]
    }]}
    ok(f"count(both, favorite_store={test_store})",
       lambda: count_audience(conn, "both", rules))


print("\n" + "═" * 70)
print("اختبار 5 — Event: copy_coupon لأي متجر خلال آخر 30 يوم")
print("═" * 70)
rules = {"version": 1, "logic": "or", "groups": [{
    "logic": "and",
    "rules": [{"type": "event", "action": "copy_coupon",
               "entity_type": "any",
               "window": {"type": "last_days", "days": 30}}]
}]}
ok("count(telegram, copied last 30d)",
   lambda: count_audience(conn, "telegram", rules))


print("\n" + "═" * 70)
print("اختبار 6 — Aggregate absolute: copy_coupon ≥ 1 آخر 90 يوم")
print("═" * 70)
rules = {"version": 1, "logic": "or", "groups": [{
    "logic": "and",
    "rules": [{"type": "aggregate", "action": "copy_coupon",
               "entity_type": "any",
               "threshold_type": "absolute", "op": ">=", "value": 1,
               "window": {"type": "last_days", "days": 90}}]
}]}
ok("count(telegram, copy>=1 in 90d)",
   lambda: count_audience(conn, "telegram", rules))


print("\n" + "═" * 70)
print("اختبار 7 — Temporal: انضم خلال آخر 365 يوم")
print("═" * 70)
rules = {"version": 1, "logic": "or", "groups": [{
    "logic": "and",
    "rules": [{"type": "temporal", "field": "joined_at",
               "op": ">=", "value_days": 365}]
}]}
ok("count(telegram, joined<=365d)",
   lambda: count_audience(conn, "telegram", rules))


print("\n" + "═" * 70)
print("اختبار 8 — قاعدة مع NOT (negate)")
print("═" * 70)
rules = {"version": 1, "logic": "or", "groups": [{
    "logic": "and",
    "rules": [{"type": "attribute", "field": "lang", "op": "=",
               "value": "ar", "negate": True}]
}]}
ok("count(telegram, NOT lang=ar)",
   lambda: count_audience(conn, "telegram", rules))


print("\n" + "═" * 70)
print("اختبار 9 — تركيب: مجموعة (lang=ar AND has_email) OR مجموعة (joined<=30d)")
print("═" * 70)
rules = {
    "version": 1, "logic": "or",
    "groups": [
        {"logic": "and", "rules": [
            {"type": "attribute", "field": "lang", "op": "=", "value": "ar"},
            {"type": "attribute", "field": "has_email", "op": "=", "value": True},
        ]},
        {"logic": "and", "rules": [
            {"type": "temporal", "field": "joined_at", "op": ">=", "value_days": 30},
        ]},
    ],
}
ok("count(telegram, group1 OR group2)",
   lambda: count_audience(conn, "telegram", rules))


print("\n" + "═" * 70)
print("اختبار 10 — Breakdown على شريحة مركّبة")
print("═" * 70)
ok("breakdown", lambda: count_audience_breakdown(conn, rules))


print("\n" + "═" * 70)
print("اختبار 11 — Sample (10 صفوف للمعاينة)")
print("═" * 70)
empty_rules = {"version": 1, "logic": "or", "groups": []}
sample = sample_audience(conn, "telegram", empty_rules, n=3)
print(f"عيّنة (3 صفوف):")
for r in sample:
    print(f"  - {r.get('user_id')} · {r.get('handle')} · {r.get('lang')} · {r.get('email')}")


print("\n" + "═" * 70)
print("اختبار 12 — حفظ/تحميل شريحة")
print("═" * 70)
test_rules = {
    "version": 1, "logic": "or",
    "groups": [{"logic": "and", "rules": [
        {"type": "attribute", "field": "lang", "op": "=", "value": "ar"}
    ]}]
}
sid = save_segment(conn, name="🧪 اختبار: عرب فقط",
                   rules_json=test_rules, channel="both",
                   description="شريحة تجريبية — يمكن حذفها")
print(f"✅ حفظ شريحة جديدة: id={sid}")
loaded = load_segment(conn, sid)
print(f"✅ تحميل: name='{loaded['name']}', rules keys={list(loaded['rules_json'].keys())}")
# حذف الشريحة التجريبية
with conn.cursor() as cur:
    cur.execute("DELETE FROM audience_segments WHERE id = %s", (sid,))
print(f"✅ تنظيف: حُذفت الشريحة التجريبية")


print("\n" + "═" * 70)
print("اختبار 13 — SQL Injection probe (يجب أن يُرفض أو يُهرّب)")
print("═" * 70)
evil_rules = {"version": 1, "logic": "or", "groups": [{
    "logic": "and",
    "rules": [{"type": "attribute", "field": "lang",
               "op": "=", "value": "'; DROP TABLE bot_users; --"}]
}]}
ok("count(telegram, evil value)",
   lambda: count_audience(conn, "telegram", evil_rules))
# تحقق إن bot_users لا تزال موجودة
with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM bot_users")
    print(f"✅ bot_users سليم: {cur.fetchone()[0]} صف")


print("\n" + "═" * 70)
print("اختبار 14 — قاعدة بحقل غير معروف (يجب أن يفشل بأمان)")
print("═" * 70)
bad_rules = {"version": 1, "logic": "or", "groups": [{
    "logic": "and",
    "rules": [{"type": "attribute", "field": "evil_drop_table",
               "op": "=", "value": "x"}]
}]}
try:
    count_audience(conn, "telegram", bad_rules)
    print("❌ كان يفترض يرفع ValueError!")
except ValueError as e:
    print(f"✅ رُفض بأمان: {e}")


conn.close()
print("\n" + "═" * 70)
print("✅ كل الاختبارات انتهت")
print("═" * 70)
