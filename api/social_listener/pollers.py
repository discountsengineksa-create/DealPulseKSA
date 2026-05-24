"""
Active polling for legitimate, free social monitoring sources.

ما الذي يعمل فعلاً (واقع 2026):
  • Reddit API           → مجاني، يعمل تماماً (subreddit search via .json endpoints)
  • RSS feeds            → مجاني، يدعم Google Alerts (يولّد RSS من بحث Google)
  • Telegram channels    → مجاني عبر Bot API (للقنوات العامة فقط)

ما لا يعمل (وأخبرناك):
  • X (Twitter) Recent Search — أُلغي من Free tier في 2023. تحتاج Basic ($200/شهر)
    أو Pro ($5000/شهر) للقراءة. نستقبل mentions منه فقط عبر webhook (Zapier).
  • Instagram/Facebook    — Meta لا توفّر Mention search API مجاني.
  • Threads               — لا API قراءة.

استراتيجية مفيدة بدون X API:
  1. Reddit r/saudiarabia + r/dubai + r/uae + r/jeddah + r/riyadh
     → مجتمعات نشطة بأسئلة "وش أفضل كود خصم لـ X"
  2. Google Alerts → RSS → polling → نلتقط أي ذكر لـ "DealPulse" أو
     "نبض الصفقات" أو ["كود خصم" + اسم المتجر] على كامل الإنترنت
  3. Telegram public channels: قنوات الكوبونات الكبرى نراقبها للترند

كل poller:
  • يجلب آخر mentions
  • يُمرّرها لـ ingest_signal() — يعتني بالـ dedup
  • سيلتقطها process_new_signals() في الدورة التالية + يولّد drafts
"""
from __future__ import annotations

import hashlib
import json as _json
import logging
import os
from typing import Iterable

import requests

from api.social_listener.ingest import ingest_signal

_log = logging.getLogger("dp.social.poller")


# ─── Keyword targets (Arabic + English) ─────────────────────────────────────
DEFAULT_KEYWORDS_AR = [
    "كود خصم", "كوبون خصم", "كوبونات", "عروض خصم",
    "تخفيضات", "الجمعة البيضاء", "يوم التأسيس", "اليوم الوطني",
    "عروض رمضان", "نبض الصفقات", "DealPulse",
]
DEFAULT_KEYWORDS_EN = [
    "saudi coupon", "saudi discount code", "ksa promo code",
    "noon coupon", "amazon ksa discount", "white friday saudi",
    "founding day deals", "dealpulse",
]
ALL_DEFAULT_KEYWORDS = DEFAULT_KEYWORDS_AR + DEFAULT_KEYWORDS_EN


# ═══════════════════════════════════════════════════════════════════════════
#  Reddit poller (free, no auth required for read-only .json endpoints)
# ═══════════════════════════════════════════════════════════════════════════
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT",
                              "DealPulseKSA-Listener/1.0 (mention monitor)")
REDDIT_SUBREDDITS = os.getenv(
    "REDDIT_SUBREDDITS",
    "saudiarabia,riyadh,jeddah,uae,dubai,kuwait,bahrain"
).split(",")


def poll_reddit(*, keywords: Iterable[str] | None = None, limit_per_sub: int = 25) -> dict:
    """
    يبحث في subreddits المحدّدة عن أي post/comment يحتوي كلمة مستهدفة.
    يعتمد على /r/{sub}/new.json (لا يحتاج OAuth).

    Returns: {scanned, ingested, duplicate, errors}
    """
    kws = list(keywords) if keywords else ALL_DEFAULT_KEYWORDS
    kws_lower = [k.lower() for k in kws]
    stats = {"scanned": 0, "ingested": 0, "duplicate": 0, "errors": 0}

    for sub in [s.strip() for s in REDDIT_SUBREDDITS if s.strip()]:
        try:
            r = requests.get(
                f"https://www.reddit.com/r/{sub}/new.json",
                params={"limit": limit_per_sub},
                headers={"User-Agent": REDDIT_USER_AGENT},
                timeout=10,
            )
            if r.status_code != 200:
                _log.warning("Reddit r/%s returned %s", sub, r.status_code)
                stats["errors"] += 1
                continue

            posts = (r.json() or {}).get("data", {}).get("children", [])
            for child in posts:
                stats["scanned"] += 1
                p = child.get("data", {}) or {}
                title = (p.get("title") or "").lower()
                body  = (p.get("selftext") or "").lower()
                full  = title + " " + body

                if not any(kw in full for kw in kws_lower):
                    continue

                res = ingest_signal(
                    platform=f"reddit:{sub}",
                    external_id=str(p.get("id") or hashlib.md5(full.encode()).hexdigest()[:10]),
                    content=(p.get("title") or "")[:1000] + "\n\n" +
                            (p.get("selftext") or "")[:1500],
                    author_handle=p.get("author"),
                    author_followers=None,  # Reddit لا يكشف العدد عبر JSON
                    source_url=f"https://reddit.com{p.get('permalink', '')}",
                )
                if res.get("duplicate"):
                    stats["duplicate"] += 1
                elif res.get("signal_id"):
                    stats["ingested"] += 1
        except Exception as exc:
            _log.error("poll_reddit r/%s failed: %s", sub, str(exc)[:200])
            stats["errors"] += 1

    _log.info("Reddit poll: %s", stats)
    return stats


