"""
SEO copy generator — يعالج seo_generation_jobs عبر الـ LLM.

يعيد استخدام طبقة call_llm (Gemini → OpenRouter failover + الحارس المالي
+ تسجيل llm_call_log) بالغرض purpose='seo_copy' المحجوز منذ الأسبوع الثالث.

لكل وظيفة:
  queued → running → (completed | failed)
الناتج صفحة في seo_landing_pages بحالة 'draft' (تُنشر يدوياً بعد المراجعة).

كل وظيفة في معاملة مستقلة — فشل واحدة لا يُسقط الباقي.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from api.db import get_db_context

_log = logging.getLogger("dp.seo.generator")

DEFAULT_BATCH = 3

SYSTEM_PROMPT_AR = """أنت كاتب محتوى SEO محترف لمنصة DealPulse KSA — كوبونات وخصومات
في السعودية. مهمّتك كتابة صفحة هبوط عربية مُحسّنة لمحركات البحث حول متجر/كلمة
بحث محددة.

قواعد:
1. اكتب عربية فصيحة سهلة، موجّهة لمتسوّق سعودي يبحث عن كوبون خصم.
2. اللغة طبيعية — لا حشو كلمات مفتاحية. اذكر الكلمة المستهدفة بشكل طبيعي.
3. body_markdown: 250–450 كلمة، يبدأ بفقرة مقدّمة، ثم 2–3 عناوين فرعية (##)،
   ثم جملة دعوة لاستخدام الكوب��ن. لا تضع روابط (الواجهة تضيف زر الكوبون).
4. title_meta: ≤ 60 محرفاً، جذّاب ويحوي الكلمة المستهدفة + اسم المتجر.
5. description_meta: ≤ 155 محرفاً، يلخّص العرض ويحثّ على النقر.
6. لا تخترع نِسَب خصم غير معطاة؛ استخدم المعطيات فقط.

أعد ردك كـ JSON صالح فقط بهذا الشكل بالضبط:
{
  "title_meta": "...",
  "description_meta": "...",
  "body_markdown": "## ...\\n..."
}"""


def _make_slug(keyword: str, master_id: int) -> str:
    s = (keyword or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^\w؀-ۿ\-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        s = f"page-{master_id}"
    return s[:180]


def _parse_json(text: str) -> Optional[dict]:
    """يستخرج JSON من رد الـ LLM (يزيل code fences إن وُجدت)."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # محاولة أخيرة: أول { حتى آخر }
        i, j = t.find("{"), t.rfind("}")
        if 0 <= i < j:
            try:
                return json.loads(t[i:j + 1])
            except json.JSONDecodeError:
                return None
    return None


def _mark_failed(job_id: int, error: str) -> None:
    try:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE seo_generation_jobs SET state='failed', error_message=%s, completed_at=NOW() WHERE id=%s",
                    ((error or "")[:1000], job_id),
                )
    except Exception as exc:
        _log.warning("could not mark job %s failed: %s", job_id, exc)


def _build_user_prompt(job: dict[str, Any]) -> str:
    ctx = {
        "target_keyword": job["target_keyword"],
        "store": job.get("store_id"),
        "store_name_en": job.get("name_en"),
        "store_bio": job.get("store_bio"),
        "discount_value": job.get("discount_value"),
        "public_coupon": job.get("public_coupon"),
        "extra_offer": job.get("extra_offer"),
        "tags": job.get("store_tags"),
    }
    canonical = json.dumps(ctx, ensure_ascii=False, indent=2)
    return (
        "اكتب صفحة هبوط SEO عربية للكلمة المستهدفة والمتجر التاليين:\n"
        f"```json\n{canonical}\n```\n"
        "التزم بقواعد الـ system prompt. ردك JSON صالح فقط."
    )


