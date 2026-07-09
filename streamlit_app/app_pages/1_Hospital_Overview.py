import sys

from streamlit_app import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from streamlit_app.charts import (
    chart_readmission_by_gender,
    chart_top_high_risk_encounters,
    render_dashboard_kpis,
)
from streamlit_app.components.dashboard_filters import cohort_filter_active
from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.page_registry import page_header_from_script
from streamlit_app.theme import inject_theme

inject_theme()
role, filters = render_sidebar()
page_header_from_script(__file__)

if cohort_filter_active(filters):
    st.caption("Cohort filters are active — KPIs and charts reflect the same slice on every dashboard page.")

render_dashboard_kpis(filters)

c1, c2 = st.columns([1.9, 1.1], gap="large")
with c1:
    chart_readmission_by_gender(filters)
with c2:
    st.markdown("#### Overview Notes")
    st.markdown(
        "- **Cohort filters** sync across Hospital Overview, Risk Analysis, Patient Behavior, and Model Insights "
        "(age, gender, diagnosis, readmit flag, LOS, visit/med bands, and **Risk band (model)**).\n"
        "- **Chart drill-down:** click or double-click bars and slices to toggle sidebar filters; "
        "use **Clear filters** to reset. Risk band filters the scored 30-day cohort (~7.5k encounters).\n"
        "- **RBAC:** Viewer = aggregate dashboards only; Clinician = clinical scoring + masked encounter IDs; "
        "Analyst/Admin = full IDs and ML Performance. Elevate via **Access control** in the sidebar.\n"
        "- **Risk Analysis** — diagnosis donuts and demographic breakdowns. "
        "**Model Insights** — feature importance and risk-band chart. "
        "**Grounded Chat** — plain-language readmission Q&A."
    )

st.divider()

if "dash_high_risk_top_n" not in st.session_state:
    st.session_state.dash_high_risk_top_n = 10
top_risk_n = st.slider(
    "Top high-risk encounters to show",
    min_value=1,
    max_value=20,
    value=st.session_state.dash_high_risk_top_n,
    key="dash_high_risk_top_n",
    help="Synced across Hospital Overview and Risk Analysis.",
)

chart_top_high_risk_encounters(role, filters, top_n=top_risk_n)

st.caption("Data: `data/exports/kpi_snapshot.json`, `mart_readmission.csv`, `mart_clinical_risk.csv`")
