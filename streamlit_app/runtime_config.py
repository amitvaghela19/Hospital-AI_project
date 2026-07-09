"""Runtime overrides for LLM models and external integrations (session-scoped)."""

from __future__ import annotations

import os
from typing import Any

_DEFAULT_PRIMARY = "deepseek-r1:latest"
_DEFAULT_FALLBACK = "llama3:latest"


def _secret_or_env(secret_key: str, env_key: str, default: str) -> str:
    try:
        import streamlit as st

        if hasattr(st, "secrets") and secret_key in st.secrets:
            return str(st.secrets[secret_key]).strip()
    except Exception:
        pass
    return os.environ.get(env_key, default)


def _default_primary() -> str:
    return _secret_or_env("OLLAMA_PRIMARY", "OLLAMA_PRIMARY", _DEFAULT_PRIMARY)


def _default_fallback() -> str:
    return _secret_or_env("OLLAMA_FALLBACK", "OLLAMA_FALLBACK", _DEFAULT_FALLBACK)


def get_ollama_primary() -> str:
    try:
        from streamlit_app.session_config import get_session_value

        override = get_session_value("ollama_primary_override")
        if override:
            return str(override).strip()
    except Exception:
        pass
    return _default_primary()


def get_ollama_fallback() -> str:
    try:
        from streamlit_app.session_config import get_session_value

        override = get_session_value("ollama_fallback_override")
        if override:
            return str(override).strip()
    except Exception:
        pass
    return _default_fallback()


def set_ollama_models(primary: str, fallback: str) -> None:
    try:
        from streamlit_app.session_config import set_session_value

        set_session_value("ollama_primary_override", (primary or "").strip() or None)
        set_session_value("ollama_fallback_override", (fallback or "").strip() or None)
        return
    except Exception:
        pass


def reset_ollama_models() -> None:
    try:
        from streamlit_app.session_config import pop_session_value

        pop_session_value("ollama_primary_override")
        pop_session_value("ollama_fallback_override")
    except Exception:
        pass


def get_integrations() -> dict[str, Any]:
    try:
        from streamlit_app.session_config import get_session_value

        stored = get_session_value("integrations")
        if isinstance(stored, dict):
            return dict(stored)
    except Exception:
        pass
    return {}


def update_integrations(**kwargs: Any) -> None:
    try:
        from streamlit_app.session_config import get_session_value, set_session_value

        current = dict(get_session_value("integrations") or {})
        for key, value in kwargs.items():
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value
        set_session_value("integrations", current)
    except Exception:
        pass


def integration(name: str, default: Any = None) -> Any:
    return get_integrations().get(name, default)
