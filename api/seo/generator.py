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
MAX_TOKENS = int(os.getenv("SEO_MAX_TOKENS", "8000"))  # مساحة لتفكير 2.5 + عربية ثقيلة بالتوكنز
# هدف طول التوليد — أعلى من بوّابة النشر (MIN_BODY_WORDS=350) بهامش أمان. الموديل
# أحياناً يبخل رغم طلب 600-1000 → نعيد المحاولة ونحتفظ بأطول ناتج نظيف.
MIN_GEN_WORDS = int(os.getenv("SEO_MIN_GEN_WORDS", "450"))


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
6. لا تخترع نِسَب خصم غير معطاة؛ استخدم المعطيات فقط (الكود/العرض/العرض الإضافي).
   وإن كان public_coupon كوداً فعلياً (غير فارغ وغير «.») فاذكره **حرفياً** داخل
   خطوات استخدام الكود (مثل «أدخل الكود ‎CMN10‎»)، ولا تستخدم الكلمة المستهدفة
   نفسها كأنها الكود.
7. لا تذكر منافسين أو منصّات أخرى.
8. **التزم بفئة المتجر الفعلية**: اكتب فقط عن المنتجات/الفئات التي يبيعها المتجر
   فعلاً حسب (store_tags و store_bio) المعطاة. لا تخترع فئات أو منتجات لا يبيعها
   — متجر قهوة لا تكتب عنه عبايات، ومتجر إلكترونيات لا تكتب عنه عطور. إن كانت
   الفئة غير واضحة، اكتب عاماً عن «عروض المتجر وكوبوناته» دون ذكر منتجات محددة.

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
6. Do not invent discount percentages not provided; use only the given data
   (the code / offer / extra offer). If public_coupon is a real code (not empty
   and not "."), cite it verbatim inside the "how to use" steps (e.g., "enter code
   CMN10"); never present the target keyword itself as if it were the code.
7. Do not name competitors or other platforms.
8. **Stay strictly within the store's real category**: write only about products/
   categories the store actually sells per the given store_tags and store_bio.
   Never invent categories/products it doesn't sell — a coffee store must NOT get
   abaya content, an electronics store must NOT get perfume content. If the category
   is unclear, write generically about "the store's offers and coupons" without
   naming specific products.

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
    # نقبل الـ job لو حصلنا على body_markdown على الأقل.
    # ملاحظة: unicode_escape يُفسد الحروف العربية، فنستخدم فكّ هروب يدوي آمن
    # للتسلسلات الشائعة فقط (\n \t \" \\) بدون لمس بايتات UTF-8.
    def _safe_unescape(s: str) -> str:
        return (s.replace('\\r', '').replace('\\n', '\n')
                 .replace('\\t', '\t').replace('\\"', '"')
                 .replace('\\\\', '\\'))

    extracted: dict[str, Any] = {}
    for field in ("title_meta", "description_meta"):
        m = re.search(
            rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"',
            t, re.DOTALL,
        )
        if m:
            extracted[field] = _safe_unescape(m.group(1))

    # body_markdown هو آخر حقل في المخطط → نلتقط بجشع حتى النهاية، فنتحمّل
    # علامات اقتباس " غير مهرّبة داخل النص (السبب الشائع لفشل Gemini) + البتر.
    body_match = re.search(r'"body_markdown"\s*:\s*"(.*)', t, re.DOTALL)
    if body_match:
        body_raw = body_match.group(1).rstrip()
        # أزِل إغلاق JSON النهائي إن وُجد:  "}  أو  "
        body_raw = re.sub(r'"\s*\}?\s*$', '', body_raw)
        extracted["body_markdown"] = _safe_unescape(body_raw)

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


# زوايا محتوى متنوّعة (White-Hat: تمنع تشابه/تكرار الصفحات = scaled content abuse)
_ANGLES_AR = [
    "ركّز على «كيف تستخدم الكود خطوة بخطوة» + نصيحة توفير عملية. عنوان يبدأ بفعل أو سؤال.",
    "ركّز على «أبرز فئات المنتجات والأقسام» في المتجر. عنوان يذكر الفئة + قيمة التوفير.",
    "ركّز على «لماذا تختار هذا المتجر» + ميزته التنافسية وموثوقيته. عنوان يبرز التميّز.",
    "اربط العرض بالموسم/المناسبة بنبرة عاجلة لطيفة. عنوان موسمي محدّد.",
    "أسلوب «أسئلة شائعة» — جاوب على أسئلة المتسوّق الحقيقية حول الكود والشحن والإرجاع.",
]
_ANGLES_EN = [
    "Focus on a step-by-step 'how to use the code' guide + a practical saving tip. Start the title with a verb or a question.",
    "Focus on the store's top product categories and sections. Title mentions a category + the saving value.",
    "Focus on 'why choose this store' — its competitive edge and trust signals. Title highlights the differentiator.",
    "Tie the offer to the season/occasion with a gentle urgency tone. Use a specific seasonal title.",
    "Use an FAQ style — answer real shopper questions about the code, shipping, and returns.",
]


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
    # زاوية فريدة لكل صفحة (تدوير حسب المتجر + اللغة) — تنويع يمنع القوالب المكررة
    _seed = int(job.get("matched_master_id") or 0) + (0 if lang == "ar" else 3)
    if lang == "en":
        angle = _ANGLES_EN[_seed % len(_ANGLES_EN)]
        return (
            "Write an English SEO landing page for the target keyword and store below:\n"
            f"```json\n{canonical}\n```\n"
            f"UNIQUE ANGLE for THIS page — do NOT use a generic templated title like "
            f"'Best Discount Code | Latest Exclusive Offers'; make the title and structure distinct: {angle}\n"
            "Follow the system prompt rules. Return valid JSON only."
        )
    angle = _ANGLES_AR[_seed % len(_ANGLES_AR)]
    return (
        "اكتب صفحة هبوط SEO عربية للكلمة المستهدفة والمتجر التاليين:\n"
        f"```json\n{canonical}\n```\n"
        f"زاوية فريدة لهذه الصفحة — لا تستخدم عنواناً قالبياً عاماً مثل "
        f"«أفضل كود خصم | أحدث العروض الحصرية»؛ اجعل العنوان والبنية مختلفين: {angle}\n"
        "التزم بقواعد الـ system prompt. ردك JSON صالح فقط."
    )


# ─── Per-language generation ────────────────────────────────────────────────
_BLOCKLIST_CACHE: Optional[list] = None


def _get_blocklist() -> list:
    """يحمّل أنماط الحظر مرّة (cache على مستوى العملية)."""
    global _BLOCKLIST_CACHE
    if _BLOCKLIST_CACHE is None:
        try:
            with get_db_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pattern, COALESCE(pattern_type,'substring') "
                        "FROM seo_keyword_blocklist"
                    )
                    _BLOCKLIST_CACHE = [(p, (t or "substring").lower())
                                        for p, t in cur.fetchall()]
        except Exception:
            _BLOCKLIST_CACHE = []
    return _BLOCKLIST_CACHE


