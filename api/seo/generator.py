"""
SEO copy generator — يعالج seo_generation_jobs عبر الـ LLM.

يعيد استخدام طبقة call_llm (Gemini → OpenRouter failover + الحارس المالي
+ تسجيل llm_call_log) بالغرض purpose='seo_copy' المحجوز منذ الأسبوع الثالث.

لكل وظيفة:
  queued → running → (completed | failed)
الناتج صفحة (أو صفحتين عربية+إنجليزية لو bilingual مفعّل) في
seo_landing_pages بحالة 'draft' (تُنشر يدوياً بعد المراجعة).

كل وظيفة في معاملة مستقلة — فشل واحدة لا يُسقط الباقي.

ثنائية اللغة (SEO_BILINGUAL):
  - افتراضياً مفعّلة: كل job يُنشئ سطرين (lang='ar' و lang='en')
  - إن أردت إيقافها (للتطوير/توفير التكلفة): SEO_BILINGUAL=0
  - فشل النسخة الإنجليزية لا يُفشل الـ job — العربية أساسية، الإنجليزية إضافة
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from api.db import get_db_context

_log = logging.getLogger("dp.seo.generator")

DEFAULT_BATCH = 3
BILINGUAL_ENABLED = os.getenv("SEO_BILINGUAL", "1") == "1"
# طول مرتفع — Google يفضّل صفحات 600-1200 كلمة للـ landing pages.
# ملاحظة حرجة: العربية في JSON تستهلك 3-4 tokens لكل كلمة (Unicode + escape).
# 1000 كلمة عربية في JSON ≈ 3500-4000 token output. السقف الأصلي 2400 كان
# يقطع النص في المنتصف ويكسر JSON → كل الـ jobs تفشل. 5000 يعطي هامش أمان.
MAX_TOKENS = int(os.getenv("SEO_MAX_TOKENS", "5000"))


# ─── System prompts ─────────────────────────────────────────────────────────
SYSTEM_PROMPT_AR = """أنت كاتب محتوى SEO محترف لمنصة DealPulse KSA (نبض الصفقات) — منصة
كوبونات وخصومات في المملكة العربية السعودية. مهمّتك كتابة صفحة هبوط عربية
مُحسّنة لمحركات البحث Google حول متجر/كلمة بحث محددة.

قواعد الكتابة:
1. عربية فصيحة سهلة، موجّهة لمتسوّق سعودي يبحث عن كوبون خصم.
2. لغة طبيعية — لا حشو كلمات مفتاحية. اذكر الكلمة المستهدفة 3-5 مرات بشكل
   طبيعي، ضمنها مرة في أول 100 كلمة ومرة في عنوان فرعي.
