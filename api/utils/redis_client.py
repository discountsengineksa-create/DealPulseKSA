"""
Lazy singleton Redis client.

Picks up REDIS_URL from env (Railway auto-injects when the Redis plugin
is provisioned). Falls back to a no-op in-memory shim when REDIS_URL is
unset — useful for unit tests and local dev without Redis. The shim
implements only the surface we touch (`get`, `set`, `incrbyfloat`,
`expire`, `xadd`, `ping`) so production code can stay un-conditional.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import redis  # type: ignore[import-untyped]

_log = logging.getLogger("dp.redis")
_client: Optional[Any] = None


class _NullRedis:
    """In-memory degenerate Redis. Logs writes but persists nothing across restarts."""

    def __init__(self) -> None:
        self._mem: dict[str, str] = {}

    def incrbyfloat(self, key: str, amount: float) -> float:
        cur = float(self._mem.get(key, "0"))
        new = cur + amount
        self._mem[key] = str(new)
        return new

    def get(self, key: str) -> Optional[str]:
        return self._mem.get(key)

    def set(self, key: str, value: str) -> bool:
        self._mem[key] = str(value)
        return True

    def expire(self, key: str, seconds: int) -> bool:  # noqa: ARG002
        return True

    def xadd(self, stream: str, fields: dict, maxlen: int | None = None,  # noqa: ARG002
             approximate: bool = True) -> str:  # noqa: ARG002
        _log.debug("XADD(%s) → %s", stream, fields)
        return "0-0"

    def ping(self) -> bool:
        return True


def get_redis() -> Any:
    """Return the process-wide Redis client (lazy)."""
    global _client
    if _client is not None:
        return _client

    url = os.getenv("REDIS_URL")
    if not url:
        _log.warning("REDIS_URL unset — using in-memory shim. NEVER in prod.")
        _client = _NullRedis()
        return _client

    try:
        client = redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        client.ping()
        _log.info("Redis connected: %s", url.split("@")[-1])
        _client = client
    except Exception as exc:
        _log.error("Redis connect failed: %s — falling back to in-memory shim", exc)
        _client = _NullRedis()
    return _client
