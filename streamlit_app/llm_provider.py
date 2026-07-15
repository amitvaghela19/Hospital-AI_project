"""Per-user LLM provider selection (Ollama vs custom API) — session-only, RBAC-gated in UI."""

from __future__ import annotations

import json
from typing import Any, Literal

import requests

from streamlit_app.session_config import get_session_value, set_session_value

ProviderMode = Literal["ollama", "custom_api", "none"]

OLLAMA_NOTE = (
    "**When to use Ollama Desktop:** only if you are **not** using a custom model, provider, or API. "
    "If you configure a custom API below, leave Ollama Desktop off and use your provider settings instead. "
    "Credentials stay in this browser session only — nothing is saved to GitHub or the server disk."
)


def get_provider_mode() -> ProviderMode:
    mode = str(get_session_value("llm_provider_mode", "ollama") or "ollama")
    if mode in ("ollama", "custom_api", "none"):
        return mode  # type: ignore[return-value]
    return "ollama"


def set_provider_mode(mode: ProviderMode) -> None:
    set_session_value("llm_provider_mode", mode)


def get_user_ollama_url() -> str | None:
    url = get_session_value("llm_ollama_url")
    return str(url).strip().rstrip("/") if url else None


def set_user_ollama_url(url: str) -> None:
    set_session_value("llm_ollama_url", (url or "").strip().rstrip("/") or None)


def get_custom_provider() -> dict[str, str]:
    return {
        "base_url": str(get_session_value("llm_custom_base_url", "") or "").strip().rstrip("/"),
        "api_key": str(get_session_value("llm_custom_api_key", "") or "").strip(),
        "model": str(get_session_value("llm_custom_model", "") or "").strip(),
        "health_path": str(get_session_value("llm_custom_health_path", "/v1/models") or "/v1/models").strip(),
        "name": str(get_session_value("llm_custom_name", "Custom provider") or "Custom provider").strip(),
    }


def set_custom_provider(
    *,
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    health_path: str = "/v1/models",
) -> None:
    set_session_value("llm_custom_name", name.strip() or "Custom provider")
    set_session_value("llm_custom_base_url", base_url.strip().rstrip("/"))
    set_session_value("llm_custom_api_key", api_key.strip())
    set_session_value("llm_custom_model", model.strip())
    set_session_value("llm_custom_health_path", health_path.strip() or "/v1/models")


def custom_provider_configured() -> bool:
    p = get_custom_provider()
    return bool(p.get("base_url") and p.get("model"))


def _openai_compatible_generate(
    prompt: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout_s: int = 60,
) -> tuple[str | None, str | None]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.0,
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
        if r.status_code != 200:
            return None, None
        data = r.json()
        choices = data.get("choices") or []
        if not choices:
            return None, None
        text = (choices[0].get("message") or {}).get("content", "").strip()
        return (text or None), model
    except Exception:
        return None, None


def llm_generate(
    prompt: str,
    model: str | None = None,
    timeout_s: int = 60,
) -> tuple[str | None, str | None]:
    """
    Route generation to the active per-session provider.
    Falls back to Ollama auto-probe when mode is `ollama`.
    """
    mode = get_provider_mode()
    if mode == "custom_api" and custom_provider_configured():
        p = get_custom_provider()
        return _openai_compatible_generate(
            prompt,
            base_url=p["base_url"],
            api_key=p["api_key"],
            model=model or p["model"],
            timeout_s=timeout_s,
        )
    if mode == "none":
        return None, None

    from mcp.services.llm_svc import ollama_generate

    return ollama_generate(prompt, model=model, timeout_s=timeout_s)


def provider_status() -> dict[str, Any]:
    mode = get_provider_mode()
    if mode == "custom_api" and custom_provider_configured():
        p = get_custom_provider()
        return {
            "mode": "custom_api",
            "label": p.get("name") or "Custom API",
            "model": p.get("model"),
            "url": p.get("base_url"),
            "configured": True,
        }
    from mcp.ollama_config import get_ollama_url, ollama_connection_status

    st = ollama_connection_status()
    return {
        "mode": "ollama",
        "label": "Ollama",
        "model": None,
        "url": get_user_ollama_url() or st.get("url"),
        "configured": st.get("reachable", False),
        "reachable": st.get("reachable", False),
    }
