from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.common import REDIS_URL

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        import redis

        _client = redis.from_url(REDIS_URL, decode_responses=True)
        _client.ping()
        return _client
    except Exception:
        _client = None
        return None


def cache_get(key: str) -> Any | None:
    client = _get_client()
    if not client:
        return None
    try:
        val = client.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    client = _get_client()
    if not client:
        return False
    try:
        client.setex(key, ttl_seconds, json.dumps(value))
        return True
    except Exception:
        return False


def llm_cache_key(kind: str, model: str, payload: Any) -> str:
    """Stable Redis key for LLM phrasing/format responses."""
    blob = json.dumps(
        {"kind": kind, "model": model or "", "payload": payload},
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:40]
    return f"llm:{kind}:{digest}"


def is_available() -> bool:
    return _get_client() is not None