def _generate_one(job_id: int) -> bool:
    from api.utils.llm_client import call_llm  # lazy — يتجنّب تحميل SDK عند الاستيراد

    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT j.id, j.target_keyword, j.matched_master_id,
                       m.store_id, m.name_en, m.store_bio, m.discount_value,
                       m.public_coupon, m.extra_offer, m.store_tags
                FROM seo_generation_jobs j
                JOIN master m ON m.id = j.matched_master_id
                WHERE j.id = %s
                """,
                (job_id,),
            )
            job = cur.fetchone()

    if not job:
        _mark_failed(job_id, "job or matched store not found")
        return False

    user_prompt = _build_user_prompt(job)
    prompt_hash = hashlib.sha256((SYSTEM_PROMPT_AR + user_prompt).encode("utf-8")).digest()

    res = call_llm(
        purpose="seo_copy",
        system=SYSTEM_PROMPT_AR,
        user=user_prompt,
        max_tokens=1600,
        temperature=0.6,
    )
    if not res.text:
        _mark_failed(job_id, res.error or res.__dict__.get("refused_reason") or "empty_llm_response")
        return False

    data = _parse_json(res.text)
    if not data or not data.get("body_markdown"):
        _mark_failed(job_id, "unparseable_llm_json")
        return False

    title = (data.get("title_meta") or "")[:180]
    desc = (data.get("description_meta") or "")[:280]
    body = data["body_markdown"]
    body_hash = hashlib.sha256(body.encode("utf-8")).digest()

    import psycopg2
    with get_db_context() as conn:
        with conn.cursor() as cur:
            # slug فريد — لو تصادم نُلحق -{job_id}
            base = _make_slug(job["target_keyword"], job["matched_master_id"])
            cur.execute("SELECT 1 FROM seo_landing_pages WHERE slug=%s", (base,))
            slug = base if cur.fetchone() is None else f"{base}-{job_id}"[:200]

            cur.execute(
                """
                INSERT INTO seo_landing_pages
                    (slug, target_keyword, master_id, lang, title_meta,
                     description_meta, body_markdown, body_html_hash,
                     generated_by_job_id, status)
                VALUES (%s, %s, %s, 'ar', %s, %s, %s, %s, %s, 'draft')
                RETURNING id
                """,
                (slug, job["target_keyword"], job["matched_master_id"],
                 title, desc, body, psycopg2.Binary(body_hash), job_id),
            )
            page_id = cur.fetchone()[0]

            cur.execute(
                """
                UPDATE seo_generation_jobs
                SET state='completed', completed_at=NOW(),
                    llm_model=%s, cost_usd=%s, prompt_hash=%s
                WHERE id=%s
                """,
                (res.model, res.cost_usd, psycopg2.Binary(prompt_hash), job_id),
            )

    _log.info("✅ SEO page generated: job=%s page=%s slug=%s provider=%s $%.5f",
              job_id, page_id, slug, res.provider, res.cost_usd)
    return True


def process_pending_jobs(*, batch: int = DEFAULT_BATCH) -> dict[str, int]:
    """يعالج حتى batch وظيفة queued. يرجّع {processed, generated, failed}."""
    # 1) احجز الوظائف وعلّمها running في معاملة واحدة
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM seo_generation_jobs WHERE state='queued' "
                "ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED",
                (batch,),
            )
            job_ids = [r[0] for r in cur.fetchall()]
            if job_ids:
                cur.execute(
                    "UPDATE seo_generation_jobs SET state='running', started_at=NOW() WHERE id = ANY(%s)",
                    (job_ids,),
                )

    processed = generated = failed = 0
    for jid in job_ids:
        processed += 1
        try:
            ok = _generate_one(jid)
        except Exception as exc:
            _log.error("job %s crashed: %s", jid, exc)
            _mark_failed(jid, str(exc))
            ok = False
        generated += int(ok)
        failed += int(not ok)

    _log.info("SEO generation cycle: processed=%d generated=%d failed=%d",
              processed, generated, failed)
    return {"processed": processed, "generated": generated, "failed": failed}
