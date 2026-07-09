"""Advanced system health diagnostics for Clinician and Analyst roles."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from mcp.services import http_svc
from streamlit_app.artifacts import load_register
from streamlit_app.components.readonly_table import render_readonly_table
from streamlit_app.diagnostics import (
    DiagnosticCheck,
    diagnostics_summary,
    export_diagnostics_json,
    run_full_diagnostics,
)
from streamlit_app.llm_provider import OLLAMA_NOTE
from streamlit_app.runtime_config import (
    get_integrations,
    get_ollama_fallback,
    get_ollama_primary,
    set_ollama_models,
    update_integrations,
)
from streamlit_app.session_config import mask_secret
from streamlit_app.theme import status_badge


def _sync_runtime_from_session() -> None:
    primary = st.session_state.get("diag_ollama_primary")
    fallback = st.session_state.get("diag_ollama_fallback")
    if primary and fallback:
        set_ollama_models(primary, fallback)


def render_model_switcher() -> None:
    st.markdown("#### LLM model control")
    health = http_svc.ollama_health()
    installed = health.get("models") or []
    if health.get("status") != "ok":
        st.warning(f"Ollama unreachable: {health.get('error', health.get('status'))}")
        installed = []

    default_primary = get_ollama_primary()
    default_fallback = get_ollama_fallback()
    if "diag_ollama_primary" not in st.session_state:
        st.session_state.diag_ollama_primary = default_primary
    if "diag_ollama_fallback" not in st.session_state:
        st.session_state.diag_ollama_fallback = default_fallback

    options = installed or [default_primary, default_fallback]
    options = list(dict.fromkeys(options + [default_primary, default_fallback]))

    c1, c2 = st.columns(2)
    with c1:
        primary = st.selectbox("Primary Ollama model", options, key="diag_ollama_primary")
    with c2:
        fallback = st.selectbox("Fallback Ollama model", options, key="diag_ollama_fallback")

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Apply model selection", type="primary", use_container_width=True):
            set_ollama_models(primary, fallback)
            st.success(f"Active: primary `{primary}`, fallback `{fallback}`")
    with b2:
        if st.button("Test primary model", use_container_width=True):
            _sync_runtime_from_session()
            with st.spinner("Probing model…"):
                text, model = http_svc.llm_generate(
                    "Reply with exactly: MODEL_OK",
                    model=primary,
                    timeout_s=30,
                )
            if text:
                st.success(f"**{model}** responded: {text[:200]}")
            else:
                st.error("No response from primary or fallback chain.")
    with b3:
        if st.button("Reset to environment defaults", use_container_width=True):
            from streamlit_app.runtime_config import reset_ollama_models

            reset_ollama_models()
            default_p = get_ollama_primary()
            default_f = get_ollama_fallback()
            st.session_state.diag_ollama_primary = default_p
            st.session_state.diag_ollama_fallback = default_f
            st.info("Restored default models for this session.")

    reg = load_register()
    st.caption(
        f"Served ML champion: **{reg.get('champion_model', '—')}** · "
        f"Reference: **{reg.get('reference_model', '—')}** · "
        f"Threshold: **{reg.get('threshold', '—')}**"
    )


def render_integrations_panel() -> None:
    st.markdown("#### External providers & automation")
    st.caption(
        "Connect n8n workflows, CrewAI agents, or any OpenAI-compatible API. "
        "Credentials are kept in this browser session only."
    )

    integrations = get_integrations()
    n8n_default = integrations.get("n8n_webhook_url", "")
    crew_base_default = integrations.get("crewai_base_url", "")
    crew_key_default = integrations.get("crewai_api_key", "")

    with st.expander("n8n workflow webhook", expanded=bool(n8n_default)):
        n8n_url = st.text_input(
            "n8n webhook URL",
            value=n8n_default,
            placeholder="https://your-n8n.example.com/webhook/hospital-health",
            key="diag_n8n_url",
        )
        if st.button("Save n8n webhook", key="save_n8n"):
            update_integrations(n8n_webhook_url=n8n_url.strip())
            st.success("n8n webhook saved for this session.")

    with st.expander("CrewAI", expanded=bool(crew_base_default)):
        crew_base = st.text_input(
            "CrewAI base URL",
            value=crew_base_default,
            placeholder="http://localhost:8000",
            key="diag_crew_base",
        )
        crew_key = st.text_input(
            "CrewAI API key (optional)",
            value=crew_key_default,
            type="password",
            key="diag_crew_key",
        )
        if st.button("Save CrewAI settings", key="save_crew"):
            update_integrations(
                crewai_base_url=crew_base.strip(),
                crewai_api_key=crew_key.strip(),
            )
            st.success("CrewAI settings saved for this session.")

    with st.expander("Custom LLM provider (chat & phrasing)", expanded=False):
        st.caption(OLLAMA_NOTE)
        st.info(
            "Configure your custom OpenAI-compatible provider in the **sidebar → Your LLM provider** panel. "
            "Credentials stay in this browser session only."
        )

    providers = integrations.get("custom_providers") or []
    if providers:
        st.markdown("**Legacy custom providers (this session)**")
        display = [{**p, "api_key": mask_secret(p.get("api_key"))} for p in providers]
        render_readonly_table(pd.DataFrame(display), show_caption=False)


def render_diagnostic_breakdown() -> None:
    st.markdown("#### Full diagnostic breakdown")
    if st.button("Run full diagnostic suite", type="primary"):
        with st.spinner("Running structured health checks…"):
            checks = run_full_diagnostics()
        st.session_state["last_diagnostic_checks"] = [c.to_dict() for c in checks]

    raw = st.session_state.get("last_diagnostic_checks")
    if not raw:
        st.info("Run the diagnostic suite to see per-component status, failure reasons, and remediation steps.")
        return

    checks = [DiagnosticCheck(**d) for d in raw]
    summary = diagnostics_summary(checks)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Passed", summary.get("ok", 0))
    m2.metric("Warnings", summary.get("warn", 0))
    m3.metric("Failed", summary.get("fail", 0))
    m4.metric("Skipped", summary.get("skip", 0))

    by_category: dict[str, list[DiagnosticCheck]] = {}
    for c in checks:
        by_category.setdefault(c.category, []).append(c)

    for category, items in by_category.items():
        with st.expander(f"{category} ({len(items)} checks)", expanded=any(i.status == "fail" for i in items)):
            for item in items:
                ok = item.status == "ok"
                status_badge(ok, item.name, item.summary)
                if item.status != "ok":
                    st.markdown(f"**Reason:** {item.reason}")
                    st.markdown(f"**Remediation:** {item.remediation}")
                if item.evidence:
                    st.caption(item.evidence)
                if item.duration_ms:
                    st.caption(f"Duration: {item.duration_ms} ms")

    st.download_button(
        "Download diagnostic report (JSON)",
        data=export_diagnostics_json(checks),
        file_name="system_health_diagnose.json",
        mime="application/json",
        use_container_width=True,
    )


def render_advanced_health_diagnose() -> None:
    st.markdown("### Advanced diagnostics (Clinician / Analyst)")
    st.caption(
        "Model switching, integration testing, and component-level failure analysis. "
        "Viewer access shows summary health only."
    )
    tab_models, tab_integrations, tab_breakdown = st.tabs(
        ["Models", "Integrations", "Diagnostic breakdown"]
    )
    with tab_models:
        render_model_switcher()
    with tab_integrations:
        render_integrations_panel()
    with tab_breakdown:
        render_diagnostic_breakdown()
