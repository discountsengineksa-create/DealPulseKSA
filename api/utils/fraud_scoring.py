"""
Compute a 0–100 quality score per event. Used downstream to weight clicks
in velocity snapshots — a bot-generated burst won't trip the spike alert.

Heuristics (subtractive; clamped to 0..100):
  -50 if datacenter ASN
  -30 if cf_bot_score < 30 (Cloudflare flagged as bot-likely)
  -20 if device_class == 'bot'
  -5  if region_code is empty (geo failed — slight signal degradation)
  +10 if cf_bot_score >= 70 AND not verified_bot (high-confidence human)

Datacenter detection uses a small in-process ASN blocklist of the common
hosting providers; full MaxMind ASN database is the upgrade path.
"""
from __future__ import annotations

from typing import Optional

from .geo_extractor import GeoContext

# Common hosting/cloud ASNs (humans rarely click coupons from these).
# Sources: AWS, GCP, Azure, Hetzner, OVH, Linode, DigitalOcean, Vultr, Tencent.
DATACENTER_ASNS: frozenset[int] = frozenset({
    14618,   # AWS (Amazon AES)
    16509,   # AWS (Amazon-02)
    15169,   # Google Cloud
    8075,    # Microsoft Azure
    24940,   # Hetzner
    16276,   # OVH
    63949,   # Linode
    14061,   # DigitalOcean
    20473,   # Choopa / Vultr
    132203,  # Tencent Cloud
    396982,  # Google Cloud
    200651,  # Flokinet
    51167,   # Contabo
    60068,   # Datacamp / CDN77
})


def is_datacenter(asn: Optional[int]) -> bool:
    return asn is not None and asn in DATACENTER_ASNS


def compute_quality_score(ctx: GeoContext) -> tuple[int, bool, bool]:
    """
    Return (score 0..100, is_datacenter, is_proxy).
    `is_proxy` is a placeholder until we wire a proxy database.
    """
    score = 100
    dc = is_datacenter(ctx.asn)
    proxy = False  # TODO: integrate proxycheck.io or MaxMind anonymous-IP DB

    if dc:
        score -= 50
    if ctx.cf_bot_score is not None and ctx.cf_bot_score < 30:
        score -= 30
    if ctx.device_class == "bot":
        score -= 20
    if ctx.region_code is None:
        score -= 5
    if ctx.cf_bot_score is not None and ctx.cf_bot_score >= 70 and not ctx.verified_bot:
        score += 10

    return max(0, min(100, score)), dc, proxy
