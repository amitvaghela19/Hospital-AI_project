"""Per-browser-session config (never written to git or shared across users)."""

from __future__ import annotations

from typing import Any

_SESSION_KEY = "_user_session_config"


def _store() -> dict[str, Any]:
    try:
        import streamlit as st

        if _SESSION_KEY not in st.session_state:
            st.session_state[_SESSION_KEY] = {}
        return st.session_state[_SESSION_KEY]
    except Exception:
        # MCP scripts outside Streamlit: ephemeral module bucket (not for production cloud).
        if not hasattr(_store, "_fallback"):
            _store._fallback = {}  # type: ignore[attr-defined]
        return _store._fallback  # type: ignore[attr-defined]


def get_session_value(key: str, default: Any = None) -> Any:
    return _store().get(key, default)


def set_session_value(key: str, value: Any) -> None:
    _store()[key] = value


def pop_session_value(key: str) -> None:
    _store().pop(key, None)


def clear_llm_session() -> None:
    for key in (
        "llm_provider_mode",
        "llm_ollama_url",
        "llm_ollama_primary",
        "llm_ollama_fallback",
        "llm_custom_base_url",
        "llm_custom_api_key",
        "llm_custom_model",
        "llm_custom_health_path",
        "integrations",
        "ollama_primary_override",
        "ollama_fallback_override",
    ):
        pop_session_value(key)


def mask_secret(value: str | None, visible: int = 4) -> str:
    if not value:
        return "—"
    s = str(value)
    if len(s) <= visible:
        return "•" * len(s)
    return "•" * (len(s) - visible) + s[-visible:]
