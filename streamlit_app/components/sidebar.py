from __future__ import annotations

import streamlit as st

from mcp.client.pool import pool
from streamlit_app.chat_artifacts import load_register
from streamlit_app.components.dashboard_filters import (
    cohort_filter_active,
    render_dashboard_filters,
)
from streamlit_app.components.llm_provider_panel import render_llm_provider_panel
from streamlit_app.components.ollama_banner import render_ollama_banner
from streamlit_app.rbac import capability_rows, get_role_config, can_manage_integrations, can_switch_llm
from streamlit_app.rbac_auth import (
    authenticate_elevation,
    downgrade_to_clinician,
    get_effective_role,
    lock_to_viewer,
)

from streamlit_app.runtime_config import get_ollama_fallback, get_ollama_primary


def _do_lock_viewer() -> None:
    lock_to_viewer()


def _do_unlock() -> None:
    mode = st.session_state.get("rbac_unlock_target", "Clinician")
    target = "clinician" if mode == "Clinician" else "analyst"
    password = st.session_state.get("rbac_unlock_password", "")
    ok, message = authenticate_elevation(target, password)
    st.session_state["rbac_flash"] = ("success" if ok else "error", message)
    if ok:
        st.session_state.pop("rbac_unlock_password", None)


def _do_switch_analyst() -> None:
    password = st.session_state.get("rbac_switch_analyst_pwd", "")
    ok, message = authenticate_elevation("analyst", password)
    st.session_state["rbac_flash"] = ("success" if ok else "error", message)
    if ok:
        st.session_state.pop("rbac_switch_analyst_pwd", None)


def _do_switch_clinician() -> None:
    ok, message = downgrade_to_clinician()
    st.session_state["rbac_flash"] = ("success" if ok else "error", message)


def _render_access_controls() -> str:
    """Password-gated elevation; returns verified effective role."""
    st.session_state.pop("rbac_role", None)

    role = get_effective_role()
    cfg = get_role_config(role)

    flash = st.session_state.pop("rbac_flash", None)
    if flash:
        level, message = flash
        if level == "success":
            st.sidebar.success(message)
        else:
            st.sidebar.error(message)

    st.sidebar.markdown("### Access control")

    if role == "viewer":
        st.sidebar.markdown("**Current access:** Viewer (default)")
        st.sidebar.caption("Aggregate dashboards only. Elevated modes require a password.")
        with st.sidebar.expander("Unlock Clinician or Analyst mode", expanded=False):
            st.radio(
                "Elevate to",
                ["Clinician", "Analyst"],
                horizontal=True,
                key="rbac_unlock_target",
            )
            st.text_input(
                "Password",
                type="password",
                key="rbac_unlock_password",
                help="Contact your deployment administrator for elevated access passwords.",
            )
            st.button(
                "Unlock access",
                type="primary",
                use_container_width=True,
                key="rbac_unlock_btn",
                on_click=_do_unlock,
            )
    else:
        st.sidebar.success(f"**Active mode:** {cfg.get('label', role)}")
        st.sidebar.caption(cfg.get("summary", ""))

        st.button(
            "Return to Viewer",
            use_container_width=True,
            key="rbac_lock_viewer",
            on_click=_do_lock_viewer,
            help="No password required.",
        )

        if role == "clinician":
            with st.sidebar.expander("Switch to Analyst mode", expanded=False):
                st.caption("Analyst password required (SQL, ML Performance, full patient IDs).")
                st.text_input(
                    "Analyst password",
                    type="password",
                    key="rbac_switch_analyst_pwd",
                )
                st.button(
                    "Activate Analyst mode",
                    use_container_width=True,
                    key="rbac_switch_analyst_btn",
                    on_click=_do_switch_analyst,
                )
        elif role == "analyst":
            with st.sidebar.expander("Switch to Clinician mode", expanded=False):
                st.caption("Downgrade to clinician view (limited IDs). No password required.")
                st.button(
                    "Switch to Clinician mode",
                    use_container_width=True,
                    key="rbac_switch_clinician_btn",
                    on_click=_do_switch_clinician,
                )

    return get_effective_role()


def render_sidebar(show_dashboard_filters: bool = True):
    filters = None
    if show_dashboard_filters:
        filters = render_dashboard_filters()
        if get_effective_role() == "viewer":
            st.sidebar.caption("Viewer: aggregate filters only — no encounter/patient IDs.")

    st.sidebar.title("Readmission Analytics")
    st.sidebar.caption("Analytics decision-support only — not a medical device.")

    role = _render_access_controls()

    with st.sidebar.expander("Capability matrix", expanded=False):
        for name, status in capability_rows(role):
            mark = "OK" if status.startswith("allowed") or status.startswith("limited") else "NO"
            st.markdown(f"**{name}:** {status} ({mark})")

    render_llm_provider_panel(role)

    register = load_register()
    st.sidebar.markdown("---")
    if can_manage_integrations(role):
        st.sidebar.write("**Champion:**", register.get("champion_model", "—"))
        st.sidebar.write("**Threshold:**", f"{register.get('threshold', 0):.3f}")
        if can_switch_llm(role):
            st.sidebar.write("**Ollama:**", get_ollama_primary(), "|", get_ollama_fallback())

        health = pool.health_summary()
        redis_on = "on" if health.get("redis") else "off"
        chroma = "ok" if health.get("vectordb") else "missing"
        ollama_st = health.get("ollama", {}).get("status", "?")
        st.sidebar.caption(f"MCP: Redis={redis_on} | Chroma={chroma} | Ollama={ollama_st}")

        render_ollama_banner(compact=True)
    else:
        st.sidebar.caption(
            "Model and infrastructure details are hidden in Viewer mode. Unlock **Clinician** or "
            "**Analyst** to configure LLM providers and view service status."
        )

    if not show_dashboard_filters:
        from streamlit_app.components.dashboard_filters import get_dashboard_filters_from_session

        filters = get_dashboard_filters_from_session()
        if cohort_filter_active(filters):
            st.sidebar.caption("Cohort filters active (synced from dashboard pages).")

    return role, filters
