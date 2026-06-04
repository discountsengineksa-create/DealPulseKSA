"""
Platform Health Report — لقطة صحّة المنصة تُلحَق بكل إيميل توجيهات.

تُحسب كلها من بيانات حقيقية في قاعدة البيانات (لا تخمين، لا LLM):
  • إجمالي المستخدمين (بوت + ميني-ويب + موقع)
  • أعلى 3 متاجر نسخاً وأعلى 3 نقراً (كل القنوات مجمّعة)
  • مؤشّر أداء/توقّف الموقع (heuristic: غياب حركة مفاجئ)
  • تهديدات/بوتات/حركة مشبوهة (security_threats + quality_score منخفض)
  • قفزة زيارات حقيقية (مستخدمون فعليون فوق المعدّل) + عددهم
  • المتاجر البرتقالية (تنتهي خلال 1-3 أيام)
  • فجوات البحث (كلمات بُحث عنها بلا نتيجة) — فرص إضافة متاجر

كل قسم معزول بـ try/except: لو جدول/عمود مفقود، يرجع فارغاً بدل ما يكسر الإيميل.
"""
from __future__ import annotations

import logging
from typing import Any

from api.db import get_db_context

_log = logging.getLogger("dp.health")

# عتبات قابلة للضبط
SUSPICIOUS_QUALITY = 50      # أقل من هذا = حركة مشبوهة/بوت محتمل
SPIKE_MULTIPLIER = 2.0       # ضعف المعدّل = قفزة
SPIKE_MIN_EVENTS = 10        # أقل عدد أحداث في الساعة لاعتبارها قفزة معتدّاً بها
OUTAGE_MIN_BASELINE = 5      # لو معدّل الموقع/ساعة ≥ هذا والساعة الأخيرة = 0 → احتمال توقّف


def _scalar(cur, sql: str, params: tuple = ()) -> Any:
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else 0


