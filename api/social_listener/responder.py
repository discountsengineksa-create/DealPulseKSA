"""
Auto-Responder — يحوّل الإشارات المرصودة إلى ردود جاهزة موجّهة لصفحات الهبوط.

process_new_signals: orchestrator مجدوَل (مجاني — بلا LLM):
  لكل إشارة new/scored → score → match store → build link → render template
  → INSERT social_responses. الردود عالية الثقة تُعتمد تلقائياً لو SOCIAL_AUTO_APPROVE=1.

الرابط يفضّل صفحة هبوط /c/{slug} منشورة للمتجر، ثم /store/{store_id}،
ثم /go/{cloaked_slug} — كلها تصبّ في قمع الأفلييت.
"""
from __future__ import annotations

import logging
import os

from psycopg2.extras import RealDictCursor

from api.db import get_db_context
from api.social_listener import scorer

_log = logging.getLogger("dp.social.responder")

SITE_URL = os.getenv("SITE_URL", "https://dealpulseksa.com").rstrip("/")
AUTO_APPROVE = os.getenv("SOCIAL_AUTO_APPROVE") == "1"
AUTO_APPROVE_MIN_INTENT = float(os.getenv("SOCIAL_AUTO_APPROVE_MIN_INTENT", "0.8"))
RESPOND_MIN_INTENT = float(os.getenv("SOCIAL_RESPOND_MIN_INTENT", "0.5"))
DEFAULT_BATCH = 20


def _build_link(cur, master_id: int | None) -> tuple[str, str | None, str | None, str | None]:
    """يرجّع (link_url, store_name, discount_value, public_coupon)."""
    if not master_id:
        return f"{SITE_URL}/stores", None, None, None

    cur.execute(
        """
        SELECT store_id,
               COALESCE(NULLIF(name_en, ''), store_id) AS store_name,
               discount_value, public_coupon, cloaked_slug
        FROM master WHERE id = %s
        """,
        (master_id,),
    )
    m = cur.fetchone()
    if not m:
        return f"{SITE_URL}/stores", None, None, None

    # 1) صفحة هبوط منشورة لهذا المتجر؟
    cur.execute(
        "SELECT slug FROM seo_landing_pages WHERE master_id = %s AND status='published' "
        "ORDER BY published_at DESC NULLS LAST LIMIT 1",
        (master_id,),
    )
    lp = cur.fetchone()
    if lp:
        link = f"{SITE_URL}/c/{lp['slug']}"
    elif m.get("store_id"):
        link = f"{SITE_URL}/store/{m['store_id']}"
    elif m.get("cloaked_slug"):
        link = f"https://api.dealpulseksa.com/go/{m['cloaked_slug']}"
    else:
        link = f"{SITE_URL}/stores"
    return link, m.get("store_name"), m.get("discount_value"), m.get("public_coupon")


def _pick_template(cur, lang: str) -> tuple[int | None, str, str]:
    cur.execute("SELECT id, template_ar, template_en, COALESCE(a_b_group, 'A') AS arm "
                "FROM social_response_templates WHERE active = TRUE ORDER BY random() LIMIT 1")
    row = cur.fetchone()
    if not row:
        return None, "وفّر أكثر مع كوبونات {store}: {link}", "default"
    tmpl = (row["template_en"] if lang == "en" and row.get("template_en") else row["template_ar"])
    return row["id"], tmpl, row["arm"]


def _render(tmpl: str, *, store: str | None, link: str, discount: str | None, coupon: str | None) -> str:
    return (
        tmpl.replace("{store}", store or "متجرك المفضّل")
            .replace("{link}", link)
            .replace("{discount}", discount or "")
            .replace("{coupon}", coupon or "")
            .strip()
    )


def prepare_response(cur, signal: dict) -> int | None:
    """يبني ردّاً واحداً لإشارة مُسجّلة. يرجّع response_id أو None."""
    master_id = (signal.get("candidate_master_ids") or [None])[0]
    lang = signal.get("lang_detected") or "ar"
    link, store_name, discount, coupon = _build_link(cur, master_id)
    template_id, tmpl, arm = _pick_template(cur, lang)
    text = _render(tmpl, store=store_name, link=link, discount=discount, coupon=coupon)

    intent = float(signal.get("intent_score") or 0)
    review = "auto_approved" if (AUTO_APPROVE and intent >= AUTO_APPROVE_MIN_INTENT) else "pending"

    cur.execute(
        """
        INSERT INTO social_responses
            (signal_id, master_id, template_id, rendered_text, link_url, review_status)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (signal["id"], master_id, template_id, text, link, review),
    )
    response_id = cur.fetchone()["id"]

    # A/B: سجّل ظهور القالب (migration_016) — best-effort
    try:
        from api.utils.ops import log_experiment_event
        log_experiment_event(surface="social_template", arm=arm,
                             event_type="impression", ref_id=response_id)
    except Exception:
        pass
    return response_id


def process_new_signals(*, batch: int = DEFAULT_BATCH) -> dict[str, int]:
    """يعالج الإشارات الجديدة: scoring → matching → توليد الردود."""
    scored = responded = ignored = 0
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            terms = scorer.load_active_terms(cur)
            cur.execute(
                "SELECT id, content, lang_detected FROM social_signals "
                "WHERE status IN ('new', 'scored') ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED",
                (batch,),
            )
            signals = cur.fetchall()

            for s in signals:
                content = s["content"] or ""
                intent, term_id, term_master = scorer.score_content(content, terms)
                lang = s["lang_detected"] or scorer.detect_lang(content)
                candidates = scorer.find_candidate_master_ids(cur, content)
                if term_master and term_master not in candidates:
                    candidates = [term_master] + candidates

                if intent < RESPOND_MIN_INTENT or not candidates:
                    cur.execute(
                        "UPDATE social_signals SET status='ignored', intent_score=%s, "
                        "matched_term_id=%s, lang_detected=%s WHERE id=%s",
                        (intent, term_id, lang, s["id"]),
                    )
                    ignored += 1
                    continue

                cur.execute(
                    "UPDATE social_signals SET status='matched', intent_score=%s, "
                    "matched_term_id=%s, candidate_master_ids=%s, lang_detected=%s WHERE id=%s",
                    (intent, term_id, candidates, lang, s["id"]),
                )
                scored += 1
                sig = {**s, "intent_score": intent, "candidate_master_ids": candidates,
                       "lang_detected": lang}
                rid = prepare_response(cur, sig)
                if rid:
                    cur.execute("UPDATE social_signals SET status='responded' WHERE id=%s", (s["id"],))
                    responded += 1

    _log.info("social signals processed: scored=%d responded=%d ignored=%d",
              scored, responded, ignored)
    return {"scored": scored, "responded": responded, "ignored": ignored}
