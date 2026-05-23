"""
5 اختبارات /api/v1/track — action insertion, quality scoring, idempotency.
"""
from __future__ import annotations

import uuid


def _make_payload(store_id: str, action: str = "click_link",
                  event_id: str | None = None) -> dict:
    return {
        "store_id": store_id,
        "action": action,
        "details": "pytest",
        "source": "web",
        "user_id": None,
        "event_id": event_id or str(uuid.uuid4()),
    }


def test_track_action_success(client, sample_store):
    """تتبع حركة على متجر صحيح يُسجَّل بنجاح."""
    payload = _make_payload(sample_store["store_id"], "click_link")
    resp = client.post("/api/v1/track", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["store_id"] == sample_store["store_id"]


def test_track_unknown_store_returns_404(client, sample_store):
    """متجر غير موجود → 404."""
    payload = _make_payload("does_not_exist_xyz")
    resp = client.post("/api/v1/track", json=payload)
    assert resp.status_code == 404


def test_track_idempotent_same_event_id(client, sample_store, db_conn):
    """نفس event_id لا يُسجَّل مرتين (ON CONFLICT DO NOTHING)."""
    eid = str(uuid.uuid4())
    payload = _make_payload(sample_store["store_id"], "copy_coupon", event_id=eid)

    # أول إرسال
    r1 = client.post("/api/v1/track", json=payload)
    assert r1.status_code == 201
    # نفس event_id مرة ثانية
    r2 = client.post("/api/v1/track", json=payload)
    assert r2.status_code == 201  # الـ endpoint يرجع 201 على أي حال

    # نتحقق في DB: صف واحد فقط
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM action_logs WHERE event_id = %s::uuid", (eid,))
        count = cur.fetchone()[0]
    assert count == 1, f"event_id تكرّر {count} مرات"


def test_track_high_quality_updates_master_counter(client, sample_store, db_conn):
    """copy_coupon عالي الجودة يرفع master.total_coupon_copies بـ 1."""
    sid = sample_store["store_id"]
    # اقرأ القيمة قبل
    with db_conn.cursor() as cur:
        cur.execute("SELECT COALESCE(total_coupon_copies, 0) FROM master WHERE store_id = %s", (sid,))
        before = cur.fetchone()[0]

    # أرسل event (بدون Cloudflare headers → quality يكون افتراضياً ≥ 50)
    payload = _make_payload(sid, "copy_coupon")
    r = client.post("/api/v1/track", json=payload)
    assert r.status_code == 201

    with db_conn.cursor() as cur:
        cur.execute("SELECT COALESCE(total_coupon_copies, 0) FROM master WHERE store_id = %s", (sid,))
        after = cur.fetchone()[0]
    assert after == before + 1, f"العدّاد لم يرتفع: {before} → {after}"


def test_track_search_endpoint(client, sample_store):
    """/track/search يخزّن كلمة البحث."""
    resp = client.post("/api/v1/track/search", json={
        "keyword": "بايتست-اختبار",
        "store_id": sample_store["store_id"],
        "user_found": True,
        # SearchLogRequest يقبل Literal["Web","Bot","Dashboard"] (capitalized)
        "platform": "Web",
        "name_en": None,
        "user_id": None,
        "user_email": "pytest@example.com",
    })
    assert resp.status_code == 201
    assert resp.json()["keyword"] == "بايتست-اختبار"
