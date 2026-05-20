"""
Single XADD wrapper. Centralises stream-name conventions and trimming policy.

Streams used in Week 1:
    events:raw       — every /track POST after validation + enrichment
    alerts:dispatch  — outbound email alerts (consumed by sender worker)
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .redis_client import get_redis

_log = logging.getLogger("dp.events")

# Cap each stream at ~500k entries (≈ a week of traffic at our current volume).
_MAXLEN = 500_000


def publish_event(stream: str, payload: dict[str, Any]) -> str:
    """
    XADD payload to `stream`. Returns the new entry ID (or "" on failure).

    Payload values must be primitives. Dicts/lists are JSON-encoded.
    Failure is non-fatal — the origin has already persisted the row in PG.
    """
    r = get_redis()
    flat: dict[str, str] = {}
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, (dict, list)):
            flat[k] = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        elif isinstance(v, bool):
            flat[k] = "1" if v else "0"
        else:
            flat[k] = str(v)
    try:
        return r.xadd(stream, flat, maxlen=_MAXLEN, approximate=True)
    except Exception as exc:
        _log.error("XADD %s failed: %s", stream, exc)
        return ""