# ═══════════════════════════════════════════════════════════════════════════
#  RSS poller (Google Alerts feeds)
# ═══════════════════════════════════════════════════════════════════════════
RSS_FEEDS_RAW = os.getenv("SOCIAL_RSS_FEEDS", "").strip()


def poll_rss(*, feeds: Iterable[str] | None = None) -> dict:
    """
    يجلب RSS feeds (مفيد بشكل خاص لـ Google Alerts).

    إعداد Google Alerts:
      1. اذهب إلى google.com/alerts
      2. أنشئ alert لـ "نبض الصفقات" / "DealPulse" / "كود خصم نون"...
      3. Settings → Delivery to: RSS feed
      4. انسخ رابط الـ feed
      5. في Railway env: SOCIAL_RSS_FEEDS=url1,url2,url3

    Returns: {scanned, ingested, duplicate, errors}
    """
    feed_list = list(feeds) if feeds else \
                [f.strip() for f in RSS_FEEDS_RAW.split(",") if f.strip()]
    if not feed_list:
        return {"skipped": "no_feeds_configured"}

    stats = {"scanned": 0, "ingested": 0, "duplicate": 0, "errors": 0}

    # نستخدم XML parsing بسيط — لا نضيف dependency feedparser
    import re
    from xml.etree import ElementTree as ET

    for feed_url in feed_list:
        try:
            r = requests.get(feed_url, timeout=15,
                             headers={"User-Agent": REDDIT_USER_AGENT})
            if r.status_code != 200:
                _log.warning("RSS %s returned %s", feed_url[:60], r.status_code)
                stats["errors"] += 1
                continue

            # نُنظّف XML من حروف غير صالحة قد تكسر الـ parser
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', r.text)
            root = ET.fromstring(text)

            # Google Alerts feeds = Atom format
            # المسارات الشائعة: ./{ns}entry, ./channel/item
            ns_atom = "{http://www.w3.org/2005/Atom}"
            items = root.findall(f"{ns_atom}entry") or root.findall(".//item")

            for item in items:
                stats["scanned"] += 1
                title_el = item.find(f"{ns_atom}title") if root.tag.startswith(ns_atom) \
                           else item.find("title")
                link_el = item.find(f"{ns_atom}link") if root.tag.startswith(ns_atom) \
                          else item.find("link")
                summary_el = item.find(f"{ns_atom}content") or item.find(f"{ns_atom}summary") \
                             if root.tag.startswith(ns_atom) else item.find("description")
                id_el = item.find(f"{ns_atom}id") if root.tag.startswith(ns_atom) \
                        else item.find("guid")

                title = "".join((title_el.itertext() if title_el is not None else [""])).strip()
                summary = "".join((summary_el.itertext() if summary_el is not None else [""])).strip()
                # Atom link قد يكون <link href="..."/>
                href = ""
                if link_el is not None:
                    href = link_el.attrib.get("href") or (link_el.text or "")
                ext_id = (id_el.text if id_el is not None and id_el.text
                          else hashlib.md5((title + href).encode()).hexdigest()[:16])

                if not title:
                    continue

                # نزيل HTML من الملخّص
                summary_clean = re.sub(r"<[^>]+>", "", summary)[:1500]

                res = ingest_signal(
                    platform="rss:google-alerts",
                    external_id=ext_id[:120],
                    content=f"{title}\n\n{summary_clean}"[:3000],
                    source_url=href[:500] if href else None,
                )
                if res.get("duplicate"):
                    stats["duplicate"] += 1
                elif res.get("signal_id"):
                    stats["ingested"] += 1
        except Exception as exc:
            _log.error("poll_rss %s failed: %s", feed_url[:60], str(exc)[:200])
            stats["errors"] += 1

    _log.info("RSS poll: %s", stats)
    return stats


# ═══════════════════════════════════════════════════════════════════════════
#  Orchestrator
# ═══════════════════════════════════════════════════════════════════════════
def run_all_pollers() -> dict:
    """
    دورة كاملة: Reddit + RSS. يستدعيها الـ scheduler كل 10 دقائق.
    بعد الجمع، process_new_signals() (في responder.py) يحلّل الإشارات
    الجديدة ويولّد drafts للرد اليدوي من الداشبورد.
    """
    return {
        "reddit": poll_reddit(),
        "rss":    poll_rss(),
    }
