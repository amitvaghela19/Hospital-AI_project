"""Per-user LLM provider settings (RBAC-gated, session-only)."""

from __future__ import annotations

import streamlit as st

from streamlit_app.llm_provider import (
    OLLAMA_NOTE,
    custom_provider_configured,
    get_custom_provider,
    get_provider_mode,
    get_user_ollama_url,
    provider_status,
    set_custom_provider,
    set_provider_mode,
    set_user_ollama_url,
)
from streamlit_app.rbac import can_manage_integrations
from streamlit_app.rbac_auth import validate_role
from streamlit_app.session_config import clear_llm_session, mask_secret


def render_llm_provider_panel(role: str) -> None:
    role = validate_role(role)
    if not can_manage_integrations(role):
        return

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Your LLM provider**")
    st.sidebar.caption(OLLAMA_NOTE)

    mode = st.sidebar.radio(
        "LLM source",
        ["Ollama Desktop / local Ollama", "Custom API provider"],
        index=0 if get_provider_mode() != "custom_api" else 1,
        key="llm_source_radio",
    )
    set_provider_mode("custom_api" if "Custom" in mode else "ollama")

    if get_provider_mode() == "ollama":
        default_url = get_user_ollama_url() or "http://127.0.0.1:11434"
        url = st.sidebar.text_input(
            "Ollama URL (this machine or your tunnel)",
            value=default_url,
            key="llm_ollama_url_input",
            help="Leave as 127.0.0.1 when running the app locally with Ollama Desktop.",
        )
        if st.sidebar.button("Apply Ollama URL", key="llm_apply_ollama_url"):
            set_user_ollama_url(url)
            st.session_state.pop("_ollama_resolved_url", None)
            st.sidebar.success("Ollama URL saved for this session.")
    else:
        p = get_custom_provider()
        name = st.sidebar.text_input("Provider name", value=p.get("name", ""), key="llm_custom_name_input")
        base = st.sidebar.text_input("API base URL", value=p.get("base_url", ""), key="llm_custom_base_input")
        model = st.sidebar.text_input("Model name", value=p.get("model", ""), key="llm_custom_model_input")
        api_key = st.sidebar.text_input(
            "API key",
            value="",
            type="password",
            key="llm_custom_key_input",
            placeholder="Paste API key (session only, never saved to git)",
        )
        if custom_provider_configured() and not api_key:
            api_key = p.get("api_key", "")
        if st.sidebar.button("Save custom provider", key="llm_save_custom"):
            set_custom_provider(
                name=name,
                base_url=base,
                api_key=api_key,
                model=model,
            )
            st.sidebar.success("Custom provider saved for this session only.")

        if custom_provider_configured():
            st.sidebar.caption(f"Active: {name or 'Custom'} · model `{model}` · key {mask_secret(api_key)}")

    status = provider_status()
    if status.get("mode") == "custom_api" and custom_provider_configured():
        st.sidebar.info(f"LLM: custom API · {status.get('label')}")
    elif status.get("reachable"):
        st.sidebar.success("LLM: Ollama reachable")
    else:
        st.sidebar.warning("LLM: not connected — chat uses template fallback.")

    if st.sidebar.button("Clear my LLM settings", key="llm_clear_session"):
        clear_llm_session()
        st.session_state.pop("_ollama_resolved_url", None)
        st.sidebar.success("Cleared session LLM credentials.")
        st.rerun()
