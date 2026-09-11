# Visual / Mobile-First / RTL Audit — dealpulseksa.com

**Status: BLOCKED — no screenshots captured. No visual or above-the-fold findings below are real; do not treat this file as a completed visual audit.**

## What was attempted (verbatim commands + results)

Tool: `capture_screenshot.py` (bundled with claude-seo plugin, run via
`runtime.py` — confirmed pre-installed, Chromium at
`ms-playwright\chromium-1234\chrome-win64\chrome.exe`, no install performed).

```
capture_screenshot.py "https://www.dealpulseksa.com/store/%D8%B3%D9%88%D9%8A%D8%AA%D8%B1" --viewport mobile --full
  → ✗ Failed: Page.goto: net::ERR_FAILED

capture_screenshot.py "https://dealpulseksa.com/store/%D8%B3%D9%88%D9%8A%D8%AA%D8%B1" --viewport mobile --full
  → ✗ Failed: Page.goto: net::ERR_FAILED

capture_screenshot.py "https://dealpulseksa.com/" --viewport mobile --full
  → ✗ Failed: Page.goto: net::ERR_FAILED

capture_screenshot.py "https://dealpulseksa.com/calendar" --viewport mobile --full
  → ✗ Failed: Page.goto: net::ERR_FAILED
```

All four navigation attempts (both `www.` and apex, both store and homepage
and calendar) failed identically before any pixel was rendered. `/calendar`
was never reached because the run stopped after the homepage failure in the
same batch — same error class, not re-tried.

## Root-cause isolation (not guesswork — three control tests)

1. **Raw HTTP works.** `curl -sS -o /dev/null -w "%{http_code}" https://dealpulseksa.com/`
   → `308` (redirect, healthy). `nslookup dealpulseksa.com` resolves fine
   (`216.198.79.1` present alongside IPv6/NAT64 addresses).
2. **A prior raw-mode fetch in this same audit folder succeeded.**
   `seo\audits\www.dealpulseksa.com-audit\homepage-render.json` (already on
   disk, not produced by me this run) shows `"status_code": 200` for
   `https://www.dealpulseksa.com/` with full HTML returned — confirms the
   site itself is reachable over plain HTTP and confirms `lang="ar"
   dir="rtl"` is present in the served markup.
3. **Playwright/Chromium itself is not broken.** Control test against
   `https://example.com/` with the identical `capture_screenshot.py --viewport
   mobile` command **succeeded** (`✓ Saved to .\example_com_mobile.png`,
   file removed after the test since it is not a deliverable for this audit).

Conclusion: this is not a missing-dependency problem and not a general
network outage — Chromium's browser-level navigation is specifically refused
for **dealpulseksa.com** (both host variants, all three target paths) while
the same browser reaches a control domain fine and plain HTTP reaches
dealpulseksa.com fine. This matches the existing memory entry
`claude_seo_plugin.md`: *"السحابة محجوبة عن dealpulseksa.com — تدقيق فعلي شغل
ترمنال فقط"* (cloud sandboxes are blocked from this domain at the
browser/bot-fingerprint level; likely Vercel/WAF bot-protection rejecting the
headless-Chromium TLS/JA3 fingerprint or the sandbox's IP range while
allowing plain HTTP clients). This held even though this session's Bash tool
runs on the local PC path (`C:\Users\PC\...`), not an obviously separate
cloud host — the block appears tied to the outbound network path this agent
process has, not to which tool issued the request.

## What I did NOT do

- I did not fabricate any above-the-fold, RTL-mirroring, carousel-direction,
  clipped-text, or mixed Latin/Arabic-alignment findings. Zero screenshots of
  `www.dealpulseksa.com` exist in `screenshots/` — the directory is empty
  after cleanup. Any visual claim about this site's actual rendered layout
  would be invention, which the project's zero-fabrication rule forbids.
- I did not install or reinstall Playwright/Chromium — confirmed present and
  working (control test above) before concluding the block is site-specific.

## What the raw HTML (not a screenshot) does confirm

From `homepage-render.json` (`mode_used: "raw"`, HTTP fetch, no rendering):

- `<html lang="ar" dir="rtl">` is set at the document root — correct RTL
  declaration exists in markup (says nothing about whether components
  respect it visually).
- `<meta name="viewport" content="width=device-width, initial-scale=1,
  maximum-scale=5">` — mobile viewport meta is present.
- `extracted_text` order (top of page, in source order): "محدَّث الآن
  مباشرةً" → "اكتشف أحدث كوبونات الخصم وعروض المتاجر في المملكة العربية
  السعودية" → "لا تدفع السعر كامل ما دام فيه خصم بانتظارك" → "تصفّح حسب
  التصنيف" → "اعثر على ما يناسبك بسرعة" → "البوت متاح أيضاً على تلجرام" →
  "احصل على إشعارات فورية لأقوى العروض، مفضلتك في جيبك، وميني آب احترافي بكل
  المميزات" → "افتح البوت". This is source/DOM order only — it does **not**
  establish visual position, since CSS/RTL flex-direction can reorder
  visually. No conclusion about above-the-fold placement can be drawn from
  this list; do not cite it as a layout finding.

## Recommendation

Re-run this same capture from a genuine local terminal session (per
`Claude_Memory/claude_code_cloud_sessions.md`: cloud/mobile Claude Code
sessions inherit memory but are network-blocked from this domain — only a
terminal-attached session on the actual dev machine reaches it), or confirm
with the site owner whether Vercel bot-protection / WAF rules should
allowlist this agent's egress IP range for legitimate automated QA. Until
then, this visual/RTL audit cannot be completed and should not be marked
done in any parent audit rollup.

## Files

- Screenshots directory (empty, cleanup performed):
  `c:\Users\PC\Desktop\Discounts_Engine\seo\audits\www.dealpulseksa.com-audit\screenshots\`
- Pre-existing raw fetch evidence used above:
  `c:\Users\PC\Desktop\Discounts_Engine\seo\audits\www.dealpulseksa.com-audit\homepage-render.json`
- This file:
  `c:\Users\PC\Desktop\Discounts_Engine\seo\audits\www.dealpulseksa.com-audit\findings\visual.md`