3. body_markdown: **600-1000 كلمة** — صفحة هبوط حقيقية لا مجرد فقرة:
   - فقرة افتتاحية قوية (مقدّمة + قيمة العرض)
   - 3-5 عناوين فرعية (## H2) تغطّي: نظرة عامة على المتجر، فئات المنتجات،
     طريقة استخدام الكوبون، نصائح للتسوّق المُوفّر، الأسئلة الشائعة
   - استخدم قوائم نقطية (- ) عند الحاجة
   - جملة دعوة للنسخ في النهاية
   - لا تضع روابط HTML (الواجهة تُضيف زر الكوبون تلقائياً)
4. title_meta: ≤ 60 محرفاً، جذّاب، يحوي الكلمة المستهدفة + اسم المتجر
   + كلمة جذب (أحدث/حصري/2026/خصم).
5. description_meta: 140-155 محرفاً، يلخّص العرض ويحثّ على النقر بـ CTA واضح.
6. لا تخترع نِسَب خصم غير معطاة؛ استخدم المعطيات فقط.
7. لا تذكر منافسين أو منصّات أخرى.

أعد ردك كـ JSON صالح فقط بهذا الشكل بالضبط:
{
  "title_meta": "...",
  "description_meta": "...",
  "body_markdown": "## ...\\n..."
}"""


SYSTEM_PROMPT_EN = """You are a professional SEO content writer for DealPulse KSA — a Saudi
Arabia coupons and discounts platform. Your task: write a Google-optimized
English landing page about a specific store / search keyword for Saudi/Gulf
shoppers (including expats and tourists).

Writing rules:
1. Clear, professional English aimed at Saudi-resident shoppers (including
   expatriates) looking for verified discount codes.
2. Natural language — no keyword stuffing. Use the target keyword 3-5 times
   naturally, including once in the first 100 words and once in an H2.
3. body_markdown: **600-1000 words** — a real landing page, not a paragraph:
   - Strong opening paragraph (intro + offer value)
   - 3-5 subheadings (## H2) covering: store overview, product categories,
     how to use the coupon, money-saving tips, FAQ
   - Use bullet lists (- ) where helpful
   - End with a clear call-to-copy
   - No HTML links (the UI adds the coupon button automatically)
4. title_meta: ≤ 60 chars, catchy, includes target keyword + store name
   + a hook word (latest / exclusive / 2026 / discount).
5. description_meta: 140-155 chars, summarizes the offer with clear CTA.
6. Do not invent discount percentages not provided; use only the given data.
7. Do not name competitors or other platforms.

Return your response as valid JSON only, exactly in this shape:
{
  "title_meta": "...",
  "description_meta": "...",
  "body_markdown": "## ...\\n..."
}"""


# ─── Helpers ────────────────────────────────────────────────────────────────
def _make_slug(keyword: str, master_id: int, lang: str = "ar") -> str:
    """يولّد slug آمناً. للإنجليزي يُسبّقه بـ 'en/' عن طريق suffix."""
    s = (keyword or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^\w؀-ۿ\-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        s = f"page-{master_id}"
    base = s[:170]
    return f"{base}-en" if lang == "en" else base


def _parse_json(text: str) -> Optional[dict]:
    """
    يستخرج JSON من رد الـ LLM بأقصى صلابة ممكنة.

    يتعامل مع:
      • code fences (```json ... ```)
      • نص قبل/بعد الـ JSON
      • newlines حرفية غير مهرّبة داخل القيم النصية (مشكلة شائعة مع Llama)
      • truncation: يحاول إغلاق JSON ناقص
      • Last resort: regex مباشر لاستخراج الحقول الثلاثة المطلوبة

    يرجّع dict فيه على الأقل body_markdown، أو None لو فعلاً مستحيل.
    """
    if not text:
        return None

    t = text.strip()

    # 1) أزِل code fences
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
        t = t.strip()

    # 2) محاولة مباشرة
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # 3) قصّ بين أول '{' وآخر '}'
    i, j = t.find("{"), t.rfind("}")
    candidate = None
    if 0 <= i < j:
        candidate = t[i:j + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 4) إصلاح newlines حرفية داخل القيم النصية (Llama يخرجها بدون escape)
    if candidate:
        # نستبدل \r\n و\n و\r داخل قيمة بـ \\n
        # طريقة آمنة: نُمرّر النص حرفاً حرفاً مع تتبّع الـ string state
        fixed = _escape_unescaped_newlines(candidate)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    # 5) Last resort: regex لاستخراج الحقول مباشرة
    # نقبل الـ job لو حصلنا على body_markdown على الأقل
    extracted: dict[str, Any] = {}
    for field in ("title_meta", "description_meta"):
        m = re.search(
            rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"',
            t, re.DOTALL,
        )
        if m:
            extracted[field] = m.group(1).encode().decode("unicode_escape", errors="ignore")

    # body_markdown قد يحتوي newlines حرفية — نستخرج بطريقة أكثر تساهلاً
    body_match = re.search(
        r'"body_markdown"\s*:\s*"(.*?)"\s*(?:,|\}|$)',
        t, re.DOTALL,
    )
    if body_match:
        body_raw = body_match.group(1)
        # decode escape sequences لو موجودة
        try:
            body_raw = body_raw.encode().decode("unicode_escape", errors="ignore")
        except Exception:
            pass
        extracted["body_markdown"] = body_raw

    return extracted if extracted.get("body_markdown") else None


def _escape_unescaped_newlines(s: str) -> str:
    """
    يستبدل newlines الحرفية داخل قيم JSON النصية بـ \\n.
    يتتبّع state: هل نحن داخل string أم لا.
    """
    out = []
    in_string = False
    escape_next = False
    for ch in s:
        if escape_next:
            out.append(ch)
            escape_next = False
            continue
        if ch == "\\":
            out.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string and ch in ("\n", "\r"):
            out.append("\\n")
            continue
        out.append(ch)
    return "".join(out)


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


def _build_user_prompt(job: dict[str, Any], lang: str) -> str:
    ctx = {
        "target_keyword": job["target_keyword"],
        "store_id":       job.get("store_id"),
        "store_name_en":  job.get("name_en"),
        "store_bio":      job.get("store_bio"),
        "store_bio_en":   job.get("store_bio_en"),
        "discount_value": job.get("discount_value"),
        "public_coupon":  job.get("public_coupon"),
        "extra_offer":    job.get("extra_offer"),
        "extra_offer_en": job.get("extra_offer_en"),
        "tags":           job.get("store_tags"),
        "tags_en":        job.get("store_tags_en"),
    }
    canonical = json.dumps(ctx, ensure_ascii=False, indent=2)
    if lang == "en":
        return (
            "Write an English SEO landing page for the target keyword and store below:\n"
            f"```json\n{canonical}\n```\n"
            "Follow the system prompt rules. Return valid JSON only."
        )
    return (
        "اكتب صفحة هبوط SEO عربية للكلمة المستهدفة والمتجر التاليين:\n"
        f"```json\n{canonical}\n```\n"
        "التزم بقواعد الـ system prompt. ردك JSON صالح فقط."
    )


# ─── Per-language generation ────────────────────────────────────────────────
def _generate_page_for_lang(job: dict, lang: str, job_id: int) -> tuple[bool, Optional[dict]]:
    """
    يولّد صفحة واحدة بلغة محدّدة. يرجّع (نجاح، {model, cost_usd, prompt_hash})
    للتسجيل لاحقاً في الـ job. الإدراج في seo_landing_pages يتم هنا.

    لا يعدّل حالة الـ job — المُتّصل يقرّر إجمالاً.
    """
    from api.utils.llm_client import call_llm  # lazy

    system = SYSTEM_PROMPT_EN if lang == "en" else SYSTEM_PROMPT_AR
    user_prompt = _build_user_prompt(job, lang)
    prompt_hash = hashlib.sha256((system + user_prompt).encode("utf-8")).digest()

    res = call_llm(
        purpose=f"seo_copy_{lang}",
        system=system,
        user=user_prompt,
        max_tokens=MAX_TOKENS,
        temperature=0.6,
    )
    if not res.text:
        _log.warning("LLM empty for job=%s lang=%s: %s", job_id, lang,
                     res.error or "no_text")
        return False, None

    data = _parse_json(res.text)
    if not data or not data.get("body_markdown"):
        _log.warning("Unparseable JSON for job=%s lang=%s", job_id, lang)
        return False, None

    title = (data.get("title_meta") or "")[:180]
    desc = (data.get("description_meta") or "")[:280]
    body = data["body_markdown"]
    body_hash = hashlib.sha256(body.encode("utf-8")).digest()
    word_count = len(re.findall(r"\S+", body))

    import psycopg2
    with get_db_context() as conn:
        with conn.cursor() as cur:
            base = _make_slug(job["target_keyword"], job["matched_master_id"], lang=lang)
            cur.execute("SELECT 1 FROM seo_landing_pages WHERE slug=%s", (base,))
            slug = base if cur.fetchone() is None else f"{base}-{job_id}"[:200]

            cur.execute(
                """
                INSERT INTO seo_landing_pages
                    (slug, target_keyword, master_id, lang, title_meta,
                     description_meta, body_markdown, body_html_hash,
                     generated_by_job_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')
                RETURNING id
                """,
                (slug, job["target_keyword"], job["matched_master_id"], lang,
                 title, desc, body, psycopg2.Binary(body_hash), job_id),
            )
            page_id = cur.fetchone()[0]

    _log.info("  ✅ %s page: id=%s slug=%s words=%d $%.5f",
              lang.upper(), page_id, slug, word_count, res.cost_usd or 0)
    return True, {
        "model":        res.model,
        "cost_usd":     float(res.cost_usd or 0),
        "prompt_hash":  prompt_hash,
        "words":        word_count,
    }


# ─── Per-job orchestration ──────────────────────────────────────────────────
def _generate_one(job_id: int) -> bool:
    """
    ينفّذ job واحداً. يُعتبر ناجحاً إذا نجحت العربية (الأساس). فشل الإنجليزية
    وحدها لا يُسقط الـ job — تبقى الصفحة العربية صالحة للنشر.
    """
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT j.id, j.target_keyword, j.matched_master_id,
                       m.store_id, m.name_en, m.store_bio, m.store_bio_en,
                       m.discount_value, m.public_coupon,
                       m.extra_offer, m.extra_offer_en,
                       m.store_tags, m.store_tags_en
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

    # 1) العربية — الأساس
    ar_ok, ar_meta = _generate_page_for_lang(job, "ar", job_id)
    if not ar_ok:
        _mark_failed(job_id, "arabic_generation_failed")
        return False

    # 2) الإنجليزية — إضافة لو bilingual مفعّل (فشلها لا يكسر العربية)
    total_cost = ar_meta["cost_usd"] if ar_meta else 0.0
    if BILINGUAL_ENABLED:
        en_ok, en_meta = _generate_page_for_lang(job, "en", job_id)
        if en_ok and en_meta:
            total_cost += en_meta["cost_usd"]
        else:
            _log.info("English generation skipped/failed for job=%s (Arabic OK, continuing)", job_id)

    # 3) علّم الـ job مكتمل (بالـ Arabic metadata — صحيحة دائماً)
    import psycopg2
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE seo_generation_jobs
                SET state='completed', completed_at=NOW(),
                    llm_model=%s, cost_usd=%s, prompt_hash=%s
                WHERE id=%s
                """,
                (ar_meta["model"], total_cost,
                 psycopg2.Binary(ar_meta["prompt_hash"]), job_id),
            )

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

    _log.info("SEO generation cycle: processed=%d generated=%d failed=%d bilingual=%s",
              processed, generated, failed, BILINGUAL_ENABLED)
    return {"processed": processed, "generated": generated, "failed": failed}
