---
name: health-citation-sourcing
description: Mayo Clinic + NIH ODS hard-block crawlers (403) so they read as broken links in Ahrefs; use Harvard Nutrition Source for YMYL health citations instead
metadata: 
  node_type: memory
  type: reference
  originSessionId: 1de45ec2-9d7b-4584-bbb4-3afff35c7be3
---

For YMYL health/supplement blog articles, **which** authoritative source you cite matters for the SEO audit, not just whether it's authoritative:

- **Mayo Clinic (`mayoclinic.org`)** — hard-blocks automated requests: returns **403 to both browsers and crawlers** (incl. AhrefsBot) from server IPs. Every Mayo citation eventually shows up as a "broken link" (4xx) in Ahrefs even though the page works for a human. **Avoid.**
- **NIH ODS (`ods.od.nih.gov`)** — also 403s many server IPs, BUT Ahrefs does reach it (its existing links weren't flagged). Inconsistent — risky.
- **Harvard T.H. Chan Nutrition Source (`nutritionsource.hsph.harvard.edu`)** — clean **200 for browsers AND bots**. Use its **direct** host, not the old `www.hsph.harvard.edu/nutritionsource/…` form (that 301-redirects). Pages verified live: `/magnesium/`, `/vitamin-d/`, `/vitamin-c/`, `/omega-3-fats/`, `/biotin-vitamin-b7/`, `/collagen/`, `/multivitamin/`, `/what-should-you-eat/protein/`.
- **JISSN / BioMed Central (`jissn.biomedcentral.com`)** — returns **406 to bots but 200 to browsers** (content-negotiation). Ahrefs flags it as broken but it's a **false positive** — the ISSN position stands (creatine, protein) are live; keep them.

2026-07-11 (web `2ecc937`): replaced 6 Mayo + 1 dead Cleveland Clinic biotin citation across the supplement cluster with Harvard equivalents; kept JISSN. When verifying a "broken link", always re-check with a **real browser UA** — distinguish a genuine 404 from a 403/406 bot-block. See [[web-blog-monolith-oom-and-client-prop-serialization]] [[content-guardrails-playbook]] [[health-content-cluster]].
