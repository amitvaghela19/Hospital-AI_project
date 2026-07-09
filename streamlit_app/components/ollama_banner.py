"""Ollama connectivity banner for local vs Streamlit Cloud deployments."""

from __future__ import annotations

import streamlit as st

from mcp.ollama_config import deployment_guidance, is_streamlit_cloud, ollama_connection_status, resolve_ollama_url
from streamlit_app.llm_provider import OLLAMA_NOTE, custom_provider_configured, get_provider_mode, provider_status


def render_ollama_banner(*, compact: bool = False) -> None:
    """Show LLM connectivity once per session; respects custom API provider mode."""
    mode = get_provider_mode()

    if mode == "custom_api":
        if custom_provider_configured():
            status = provider_status()
            st.sidebar.info(
                f"LLM: **{status.get('label', 'Custom API')}** · model `{status.get('model', '—')}`"
            )
            if not compact:
                st.sidebar.caption(OLLAMA_NOTE)
            return
        st.sidebar.warning("Custom API selected but not fully configured — add base URL and model in the sidebar.")
        if not compact:
            st.sidebar.caption(OLLAMA_NOTE)
        return

    resolve_ollama_url()
    status = ollama_connection_status()

    if st.session_state.get("_ollama_banner_dismissed") and compact:
        return

    if status["reachable"]:
        models = []
        try:
            from mcp.services import http_svc

            health = http_svc.ollama_health()
            models = (health.get("models") or [])[:3]
        except Exception:
            pass
        model_hint = f" Models: {', '.join(models)}" if models else ""
        st.sidebar.success(f"Ollama connected at `{status['url']}`{model_hint}")
        if not compact:
            st.sidebar.caption(OLLAMA_NOTE)
        return

    if is_streamlit_cloud():
        st.sidebar.warning("Ollama not reachable from Streamlit Cloud.")
        if not compact:
            with st.sidebar.expander("How to enable LLM on cloud deploy", expanded=False):
                st.markdown(deployment_guidance())
                st.caption(OLLAMA_NOTE)
    else:
        st.sidebar.warning("Ollama not detected — start **Ollama Desktop** on this PC (only if not using a custom API).")
        if not compact:
            with st.sidebar.expander("Local Ollama setup", expanded=False):
                st.markdown(deployment_guidance())
                st.caption(OLLAMA_NOTE)
                st.code("ollama pull deepseek-r1\nollama pull llama3", language="bash")
        if st.sidebar.button("Retry Ollama connection", key="ollama_retry_probe"):
            st.session_state.pop("_ollama_resolved_url", None)
            resolve_ollama_url()
            st.rerun()
