"""
Schema.org JSON-LD generator — يحوّل صفحة هبوط إلى structured data كاملة.

الهدف:
  1. Google يعرضك في Rich Results / AI Overviews
  2. ChatGPT / Gemini / Perplexity يقتبسونك كمصدر موثوق (SGE optimization)
  3. Bing/Copilot يضمّك إلى سياقات إجاباتهم

الأنواع المُولَّدة لكل صفحة:
  • Article          → نوع المحتوى الرئيسي
  • Organization     → DealPulse KSA كمُصدر
  • FAQPage          → الأسئلة المستخرجة من body_markdown (لو وُجدت)
  (مسار التنقّل BreadcrumbList تُصدره الواجهة app/c/[slug] — مصدر واحد مُرمَّز صالح.)

كل ذلك في JSON-LD واحد @graph (الأسلوب المفضّل لـ Google 2024+).

استخدام:
    from api.seo.schema_markup import build_jsonld
    page_data = {...}  # من api/routers/seo.py
    jsonld_dict = build_jsonld(page_data, site_url="https://www.dealpulseksa.com")
    # ضع نتيجة json.dumps(jsonld_dict) داخل <script type="application/ld+json">
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

SITE_URL = os.getenv("SITE_URL", "https://www.dealpulseksa.com").rstrip("/")
SEO_PAGE_PATH = os.getenv("SEO_PAGE_PATH", "/c/{slug}")

ORG_NAME_AR = "نبض الصفقات"
ORG_NAME_EN = "DealPulse KSA"
ORG_DESC_AR = "منصة سعودية لكوبونات وخصومات عشرات المتاجر — تشمل البراندات العالمية والمحلية والمتاجر السعودية، مع عروض المواسم الكبرى والصفقات اليومية."
ORG_DESC_EN = "Saudi platform for discount codes from dozens of stores — spanning international and local brands and Saudi retailers, with major-season offers and daily deals."
ORG_LOGO = f"{SITE_URL}/logo.png"

KSA_LANGS = ["ar", "en"]
KSA_AREA = {"@type": "Country", "name": "Saudi Arabia"}


# ─── Helpers ────────────────────────────────────────────────────────────────
def _extract_faqs(body_markdown: str, max_faqs: int = 6) -> list[dict]:
    """
    يستخرج أسئلة شائعة من body. يبحث عن H2/H3 بشكل سؤال (؟ في الآخر أو
    كلمات استفهام في الأول). الجواب = النص بعد العنوان حتى العنوان التالي.

    يرجّع list من dicts: [{"q": "...", "a": "..."}, ...] أو [] لو لم يجد.
    """
    if not body_markdown:
        return []

    # نُقسّم على العناوين ## أو ###
    sections = re.split(r'^(#{2,3})\s+(.+)$', body_markdown, flags=re.MULTILINE)
    # sections = [pre, '##', 'title', body, '##', 'title', body, ...]

    qa_patterns_ar = ('؟', 'كيف', 'متى', 'أين', 'لماذا', 'ما هو', 'ما هي', 'هل')
    qa_patterns_en = ('?', 'how ', 'when ', 'where ', 'why ', 'what ', 'is ', 'are ', 'can ')

    faqs: list[dict] = []
    i = 1
    while i + 2 < len(sections):
        title = (sections[i + 1] or "").strip()
        body = (sections[i + 2] or "").strip()

        title_l = title.lower()
        is_question = (
            title.endswith('؟') or title.endswith('?') or
            any(title.startswith(p) for p in qa_patterns_ar) or
            any(title_l.startswith(p) for p in qa_patterns_en)
        )

        if is_question and len(body) >= 20:
            # نزيل markdown formatting من الجواب
            clean_body = re.sub(r'^[-*]\s+', '', body, flags=re.MULTILINE)
            clean_body = re.sub(r'\n{2,}', ' ', clean_body)
            clean_body = re.sub(r'\s+', ' ', clean_body).strip()
            faqs.append({"q": title.rstrip('؟?').strip(), "a": clean_body[:500]})
            if len(faqs) >= max_faqs:
                break
        i += 3

    return faqs


def _abs_url(slug: str) -> str:
    """URL مطلق للصفحة — الـ slug مُرمَّز (عربي/مسافات) ليكون URL صالحاً يطابق canonical."""
    return f"{SITE_URL}{SEO_PAGE_PATH.format(slug=quote(slug, safe=''))}"


# ─── Builders for each schema type ──────────────────────────────────────────
def _build_organization(lang: str = "ar") -> dict:
    return {
        "@type":       "Organization",
        "@id":         f"{SITE_URL}/#organization",
        "name":        ORG_NAME_AR if lang == "ar" else ORG_NAME_EN,
        "alternateName": ORG_NAME_EN if lang == "ar" else ORG_NAME_AR,
        "url":         SITE_URL,
        "logo":        {"@type": "ImageObject", "url": ORG_LOGO},
        "description": ORG_DESC_AR if lang == "ar" else ORG_DESC_EN,
        "areaServed":  KSA_AREA,
        "knowsLanguage": KSA_LANGS,
    }


def _build_article(page: dict, lang: str) -> dict:
    url = _abs_url(page["slug"])
    published = page.get("published_at") or datetime.now(timezone.utc).isoformat()

    article: dict[str, Any] = {
        "@type":            "Article",
        "@id":              f"{url}#article",
        "url":              url,
        "headline":         (page.get("title_meta") or page.get("target_keyword", ""))[:110],
        "description":      page.get("description_meta") or "",
        "inLanguage":       lang,
        "datePublished":    published,
        "dateModified":     published,
        "author":           {"@id": f"{SITE_URL}/#organization"},
        "publisher":        {"@id": f"{SITE_URL}/#organization"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "isAccessibleForFree": True,
    }
    if page.get("logo_url"):
        article["image"] = page["logo_url"]
    return article


# ملاحظة: لا نولّد Offer/Product للكوبونات. الكوبون كود خصم لا منتج بسعر، وقوقل
# يطالب Offer/Product بحقل price (خطأ «price ناقص» في تقارير Merchant/Product).
# اختلاق سعر = فبركة، والكوبون أصلاً بلا Rich Result عبر Offer. نكتفي بأنواع
# صالحة تعطي نتائج غنية فعلاً: Article + FAQPage + BreadcrumbList + Organization.


def _build_faq(faqs: list[dict]) -> dict | None:
    if not faqs:
        return None
    return {
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type":          "Question",
                "name":           f["q"][:300],
                "acceptedAnswer": {"@type": "Answer", "text": f["a"][:500]},
            }
            for f in faqs
        ],
    }


# ─── Public API ─────────────────────────────────────────────────────────────
def build_jsonld(page: dict, *, site_url: str | None = None) -> dict:
    """
    يبني @graph موحّد فيه كل الأنواع المنطبقة على الصفحة.

    page dict متوقّع: slug, target_keyword, lang, title_meta, description_meta,
                      body_markdown, published_at, store_id, store_name,
                      logo_url, discount_value, public_coupon, store_tags.

    يرجّع dict جاهز لـ json.dumps + إدراج في <script type="application/ld+json">.
    """
    lang = page.get("lang") or "ar"

    # لا BreadcrumbList هنا — الواجهة (app/c/[slug]) تُصدر المسار الوحيد المُرمَّز
    # الصالح؛ إصدار الباكند سابقاً حمل رابطاً عربياً خاماً أبطل المسار في GSC.
    graph: list[dict] = [
        _build_organization(lang),
        _build_article(page, lang),
    ]

    faqs = _extract_faqs(page.get("body_markdown") or "")
    faq_block = _build_faq(faqs)
    if faq_block:
        graph.append(faq_block)

    return {"@context": "https://schema.org", "@graph": graph}
