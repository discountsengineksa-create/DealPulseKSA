"""
Schema.org JSON-LD generator — يحوّل صفحة هبوط إلى structured data كاملة.

الهدف:
  1. Google يعرضك في Rich Results / AI Overviews
  2. ChatGPT / Gemini / Perplexity يقتبسونك كمصدر موثوق (SGE optimization)
  3. Bing/Copilot يضمّك إلى سياقات إجاباتهم

الأنواع المُولَّدة لكل صفحة:
  • Article          → نوع المحتوى الرئيسي
  • Offer            → الكوبون نفسه (سعر، عملة، صلاحية)
  • Organization     → DealPulse KSA كمُصدر
  • BreadcrumbList   → مسار الصفحة (Home > Category > Store)
  • FAQPage          → الأسئلة المستخرجة من body_markdown (لو وُجدت)

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
ORG_DESC_AR = "منصة سعودية متخصّصة في كوبونات وخصومات أكثر من 300 متجر، تشمل المواسم الكبرى والعروض اليومية."
ORG_DESC_EN = "Saudi platform specialized in verified discount codes from 300+ stores, including major-season offers and daily deals."
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


def _category_from_tags(store_tags: str | None) -> str | None:
    """يستخرج أول tag كـ category — بسيط ومحسوب."""
    if not store_tags:
        return None
    # store_tags بصيغة '{a,b,c}'
    s = store_tags.strip('{} ')
    if not s:
        return None
    first = s.split(',', 1)[0].strip().strip('"')
    return first or None


def _abs_url(slug: str) -> str:
    """URL مطلق للصفحة على الموقع."""
    return f"{SITE_URL}{SEO_PAGE_PATH.format(slug=slug)}"


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


def _build_breadcrumb(page: dict, lang: str) -> dict:
    home_label = "الرئيسية" if lang == "ar" else "Home"
    cat = _category_from_tags(page.get("store_tags"))
    store_id = page.get("store_id")
    page_label = page.get("title_meta") or page.get("target_keyword", "")

    items: list[dict] = [
        {"@type": "ListItem", "position": 1, "name": home_label, "item": SITE_URL},
    ]
    pos = 2
    if cat:
        items.append({
            "@type":    "ListItem",
            "position": pos,
            "name":     cat,
            "item":     f"{SITE_URL}/category/{quote(cat, safe='')}",
        })
        pos += 1
    # مستوى المتجر — يُضاف فقط عند وجود متجر مرتبط، مع رابطه (item). أي عنصر غير
    # أخير بلا item يُبطِل المسار كاملاً في Google (هذا كان سبب «الحقل item غير
    # مضمَّن»). والترميز يحمي من المسافات/العربية في store_id (مثل «عود رويال»).
    if store_id:
        items.append({
            "@type":    "ListItem",
            "position": pos,
            "name":     page.get("store_name") or store_id,
            "item":     f"{SITE_URL}/store/{quote(store_id, safe='')}",
        })
        pos += 1
    items.append({
        "@type":    "ListItem",
        "position": pos,
        "name":     page_label,
        "item":     _abs_url(page["slug"]),
    })

    return {"@type": "BreadcrumbList", "itemListElement": items}


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


def _build_offer(page: dict, lang: str) -> dict | None:
    """يبني Offer schema لو في كوبون فعلي + اسم متجر."""
    if not page.get("store_id") and not page.get("store_name"):
        return None

    coupon_code = page.get("public_coupon") or "AUTO_APPLIED"
    offer: dict[str, Any] = {
        "@type":         "Offer",
        "@id":           f"{_abs_url(page['slug'])}#offer",
        "name":          page.get("title_meta") or page.get("target_keyword", ""),
        "description":   page.get("description_meta") or "",
        "url":           _abs_url(page["slug"]),
        "availability":  "https://schema.org/InStock",
        "priceCurrency": "SAR",
        "seller": {
            "@type": "Organization",
            "name":  page.get("store_name") or page.get("store_id"),
        },
        "category":      _category_from_tags(page.get("store_tags")) or "Discount Coupon",
        "areaServed":    KSA_AREA,
    }
    if page.get("discount_value"):
        # discount_value قد يكون "20%" أو "50 SAR" — نتركه نصاً
        offer["priceSpecification"] = {
            "@type":             "PriceSpecification",
            "description":       f"Discount: {page['discount_value']}",
        }
    # IMPORTANT: للكوبونات حقيقية، نضيف couponCode
    if coupon_code and coupon_code != "AUTO_APPLIED":
        offer["couponCode"] = coupon_code
    return offer


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

    graph: list[dict] = [
        _build_organization(lang),
        _build_article(page, lang),
        _build_breadcrumb(page, lang),
    ]

    offer = _build_offer(page, lang)
    if offer:
        graph.append(offer)

    faqs = _extract_faqs(page.get("body_markdown") or "")
    faq_block = _build_faq(faqs)
    if faq_block:
        graph.append(faq_block)

    return {"@context": "https://schema.org", "@graph": graph}
