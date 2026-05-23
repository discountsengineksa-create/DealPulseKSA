"""
3 اختبارات /go/{slug} — affiliate cloaking redirect.
"""
from __future__ import annotations


def test_go_unknown_slug_returns_404(client):
    """slug غير موجود يرجع صفحة HTML 404."""
    resp = client.get("/go/doesnotexist-pytest", follow_redirects=False)
    assert resp.status_code == 404
    # نتوقع HTML عربي (صفحة الـ not_found)
    assert "غير متوفر" in resp.text


def test_go_valid_slug_high_quality_redirects(client, sample_store):
    """slug صحيح + جودة عالية (بدون CF headers → quality افتراضي عالٍ) → 302."""
    resp = client.get(
        f"/go/{sample_store['slug']}",
        follow_redirects=False,
        # نمرّر h=1 لتجاوز الـ JS challenge مباشرة لو ظهر
        params={"h": "1"},
    )
    assert resp.status_code == 302, f"توقعنا 302، حصلنا على {resp.status_code}"
    # الـ Location يجب أن يكون رابط الأفلييت
    location = resp.headers.get("location", "")
    assert "example.com" in location
    # Headers أمنية
    assert resp.headers.get("cache-control") == "no-store"
    assert resp.headers.get("referrer-policy") == "no-referrer"


def test_go_valid_slug_logs_click(client, sample_store, db_conn):
    """نقرة عبر /go تنشئ صف في action_logs."""
    # ننظّف أي logs سابقة لهذا المتجر
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM action_logs WHERE store_id = %s", (sample_store["store_id"],))
    db_conn.commit()

    resp = client.get(f"/go/{sample_store['slug']}", follow_redirects=False, params={"h": "1"})
    assert resp.status_code == 302

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT action_type, details FROM action_logs WHERE store_id = %s",
            (sample_store["store_id"],),
        )
        rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "click_link"
    assert "via_cloak" in rows[0][1]
