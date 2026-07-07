---
name: distinguish-bot-spike-from-real-promo-3-signal-check
description: Before calling a traffic spike a bot, run a 3-signal check (visitor_id diversity + timing gaps + ASN diversity). VPN usage from Italy/hosting-adjacent ASNs is legitimate in KSA context and must not be blocklisted.
type: feedback
originSessionId: b6ba939a-2469-4f6a-9833-5d2da06c5e04
---
**Case (2026-07-07):** I called two Jun 26 patterns "scrapers" — Milan/Aruba (ASN 63023) and the Jun 26 chart spike. Owner corrected me with two sentences: «القفزه كانت يوم اعلان وزعته الا اصحابي» and «اما ايطاليا فغالبا انه كان مشغل في بي ان». SQL verification confirmed him:
- Jun 26 = 22 unique real KSA visitors across 5 cities and 4-5 Saudi ISPs (STC/Zain/Mobily/Etihad) = classic "shared with friends" pattern.
- Milan/Aruba (ASN 63023) = 6 distinct visitor_ids with human-spaced timing (minutes apart, not seconds); two of them matched the top monthly repeat-visitors list from Riyadh mobile → same friends on a VPN.
- Jul 4 (which I originally labeled the "spike") was actually 529 Google Cloud Dallas bots — a separate, unrelated event on a different day.

**Why:** ASN alone lies. Hosting ASNs (Aruba, Level 3, sometimes even AWS via consumer VPN) carry legitimate VPN users in KSA where residential access to some services requires masking. Blocklisting these blindly = deleting real users' visits.

**How to apply — the 3-signal check before calling any spike a bot:**
1. **visitor_id diversity** — bots typically share one visitor_id or rotate through a handful. Humans yield N distinct visitor_ids where N ≈ visit count.
2. **Timing gaps between hits** — bots hit in seconds (crawlers, scrapers). Humans in minutes (reading, tab-switching).
3. **ASN diversity across the spike** — bots use one ASN (e.g., ASN 15169 Google Cloud for 529/535 Jul 4 hits). Real audiences show multiple ISPs (STC + Zain + Mobily + Etihad = friend network).

Only if all three signals point to "same visitor_id / seconds apart / single ASN" → confidently a bot.

**KSA-specific context:**
- VPN usage is common; do NOT blocklist consumer-egress ASNs (Aruba S.p.A ASN 63023, some Level 3 endpoints ASN 3356) even though they're also hosting providers.
- Confirmed bot-only ASNs for the current blocklist stay: 14618/16509 AWS, 15169/396982 Google Cloud, 8075 Azure, 24940 Hetzner, 16276 OVH, 63949 Linode, 14061 DigitalOcean, 20473 Vultr, 132203 Tencent, 200651 Flokinet, 51167 Contabo, 60068 CDN77. These are pure hosting, no meaningful consumer VPN egress.

Aligns with [[feedback_mirror_audit]] (verify by trace not claim) and [[feedback_no_dead_code]] (don't filter what isn't confirmed noise).
