"""Ollama URL resolution for local dev, Streamlit Cloud, and tunneled deployments."""

from __future__ import annotations

import os
from typing import Any

import requests

_DEFAULT_LOCAL = "http://127.0.0.1:11434"
_FALLBACK_LOCAL = "http://localhost:11434"
_PROBE_TIMEOUT_S = 4


def is_streamlit_cloud() -> bool:
    """True when the app runs on Streamlit Community Cloud (not on your laptop)."""
    env = (os.environ.get("STREAMLIT_RUNTIME_ENVIRONMENT") or "").strip().lower()
    if env == "cloud":
        return True
    # Legacy / alternate signals used by hosted Streamlit.
    if os.environ.get("STREAMLIT_SHARING_MODE"):
        return True
    return False


def _secrets_ollama_url() -> str | None:
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            if "OLLAMA_URL" in st.secrets:
                return str(st.secrets["OLLAMA_URL"]).strip()
            ollama = st.secrets.get("ollama")
            if isinstance(ollama, dict) and ollama.get("url"):
                return str(ollama["url"]).strip()
    except Exception:
        pass
    return None


def _candidate_ollama_urls() -> list[str]:
    urls: list[str] = []
    try:
        from streamlit_app.llm_provider import get_user_ollama_url

        user_url = get_user_ollama_url()
        if user_url:
            urls.append(user_url)
    except Exception:
        pass
    for raw in (_secrets_ollama_url(), os.environ.get("OLLAMA_URL"), _DEFAULT_LOCAL, _FALLBACK_LOCAL):
        if not raw:
            continue
        url = str(raw).strip().rstrip("/")
        if url and url not in urls:
            urls.append(url)
    return urls


def _probe_ollama(url: str) -> bool:
    try:
        r = requests.get(f"{url}/api/tags", timeout=_PROBE_TIMEOUT_S)
        return r.status_code == 200
    except Exception:
        return False


def resolve_ollama_url() -> str:
    """
    Return the first reachable Ollama base URL.
    Tries Streamlit secrets, env var, then 127.0.0.1 / localhost.
    """
    try:
        import streamlit as st

        cached = st.session_state.get("_ollama_resolved_url")
        if cached and _probe_ollama(str(cached)):
            return str(cached).rstrip("/")
    except Exception:
        pass

    for url in _candidate_ollama_urls():
        if _probe_ollama(url):
            try:
                import streamlit as st

                st.session_state["_ollama_resolved_url"] = url
                st.session_state["_ollama_probe_ok"] = True
            except Exception:
                pass
            return url

    try:
        import streamlit as st

        st.session_state["_ollama_probe_ok"] = False
    except Exception:
        pass

    # Default for error messages / health panel even when unreachable.
    return (_secrets_ollama_url() or os.environ.get("OLLAMA_URL") or _DEFAULT_LOCAL).rstrip("/")


def get_ollama_url() -> str:
    return resolve_ollama_url()


def ollama_connection_status() -> dict[str, Any]:
    """Structured status for UI banners and health checks."""
    url = get_ollama_url()
    ok = _probe_ollama(url)
    cloud = is_streamlit_cloud()
    return {
        "reachable": ok,
        "url": url,
        "cloud_hosted": cloud,
        "mode": "cloud" if cloud else "local",
    }


def deployment_guidance() -> str:
    cloud = is_streamlit_cloud()
    if cloud:
        return (
            "Hosted on **Streamlit Cloud** — no API keys or model passwords are stored in this repository. "
            "Each user configures their own LLM in the sidebar (Clinician/Analyst): either a **custom API** "
            "or an Ollama endpoint URL (tunnel required for cloud). "
            "**Use Ollama Desktop only if you are not using a custom provider/API.** "
            "Dashboards and chat still work with deterministic fallbacks when no LLM is connected."
        )
    return (
        "Running locally. **Use Ollama Desktop only if you are not using a custom model/provider/API.** "
        "Otherwise configure your custom provider in the sidebar (Clinician/Analyst unlock required). "
        "Credentials remain in this browser session only."
    )
