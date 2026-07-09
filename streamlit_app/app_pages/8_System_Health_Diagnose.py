import sys

from streamlit_app import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from streamlit_app.components.health_diagnose_advanced import render_advanced_health_diagnose
from streamlit_app.components.health_panel import render_health_panel
from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.rbac import can_diagnose_advanced, require_page_access
from streamlit_app.page_registry import page_header_from_script
from streamlit_app.theme import inject_theme

inject_theme()
role, _ = render_sidebar()
page_header_from_script(__file__)

if not require_page_access(role, "system_health_diagnose"):
    st.stop()

st.warning(
    "Analytics decision-support only — not a medical device; not for standalone clinical decisions."
)

render_health_panel(show_bootstrap=True, role=role)

if can_diagnose_advanced(role):
    st.divider()
    render_advanced_health_diagnose()
else:
    st.divider()
    st.info(
        "Unlock **Clinician** or **Analyst** mode in the sidebar to access advanced diagnostics: "
        "LLM model switching, n8n/CrewAI/API integrations, and full failure breakdown tests."
    )

st.caption(
    "Viewer: summary health and bootstrap actions. "
    "Clinician/Analyst: model control, integration probes, and downloadable diagnostic reports."
)