def build_health_report(window_days: int = 7) -> dict[str, Any]:
    """يبني تقرير الصحّة. كل قسم best-effort؛ الأخطاء تُسجَّل ولا تُرفع."""
    rep: dict[str, Any] = {"window_days": window_days}

    with get_db_context() as conn:
        # ── 1) إجمالي المستخدمين لكل قناة ──
        try:
            with conn.cursor() as cur:
                bot = _scalar(cur, "SELECT COUNT(DISTINCT user_id) FROM action_logs "
                                   "WHERE source='bot' AND user_id IS NOT NULL")
                mini = _scalar(cur, "SELECT COUNT(DISTINCT COALESCE(user_id::text, encode(ip_hash,'hex'))) "
                                    "FROM action_logs WHERE source IN ('telegram_miniapp','miniapp')")
                web = _scalar(cur,
                    "SELECT (SELECT COUNT(DISTINCT user_id) FROM action_logs "
                    "          WHERE source='web' AND user_id IS NOT NULL) "
                    "     + (SELECT COUNT(DISTINCT encode(ip_hash,'hex')) FROM action_logs "
                    "          WHERE source='web' AND user_id IS NULL AND ip_hash IS NOT NULL)")
                rep["users"] = {"bot": int(bot), "mini": int(mini), "web": int(web),
                                "total": int(bot) + int(mini) + int(web)}
        except Exception as exc:
            _log.warning("users section failed: %s", exc)
            conn.rollback()

        # ── 2) أعلى 3 متاجر نسخاً / 3) نقراً (كل القنوات، آخر window_days) ──
        for key, atype in (("top_copies", "copy_coupon"), ("top_clicks", "click_link")):
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT t.store_id, t.n, m.name_en
                        FROM (
                            SELECT store_id, COUNT(*) AS n
                            FROM action_logs
                            WHERE action_type = %s
                              AND store_id IS NOT NULL AND store_id <> ''
                              AND action_time > NOW() - make_interval(days => %s)
                            GROUP BY store_id ORDER BY n DESC LIMIT 3
                        ) t
                        LEFT JOIN LATERAL (
                            SELECT name_en FROM master WHERE store_id = t.store_id LIMIT 1
                        ) m ON TRUE
                        ORDER BY t.n DESC
                        """,
                        (atype, window_days),
                    )
                    rep[key] = [{"store_id": r[0], "count": int(r[1]), "name_en": r[2]}
                                for r in cur.fetchall()]
            except Exception as exc:
                _log.warning("%s section failed: %s", key, exc)
                conn.rollback()

        # ── 4) أداء/توقّف الموقع (heuristic) ──
        try:
            with conn.cursor() as cur:
                web_24h = _scalar(cur, "SELECT COUNT(*) FROM action_logs "
                                       "WHERE source='web' AND action_time > NOW() - INTERVAL '24 hours'")
                web_1h = _scalar(cur, "SELECT COUNT(*) FROM action_logs "
                                      "WHERE source='web' AND action_time > NOW() - INTERVAL '1 hour'")
                # المعدّل/ساعة عبر آخر 7 أيام
                web_7d = _scalar(cur, "SELECT COUNT(*) FROM action_logs "
                                      "WHERE source='web' AND action_time > NOW() - INTERVAL '7 days'")
                baseline_hr = float(web_7d) / (7 * 24)
                possible_outage = baseline_hr >= OUTAGE_MIN_BASELINE and int(web_1h) == 0
                rep["site"] = {
                    "web_24h": int(web_24h), "web_1h": int(web_1h),
                    "baseline_hr": round(baseline_hr, 1),
                    "possible_outage": possible_outage,
                }
        except Exception as exc:
            _log.warning("site section failed: %s", exc)
            conn.rollback()

        # ── 5) تهديدات / بوتات / حركة مشبوهة ──
        try:
            with conn.cursor() as cur:
                threats_24h = _scalar(cur, "SELECT COUNT(*) FROM security_threats "
                                           "WHERE detection_time > NOW() - INTERVAL '24 hours'")
                cur.execute(
                    "SELECT threat_type, COUNT(*) FROM security_threats "
                    "WHERE detection_time > NOW() - INTERVAL '24 hours' "
                    "GROUP BY threat_type ORDER BY COUNT(*) DESC LIMIT 5"
                )
                by_type = [{"type": r[0] or "غير محدّد", "n": int(r[1])} for r in cur.fetchall()]
                blacklist_24h = _scalar(cur, "SELECT COUNT(*) FROM security_blacklist "
                                             "WHERE block_date > NOW() - INTERVAL '24 hours'")
                rep["security"] = {"threats_24h": int(threats_24h),
                                   "by_type": by_type,
                                   "blacklist_24h": int(blacklist_24h)}
        except Exception as exc:
            _log.warning("security(threats) section failed: %s", exc)
            conn.rollback()
        try:
            with conn.cursor() as cur:
                suspicious_24h = _scalar(cur,
                    "SELECT COUNT(*) FROM action_logs "
                    "WHERE action_time > NOW() - INTERVAL '24 hours' "
                    "  AND quality_score IS NOT NULL AND quality_score < %s",
                    (SUSPICIOUS_QUALITY,))
                rep.setdefault("security", {})["suspicious_events_24h"] = int(suspicious_24h)
        except Exception as exc:
            _log.warning("security(quality) section failed: %s", exc)
            conn.rollback()

        # ── 6) قفزة زيارات حقيقية (مستخدمون فعليون فوق المعدّل) ──
        try:
            with conn.cursor() as cur:
                real_1h = _scalar(cur,
                    "SELECT COUNT(*) FROM action_logs "
                    "WHERE action_time > NOW() - INTERVAL '1 hour' "
                    "  AND COALESCE(quality_score, 100) >= %s", (SUSPICIOUS_QUALITY,))
                real_7d = _scalar(cur,
                    "SELECT COUNT(*) FROM action_logs "
                    "WHERE action_time > NOW() - INTERVAL '7 days' "
                    "  AND COALESCE(quality_score, 100) >= %s", (SUSPICIOUS_QUALITY,))
                baseline_hr = float(real_7d) / (7 * 24)
                is_spike = (int(real_1h) >= SPIKE_MIN_EVENTS
                            and baseline_hr > 0
                            and int(real_1h) >= baseline_hr * SPIKE_MULTIPLIER)
                spike_users = 0
                if is_spike:
                    spike_users = _scalar(cur,
                        "SELECT COUNT(DISTINCT COALESCE(user_id::text, encode(ip_hash,'hex'))) "
                        "FROM action_logs WHERE action_time > NOW() - INTERVAL '1 hour' "
                        "  AND COALESCE(quality_score, 100) >= %s", (SUSPICIOUS_QUALITY,))
                rep["spike"] = {"is_spike": is_spike, "real_1h": int(real_1h),
                                "baseline_hr": round(baseline_hr, 1),
                                "real_users": int(spike_users)}
        except Exception as exc:
            _log.warning("spike section failed: %s", exc)
            conn.rollback()

        # ── 7) المتاجر البرتقالية (تنتهي خلال 1-3 أيام) ──
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT store_id, name_en, (last_time::date - CURRENT_DATE) AS days_left
                    FROM master
                    WHERE last_time IS NOT NULL
                      AND (last_time::date - CURRENT_DATE) BETWEEN 1 AND 3
                    ORDER BY last_time ASC LIMIT 15
                    """
                )
                rep["expiring_orange"] = [
                    {"store_id": r[0], "name_en": r[1], "days_left": int(r[2])}
                    for r in cur.fetchall()
                ]
        except Exception as exc:
            _log.warning("expiring section failed: %s", exc)
            conn.rollback()

        # ── 8) فجوات البحث (كلمات بلا نتيجة) — فرص إضافة متاجر ──
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT search_keyword, COUNT(*) AS n
                    FROM direct_search
                    WHERE user_found = FALSE
                      AND search_keyword IS NOT NULL AND trim(search_keyword) <> ''
                      AND search_date > NOW() - make_interval(days => %s)
                    GROUP BY search_keyword ORDER BY n DESC LIMIT 5
                    """,
                    (window_days,),
                )
                rep["search_gaps"] = [{"kw": r[0], "n": int(r[1])} for r in cur.fetchall()]
        except Exception as exc:
            _log.warning("search_gaps section failed: %s", exc)
            conn.rollback()

    return rep


# ─────────────────────────────────────────────────────────────────────────────
# HTML rendering — يطابق ستايل الإيميل (RTL، بطاقات ملوّنة)
# ─────────────────────────────────────────────────────────────────────────────

def _store_label(item: dict) -> str:
    name = (item.get("name_en") or "").strip()
    sid = item.get("store_id") or ""
    return f"{name} ({sid})" if name and name != sid else (name or sid)


def render_health_html(rep: dict[str, Any]) -> str:
    wd = rep.get("window_days", 7)
    parts: list[str] = [
        "<hr style='border:none;border-top:2px solid #E5E7EB;margin:22px 0 14px;'>",
        "<h3 style='color:#111827;margin:0 0 12px;'>🩺 لقطة صحّة المنصة</h3>",
    ]

    # 1) المستخدمون
    u = rep.get("users")
    if u:
        parts.append(
            f"<div style='background:#F0FDF4;border-radius:8px;padding:12px 14px;margin:8px 0;'>"
            f"<b>👥 إجمالي المستخدمين: {u['total']:,}</b>"
            f"<div style='color:#6B7280;font-size:13px;margin-top:4px;'>"
            f"بوت {u['bot']:,} · ميني-ويب {u['mini']:,} · موقع {u['web']:,}</div></div>"
        )

    # 2+3) أعلى المتاجر
    def _top_block(title: str, rows: list, color: str) -> str:
        if not rows:
            return ""
        lis = "".join(
            f"<li style='margin:3px 0;'>{i}. <b>{_store_label(r)}</b> — "
            f"<span style='color:{color};'>{r['count']:,}</span></li>"
            for i, r in enumerate(rows, 1)
        )
        return (f"<div style='margin:8px 0;'><div style='font-weight:700;'>{title}</div>"
                f"<ol style='margin:6px 0;padding-inline-start:22px;'>{lis}</ol></div>")

    parts.append(_top_block(f"📋 أعلى 3 متاجر نسخاً (كل القنوات · آخر {wd} يوم)",
                            rep.get("top_copies", []), "#059669"))
    parts.append(_top_block(f"🖱️ أعلى 3 متاجر نقراً (كل القنوات · آخر {wd} يوم)",
                            rep.get("top_clicks", []), "#2563EB"))

    # 4) أداء الموقع
    s = rep.get("site")
    if s:
        if s.get("possible_outage"):
            parts.append(
                f"<div style='background:#FEF2F2;border-right:4px solid #DC2626;border-radius:8px;"
                f"padding:10px 14px;margin:8px 0;'><b style='color:#DC2626;'>🔴 احتمال توقّف الموقع</b>"
                f"<div style='color:#6B7280;font-size:13px;'>صفر زيارات في آخر ساعة بينما المعدّل "
                f"~{s['baseline_hr']}/ساعة. راجع توفّر الموقع فوراً.</div></div>"
            )
        else:
            parts.append(
                f"<div style='color:#6B7280;font-size:13px;margin:8px 0;'>"
                f"🌐 أداء الموقع: {s['web_24h']:,} زيارة/24س · {s['web_1h']:,} في آخر ساعة "
                f"(المعدّل ~{s['baseline_hr']}/ساعة) — طبيعي.</div>"
            )

    # 5) الأمان
    sec = rep.get("security")
    if sec:
        threats = sec.get("threats_24h", 0)
        suspicious = sec.get("suspicious_events_24h", 0)
        blk = sec.get("blacklist_24h", 0)
        danger = threats > 0 or blk > 0 or suspicious > 50
        bg, bc = ("#FEF2F2", "#DC2626") if danger else ("#F9FAFB", "#6B7280")
        types = " · ".join(f"{t['type']}: {t['n']}" for t in sec.get("by_type", [])) or "—"
        parts.append(
            f"<div style='background:{bg};border-right:4px solid {bc};border-radius:8px;"
            f"padding:10px 14px;margin:8px 0;'>"
            f"<b style='color:{bc};'>🛡️ الأمان (آخر 24س)</b>"
            f"<div style='color:#374151;font-size:13px;margin-top:4px;'>"
            f"تهديدات: <b>{threats}</b> ({types}) · "
            f"حظر جديد: <b>{blk}</b> · "
            f"أحداث مشبوهة (جودة منخفضة): <b>{suspicious:,}</b></div></div>"
        )

    # 6) قفزة حقيقية
    sp = rep.get("spike")
    if sp and sp.get("is_spike"):
        parts.append(
            f"<div style='background:#EFF6FF;border-right:4px solid #2563EB;border-radius:8px;"
            f"padding:10px 14px;margin:8px 0;'><b style='color:#2563EB;'>📈 قفزة زيارات حقيقية</b>"
            f"<div style='color:#374151;font-size:13px;margin-top:4px;'>"
            f"{sp['real_1h']:,} حدث في آخر ساعة (المعدّل ~{sp['baseline_hr']}/ساعة) "
            f"من <b>{sp['real_users']:,} مستخدم حقيقي</b>. اغتنم الزخم.</div></div>"
        )

    # 7) المتاجر البرتقالية
    exp = rep.get("expiring_orange") or []
    if exp:
        lis = "".join(
            f"<li style='margin:3px 0;'>🟠 <b>{_store_label(e)}</b> — "
            f"يتبقّى {e['days_left']} يوم</li>" for e in exp
        )
        parts.append(
            f"<div style='margin:8px 0;'><div style='font-weight:700;color:#F59E0B;'>"
            f"⏳ متاجر تنتهي خلال 1-3 أيام ({len(exp)})</div>"
            f"<ul style='margin:6px 0;padding-inline-start:22px;'>{lis}</ul></div>"
        )

    # 8) فجوات البحث
    gaps = rep.get("search_gaps") or []
    if gaps:
        lis = "".join(f"<li style='margin:3px 0;'>🔍 «{g['kw']}» — {g['n']} بحثة بلا نتيجة</li>"
                      for g in gaps)
        parts.append(
            f"<div style='margin:8px 0;'><div style='font-weight:700;'>"
            f"💡 فرص (كلمات مبحوثة بلا نتيجة · آخر {wd} يوم)</div>"
            f"<ul style='margin:6px 0;padding-inline-start:22px;'>{lis}</ul></div>"
        )

    return "".join(p for p in parts if p)
