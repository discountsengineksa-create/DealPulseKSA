"""
Keyword blocklist helpers — White-Hat gates used by the SEO page generator.

Was: keyword→store matcher + automatic job enqueuer. `match_and_enqueue()`
(automatic job creation from trend_signals) was removed 2026-09-09 at the
owner's request — no more automatic SEO page generation. Jobs are queued
only explicitly via /admin/seo-seed-custom.

`_normalize_ar` is kept because it is documented as the canonical Arabic
normalization (see api/utils/arabic_search.py). `_is_blocked` is called by
the generator (api/seo/generator._body_has_blocked).
"""
from __future__ import annotations

import re


def _normalize_ar(s: str) -> str:
    """توحيد صور الحرف العربي: ة/ه، أإآ/ا، ى/ي، حذف التطويل والتشكيل.
    ضروري هنا لأن «منصه» و«منصة» صورتان لكلمة واحدة، وبدون التوحيد يمرّ أحدهما."""
    s = (s or "").strip().lower()
    s = re.sub(r"[ـً-ْ]", "", s)          # تطويل + تشكيل
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"[أإآ]", "ا", s)
    return re.sub(r"\s+", " ", s).strip()


def _is_blocked(keyword: str, blocklist: list[tuple[str, str]]) -> bool:
    kw = keyword.lower().strip()
    for pattern, ptype in blocklist:
        pat = (pattern or "").lower().strip()
        if not pat:
            continue
        if ptype == "exact" and kw == pat:
            return True
        if ptype == "substring" and pat in kw:
            return True
        if ptype == "regex":
            try:
                if re.search(pattern, keyword, re.IGNORECASE):
                    return True
            except re.error:
                continue
    return False
