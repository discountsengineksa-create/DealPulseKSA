"""
Keyword → Store matcher + job enqueuer.

لكل إشارة ترند ذات قيمة:
  1. نتحقق من seo_keyword_blocklist (لا نولّد محتوى لكلمات محظورة).
  2. نطابق الكلمة بأقرب متجر في master عبر trigram similarity.
  3. لو في تطابق فوق العتبة → نُنشئ seo_generation_jobs(state='queued').

نولّد فقط لكلمات لها متجر مطابق (محتوى مرتبط بعرض حقيقي قابل للربح).
الـ dedup: نتخطّى الكلمة لو عندها وظيفة فعّالة/مكتملة أو صفحة موجودة.
"""
from __future__ import annotations

import logging
import re

from psycopg2.extras import RealDictCursor

from api.db import get_db_context

_log = logging.getLogger("dp.seo.matcher")

DEFAULT_LIMIT = 25
SIM_THRESHOLD = 0.30   # نفس روح بحث الكوبونات (similarity > 0.05) لكن أصرم للجودة


MIN_KEYWORD_LEN = 3


def _normalize_ar(s: str) -> str:
    """توحيد صور الحرف العربي: ة/ه، أإآ/ا، ى/ي، حذف التطويل والتشكيل.
    ضروري هنا لأن «منصه» و«منصة» صورتان لكلمة واحدة، وبدون التوحيد يمرّ أحدهما."""
    s = (s or "").strip().lower()
    s = re.sub(r"[ـً-ْ]", "", s)          # تطويل + تشكيل
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"[أإآ]", "ا", s)
    return re.sub(r"\s+", " ", s).strip()


def _is_name_fragment(keyword: str, store_name: str) -> bool:
    """هل الكلمة **جزء مبتور** من اسم المتجر لا الاسم نفسه؟

    `trend_signals` يلتقط بحث المستخدم **أثناء الكتابة**، فتُسجَّل مقاطع جزئية
    ويصنع المطابق صفحة هبوط لكل واحدة. الأثر الموثّق (٢٠٢٦-٠٨-٠٨): «منصة زد»
    وحدها صارت أربع صفحات منشورة من `منص` و`منصه` و`منصة` و`زد` — تتنافس بينها
    وتتنافس مع صفحة المتجر. ومثلها `تو`←تويو و`وولف`←وولفيكس و`بيد`←بيد إن روم
    و`قطرة عس`←قطرة عسل. الاسم الكامل يمرّ (`ريمان`، `نون`) لأنه ليس مبتوراً.
    """
    k, s = _normalize_ar(keyword), _normalize_ar(store_name)
    if not k or not s:
        return False
    return k != s and k in s


def _load_blocklist(cur) -> list[tuple[str, str]]:
    """يرجّع [(pattern, pattern_type), ...]. pattern_type: exact|substring|regex."""
    cur.execute("SELECT pattern, COALESCE(pattern_type, 'substring') FROM seo_keyword_blocklist")
    return [(p, (t or "substring").lower()) for p, t in cur.fetchall()]


def _is_blocked(keyword: str, blocklist: list[tuple[str, str]]) -> bool:
    kw = keyword.lower().strip()
    for pattern, ptype in blocklist:
        pat = (pattern or "").lower().strip()
        if not pat:
            continue
        if ptype == "exact" and kw == pat:
            return True
        if ptype == "substring" and pat in kw:
            return True
        if ptype == "regex":
            try:
                if re.search(pattern, keyword, re.IGNORECASE):
                    return True
            except re.error:
                continue
    return False


def match_and_enqueue(*, limit: int = DEFAULT_LIMIT, sim_threshold: float = SIM_THRESHOLD) -> int:
    """يطابق أعلى إشارات الترند ويُنشئ وظائف توليد. يرجّع عدد الوظائف المُنشأة."""
    enqueued = 0
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            blocklist = _load_blocklist(cur)

            # أعلى إشارات الترند التي لا تملك بعد وظيفة فعّالة/مكتملة ولا صفحة
            cur.execute(
                """
                SELECT ts.id, ts.query_text, ts.interest_score
                FROM trend_signals ts
                WHERE NOT EXISTS (
                    SELECT 1 FROM seo_generation_jobs j
                    WHERE j.target_keyword = ts.query_text
                      AND j.state IN ('queued', 'running', 'completed')
                )
                AND NOT EXISTS (
                    SELECT 1 FROM seo_landing_pages p
                    WHERE p.target_keyword = ts.query_text
                )
                ORDER BY ts.interest_score DESC NULLS LAST, ts.captured_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            candidates = cur.fetchall()

            for c in candidates:
                kw = (c["query_text"] or "").strip()
                if not kw or _is_blocked(kw, blocklist):
                    continue
                if len(_normalize_ar(kw)) < MIN_KEYWORD_LEN:
                    _log.info("  ⏭️  keyword too short, skipped: %r", kw)
                    continue

                # أقرب متجر بالـ trigram
                cur.execute(
                    """
                    SELECT id, store_id,
                           GREATEST(
                               similarity(lower(store_id),                    lower(%(q)s)),
                               similarity(lower(COALESCE(name_en, '')),       lower(%(q)s)),
                               similarity(lower(COALESCE(store_tags, '')),    lower(%(q)s)),
                               similarity(lower(COALESCE(store_tags_en, '')), lower(%(q)s))
                           ) AS sim
                    FROM master
                    ORDER BY sim DESC
                    LIMIT 1
                    """,
                    {"q": kw},
                )
                m = cur.fetchone()
                if not m or float(m["sim"] or 0) < sim_threshold:
                    continue  # لا متجر مطابق — تخطّى (فجوة محتوى، نتركها)

                # مقطع مبتور من اسم المتجر ⇒ لا صفحة له: صفحة المتجر تغطّيه،
                # وإنشاؤها يوَلّد منافساً داخلياً لا طلباً جديداً.
                if _is_name_fragment(kw, m["store_id"] or ""):
                    _log.info("  ⏭️  fragment of store name, skipped: %r ⊂ %r",
                              kw, m["store_id"])
                    continue

                cur.execute(
                    """
                    INSERT INTO seo_generation_jobs
                        (trend_signal_id, target_keyword, matched_master_id, state)
                    VALUES (%s, %s, %s, 'queued')
                    ON CONFLICT (target_keyword, matched_master_id)
                        WHERE state IN ('queued', 'running')
                        DO NOTHING
                    """,
                    (c["id"], kw, m["id"]),
                )
                if cur.rowcount:
                    enqueued += 1

    _log.info("seo jobs enqueued: %d (from %d candidates)", enqueued, len(candidates))
    return enqueued