def _body_has_blocked(text: str) -> bool:
    """يفحص نص الصفحة (عربي/إنجليزي) ضد قائمة الحظر (substring/regex)."""
    from api.seo.matcher import _is_blocked
    return _is_blocked(text or "", _get_blocklist())


def _generate_page_for_lang(job: dict, lang: str, job_id: int) -> tuple[bool, Optional[dict], Optional[str]]:
    """
    يولّد صفحة واحدة بلغة محدّدة. يرجّع (نجاح، meta، reason_if_failed).
    لا يعدّل حالة الـ job — المُتّصل يقرّر إجمالاً.
    """
    from api.utils.llm_client import call_llm  # lazy

    system = SYSTEM_PROMPT_EN if lang == "en" else SYSTEM_PROMPT_AR
    user_prompt = _build_user_prompt(job, lang)
    prompt_hash = hashlib.sha256((system + user_prompt).encode("utf-8")).digest()

    # إعادة المحاولة عند الفشل العابر (التوليد عشوائي): JSON غير صالح/بتر/رد فارغ
    # غالباً تنجح المحاولة الثانية. نتوقّف فوراً لو السبب نضوب الميزانية (لا فائدة).
    res = None
    data: Optional[dict] = None
    best_data: Optional[dict] = None
    best_words = -1
    diag = ""
    for attempt in range(3):
        res = call_llm(
            purpose=f"seo_copy_{lang}",
            system=system,
            user=user_prompt,
            max_tokens=MAX_TOKENS,
            temperature=0.6,
        )
        diag = f"provider={res.provider} model={res.model}"

        if res.refused_by_guardian:
            reason = f"{diag} REFUSED_BY_GUARDIAN (daily LLM budget exhausted)"
            _log.warning("LLM refused for job=%s lang=%s: %s", job_id, lang, reason)
            return False, None, reason  # نضوب الميزانية — الإعادة بلا فائدة

        if res.text:
            cand = _parse_json(res.text)
            if cand and cand.get("body_markdown"):
                body = cand["body_markdown"]
                words = len(re.findall(r"\S+", body))
                # حارس جودة: أحرف سيريلية/صينية = هلوسة موديل عشوائية → ارفض وأعد
                has_foreign = bool(re.search(r"[Ѐ-ӿ一-鿿]", body))
                # احتفظ بأطول ناتج نظيف عبر المحاولات (احتياط لو كلها قصيرة)
                if not has_foreign and words > best_words:
                    best_data, best_words = cand, words
                # نجاح كامل: طويل بما يكفي + نظيف
                if words >= MIN_GEN_WORDS and not has_foreign:
                    break
                _log.info("seo gen attempt %d short/dirty job=%s lang=%s "
                          "(words=%d foreign=%s) — retrying",
                          attempt + 1, job_id, lang, words, has_foreign)
                continue
        _log.warning("seo gen attempt %d failed for job=%s lang=%s (%s) — retrying",
                     attempt + 1, job_id, lang, diag)

    # أفضل ناتج عبر المحاولات (الأطول النظيف) — أفضل من رفض الـ job كلياً
    data = best_data

    if not data or not data.get("body_markdown"):
        # فشل بعد كل المحاولات — نحفظ سبباً دقيقاً للتشخيص (للوحة الوظائف الفاشلة)
        if res is not None and not res.text:
            reason = f"{diag} EMPTY_RESPONSE err={(res.error or 'no_error_msg')[:200]}"
        else:
            preview = (res.text or "")[:300].replace("\n", " ") if res else ""
            reason = f"{diag} JSON_PARSE_FAIL len={len(res.text) if res else 0} preview={preview}"
        _log.warning("seo gen failed after retries for job=%s lang=%s: %s", job_id, lang, reason)
        return False, None, reason

    title = (data.get("title_meta") or "")[:180]
    desc = (data.get("description_meta") or "")[:280]
    body = data["body_markdown"]
    body_hash = hashlib.sha256(body.encode("utf-8")).digest()
    word_count = len(re.findall(r"\S+", body))

    # فلتر المحتوى: لا ننشئ صفحة نصّها/عنوانها يحتوي كلمة محظورة (عربي/إنجليزي)
    if _body_has_blocked(f"{title} {desc} {body}"):
        return False, None, f"{diag} BODY_BLOCKED (banned word in generated content)"

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
    }, None


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
                       m.store_tags, m.store_tags_en,
                       COALESCE(m.seo_enabled, TRUE) AS seo_enabled
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
    # قائمة المنع: متجر مُعطّل SEO لا يُولَّد له إطلاقاً (نقطة اختناق تحمي كل المسارات).
    if not job["seo_enabled"]:
        _mark_failed(job_id, "store SEO disabled (blocklist) — skipped")
        return False

    # 1) العربية — الأساس
    ar_ok, ar_meta, ar_reason = _generate_page_for_lang(job, "ar", job_id)
    if not ar_ok:
        # نحفظ السبب الحقيقي بدل رسالة عامة
        _mark_failed(job_id, f"AR_FAIL: {ar_reason or 'unknown'}")
        return False

    # 2) الإنجليزية — إضافة لو bilingual مفعّل (فشلها لا يكسر العربية)
    total_cost = ar_meta["cost_usd"] if ar_meta else 0.0
    if BILINGUAL_ENABLED:
        en_ok, en_meta, en_reason = _generate_page_for_lang(job, "en", job_id)
        if en_ok and en_meta:
            total_cost += en_meta["cost_usd"]
        else:
            _log.info("English generation skipped/failed for job=%s: %s", job_id, en_reason or "?")

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
