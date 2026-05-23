"""
Intent scoring + store matching for social signals.

score_content: يطابق نص الإشارة بمصطلحات الرصد النشطة ويحسب intent_score (0..1).
find_candidate_master_ids: يكتشف المتاجر المذكورة صراحةً في النص (ILIKE).
"""
from __future__ import annotations

import re
from typing import Any


def detect_lang(text: str) -> str:
    """عربي لو فيه أي حرف عربي، وإلا إنجليزي."""
    return "ar" if re.search(r"[؀-ۿ]", text or "") else "en"


_TERM_COLS = ("id", "term", "term_type", "intent_weight", "associated_master_id")


def _row_to_dict(row, cols: tuple[str, ...]) -> dict[str, Any]:
    """يدعم RealDictRow (dict) والصفوف العادية (tuple) معاً."""
    if isinstance(row, dict):
        return {c: row[c] for c in cols}
    return dict(zip(cols, row))


def load_active_terms(cur) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT id, term, COALESCE(term_type, 'keyword') AS term_type,
               COALESCE(intent_weight, 1.00) AS intent_weight, associated_master_id
        FROM social_listening_terms
        WHERE active = TRUE
        """
    )
    return [_row_to_dict(r, _TERM_COLS) for r in cur.fetchall()]


def _term_matches(content: str, term: str, term_type: str) -> bool:
    c = content.lower()
    t = (term or "").lower().strip()
    if not t:
        return False
    if term_type == "regex":
        try:
            return re.search(term, content, re.IGNORECASE) is not None
        except re.error:
            return False
    # keyword + hashtag: substring match (hashtag يُكتب بدون #)
    return t.lstrip("#") in c


def score_content(content: str, terms: list[dict[str, Any]]) -> tuple[float, int | None, int | None]:
    """
    يرجّع (intent_score, matched_term_id, associated_master_id).
    intent_score = أعلى وزن مطابق + 0.1 لكل مطابقة إضافية (مقصوص عند 1.0).
    """
    matched = [t for t in terms if _term_matches(content, t["term"], t["term_type"])]
    if not matched:
        return 0.0, None, None
    matched.sort(key=lambda t: float(t["intent_weight"]), reverse=True)
    base = float(matched[0]["intent_weight"])
    score = min(1.0, base + 0.10 * (len(matched) - 1))
    return round(score, 2), matched[0]["id"], matched[0]["associated_master_id"]


def find_candidate_master_ids(cur, content: str, *, limit: int = 3) -> list[int]:
    """المتاجر المذكورة صراحةً في النص (اسم المتجر يظهر كـ substring)."""
    cur.execute(
        """
        SELECT id
        FROM master
        WHERE length(store_id) >= 2
          AND (
              %(c)s ILIKE '%%' || store_id || '%%'
              OR (name_en IS NOT NULL AND length(name_en) >= 2
                  AND %(c)s ILIKE '%%' || name_en || '%%')
          )
        ORDER BY COALESCE(total_link_clicks, 0) + COALESCE(total_coupon_copies, 0) DESC
        LIMIT %(lim)s
        """,
        {"c": content, "lim": limit},
    )
    return [(r["id"] if isinstance(r, dict) else r[0]) for r in cur.fetchall()]
