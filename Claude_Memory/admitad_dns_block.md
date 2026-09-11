---
name: admitad-dns-block
description: "User's KSA network blocks admitad.com via DNS hijacking; fix is encrypted DNS (DoH/Cloudflare)"
metadata: 
  node_type: memory
  type: project
  originSessionId: e43e2541-11d8-48b5-a393-5be75907af00
---

On the user's **computer** (KSA network/ISP), `admitad.com` / `store.admitad.com` fail to load — Chrome shows `DNS_PROBE_FINISHED_NXDOMAIN`, Firefox shows "الخادوم غير موجود". The **phone works fine** (different DNS path).

**Root cause (verified 2026-07-18):** The ISP transparently intercepts plain port-53 DNS and forges an NXDOMAIN for admitad.com specifically. Proof: `nslookup admitad.com 8.8.8.8` returned "Non-existent domain" (forged — the interception hijacks even queries addressed to 8.8.8.8/1.1.1.1), but Google DoH JSON (`https://dns.google/resolve?name=admitad.com`) returned real IPs (104.26.13.214 / store → 5.187.1.114). Connecting by IP with `curl --resolve` gave HTTP 302 — **site is fully alive, no IP/SNI block, DNS-only block.** `mitgo.com` is NOT blocked (that's why the Mitgo ID login page loads first).

**Fix that worked:** Chrome → أمن المعلومات (Security) → "استخدام نظام أسماء النطاقات الآمن" (Use secure DNS) → ON → "مع" → **Cloudflare (1.1.1.1)**. Site loaded immediately.

**Key gotcha:** Changing plain OS DNS to 8.8.8.8/1.1.1.1 does NOT help — interception forges those too. Only **encrypted DNS (DoH)** bypasses it. Firefox equivalent: Privacy → "DNS عبر HTTPS" → Increased/Max → Cloudflare (NOT the tracking-protection section — user set that to Strict by mistake once). System-wide alternative: Cloudflare `1.1.1.1` app.

**Second issue (Firefox only):** After DNS was fixed, the Admitad panel loaded blank + showed "you're using an ad blocker" notice. Cause was **uBlock Origin** blocking the panel's scripts (userflow.com etc.). Fix: whitelist store.admitad.com in uBlock (click uBlock icon → big power button OFF for this site → reload). NOT caused by tracking protection — user's ETP was correctly on Standard and Firefox DoH was correctly on Cloudflare (I wrongly guessed Strict; user corrected me). Chrome had no ad blocker so the panel worked there immediately.

Related: [[admitad_affiliate_setup]]
