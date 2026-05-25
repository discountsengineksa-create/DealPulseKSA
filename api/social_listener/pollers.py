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
#  Orchestrator
# ═══════════════════════════════════════════════════════════════════════════
# NOTE: RSS / Google Alerts poller تمت إزالته (2026-05) — أثبت أن Google Alerts
# يعتمد على فهرسة Google بطيئة جداً للعربية. الاستراتيجية الجديدة تعتمد على
# Google Trends مع keyword CRUD في "محرك الفرص" (api/seo/trends_puller.py).

def run_all_pollers() -> dict:
    """
    دورة كاملة لجمع social signals: Reddit فقط الآن.
    يستدعيها الـ scheduler كل 10 دقائق. بعد الجمع، process_new_signals()
    (في responder.py) يحلّل الإشارات الجديدة ويولّد drafts للرد اليدوي.
    """
    return {
        "reddit": poll_reddit(),
    }
