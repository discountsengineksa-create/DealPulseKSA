"""اختبار end-to-end لـ tracking: pixel + click + report."""
import os, sys, time
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

# نضبط TRACKING_BASE_URL لاختبار محلي
os.environ["TRACKING_BASE_URL"] = "http://test.example/api"

import psycopg2
from fastapi.testclient import TestClient

from api.audience_engine import save_segment, delete_segment
from api.audience_sender import (send_email_broadcast, send_telegram_broadcast,
                                 broadcast_report)
from api.utils import broadcast_tracker as bt
from api.routers import broadcast_tracking
from fastapi import FastAPI


def header(t):
    print("\n" + "═"*70); print(t); print("═"*70)


# ─────────────────────────────────────────────────────────────────────────
# 1. ركّب FastAPI صغيرة بـ broadcast_tracking router فقط
# ─────────────────────────────────────────────────────────────────────────
header("1. تهيئة FastAPI TestClient")
app = FastAPI()
app.include_router(broadcast_tracking.router)
client = TestClient(app)
print("✅ FastAPI + router جاهزان")

c = psycopg2.connect(os.getenv("DATABASE_URL") or os.getenv("MIGRATION_DATABASE_URL"))
c.autocommit = True

# ─────────────────────────────────────────────────────────────────────────
# 2. تحقّق من helper functions
# ─────────────────────────────────────────────────────────────────────────
header("2. broadcast_tracker helpers")
print("is_tracking_enabled =", bt.is_tracking_enabled())
print("token sample:", bt.generate_token())
test_body = 'مرحباً! زر https://example.com/offer1 و <a href="https://example.com/offer2">العرض</a>'
urls = bt.extract_urls(test_body)
print("URLs المستخرجة:", urls)
assert "https://example.com/offer1" in urls
assert "https://example.com/offer2" in urls
print("✅ extract_urls يعمل")

# ─────────────────────────────────────────────────────────────────────────
# 3. اختبار /bt/o/{token}.gif (pixel)
# ─────────────────────────────────────────────────────────────────────────
header("3. اختبار pixel endpoint")
# اختر مستلم بـ tracking_token من حملة سابقة (لو موجود)
cur = c.cursor()
cur.execute("""
    SELECT br.id, br.tracking_token, br.broadcast_kind
    FROM broadcast_recipients br WHERE br.tracking_token IS NULL
    ORDER BY br.id DESC LIMIT 1
""")
old_recipient = cur.fetchone()

# لو ما في recipient بـ token، نولّد واحد للاختبار
test_token = bt.generate_token()
cur.execute("""
    INSERT INTO broadcast_recipients
    (broadcast_id, broadcast_kind, user_identifier, user_db_id,
     tracking_token, status)
    VALUES (1, 'email', 'test@example.com', 'test', %s, 'sent')
    RETURNING id
""", (test_token,))
test_rid = cur.fetchone()[0]
print(f"أنشأنا recipient اختباري #{test_rid} بـ token={test_token[:8]}...")

# نطلب pixel
r = client.get(f"/bt/o/{test_token}.gif")
print(f"pixel HTTP status: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type')}")
print(f"Content-Length: {len(r.content)} byte")
assert r.status_code == 200
assert r.headers["content-type"] == "image/gif"
assert 30 < len(r.content) < 60  # GIF 1x1 شفاف صغير

# تحقّق إن DB انتعش
cur.execute("SELECT open_count, opened_at, status FROM broadcast_recipients WHERE id=%s", (test_rid,))
row = cur.fetchone()
print(f"بعد طلب pixel: open_count={row[0]}, opened_at={row[1]}, status={row[2]}")
assert row[0] == 1, "open_count لازم =1"
assert row[1] is not None, "opened_at لازم يُعبّأ"
print("✅ pixel سجّل الفتح في DB")

# طلب pixel ثاني — يفترض open_count يصير 2
client.get(f"/bt/o/{test_token}.gif")
cur.execute("SELECT open_count FROM broadcast_recipients WHERE id=%s", (test_rid,))
oc = cur.fetchone()[0]
print(f"بعد فتح ثاني: open_count={oc}")
assert oc == 2
print("✅ فتح مكرر يُحسب صحيح")

# ─────────────────────────────────────────────────────────────────────────
# 4. اختبار /bt/c/{token}/{lid} (click + redirect)
# ─────────────────────────────────────────────────────────────────────────
header("4. اختبار click endpoint")
# سجّل link target
cur.execute("""
    INSERT INTO broadcast_link_targets (broadcast_id, broadcast_kind, original_url)
    VALUES (1, 'email', 'https://dealpulseksa.com/test-offer')
    ON CONFLICT DO NOTHING RETURNING id
""")
row = cur.fetchone()
if row:
    test_lid = row[0]
else:
    cur.execute("""SELECT id FROM broadcast_link_targets
                   WHERE original_url='https://dealpulseksa.com/test-offer'""")
    test_lid = cur.fetchone()[0]
print(f"link_target_id = {test_lid}")

r = client.get(f"/bt/c/{test_token}/{test_lid}", follow_redirects=False)
print(f"click HTTP status: {r.status_code}")
print(f"Location: {r.headers.get('location')}")
assert r.status_code == 302
assert r.headers["location"] == "https://dealpulseksa.com/test-offer"

cur.execute("SELECT click_count, clicked_at, status FROM broadcast_recipients WHERE id=%s", (test_rid,))
row = cur.fetchone()
print(f"بعد click: click_count={row[0]}, clicked_at={row[1]}, status={row[2]}")
assert row[0] == 1
assert row[1] is not None
assert row[2] == "clicked"
print("✅ click سجّل + redirect صحيح + status=clicked")

# ─────────────────────────────────────────────────────────────────────────
# 5. اختبار rewrite_body
# ─────────────────────────────────────────────────────────────────────────
header("5. rewrite_body_for_recipient")
url_map = {"https://example.com/offer1": test_lid,
           "https://example.com/offer2": test_lid}
rewritten = bt.rewrite_body_for_recipient(
    test_body, tracking_token="ABC123",
    url_to_id=url_map, is_html=True)
print("الأصل:    ", test_body)
print("بعد إعادة:", rewritten)
assert "/bt/c/ABC123/" in rewritten
print("✅ إعادة الكتابة تعمل")

# ─────────────────────────────────────────────────────────────────────────
# 6. inject_open_pixel
# ─────────────────────────────────────────────────────────────────────────
header("6. inject_open_pixel")
html = "<html><body><h1>Hi</h1></body></html>"
injected = bt.inject_open_pixel(html, "XYZ789")
print("بعد الحقن:", injected)
assert 'src="http://test.example/api/bt/o/XYZ789.gif"' in injected
assert injected.index('img') < injected.index('</body>')
print("✅ pixel مُحقَن قبل </body>")

# ─────────────────────────────────────────────────────────────────────────
# 7. broadcast_report يحسب open/click rate
# ─────────────────────────────────────────────────────────────────────────
header("7. broadcast_report بعد فتح/نقر")
# نُنشئ email_log اختباري عشان يكون عنده report
cur.execute("""
    INSERT INTO email_logs (subject, body_html, target_audience,
                            delivery_count, sent_count, failed_count, status)
    VALUES ('TEST', '<p>x</p>', 'test', 1, 1, 0, 'completed')
    RETURNING id
""")
test_eid = cur.fetchone()[0]
# ربط الـrecipient الاختباري بهذي الحملة
cur.execute("UPDATE broadcast_recipients SET broadcast_id=%s WHERE id=%s",
            (test_eid, test_rid))
# ربط link_target بنفس الحملة
cur.execute("UPDATE broadcast_link_targets SET broadcast_id=%s WHERE id=%s",
            (test_eid, test_lid))
rep = broadcast_report(c, test_eid, "email")
print("التقرير:")
import json as _j
print(_j.dumps({k:v for k,v in rep.items() if k != "by_status"},
              ensure_ascii=False, indent=2, default=str))
print("by_status:", rep.get("by_status"))
print("engagement:", rep.get("engagement"))
assert rep["engagement"]["unique_opens"] >= 1
assert rep["engagement"]["unique_clicks"] >= 1
print("✅ التقرير يعكس الفتح والنقر")

# ─────────────────────────────────────────────────────────────────────────
# تنظيف
# ─────────────────────────────────────────────────────────────────────────
header("تنظيف بيانات الاختبار")
cur.execute("DELETE FROM broadcast_recipients WHERE id=%s", (test_rid,))
cur.execute("DELETE FROM broadcast_link_targets WHERE id=%s", (test_lid,))
cur.execute("DELETE FROM email_logs WHERE id=%s", (test_eid,))
print(f"✅ نُظّفت بيانات الاختبار (recipient #{test_rid}, "
      f"link #{test_lid}, email_log #{test_eid})")

c.close()
print("\n" + "═"*70)
print("✅ كل اختبارات tracking نجحت")
print("═"*70)
