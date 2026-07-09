import sys

from streamlit_app import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from streamlit_app.charts import (
    chart_readmission_by_age,
    chart_readmission_by_diagnosis,
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
    st.caption("Cohort filters are active — charts and high-risk tables stay in sync across dashboard pages.")

render_dashboard_kpis(filters)

c1, c2 = st.columns(2, gap="large")
with c1:
    chart_readmission_by_age(filters)
with c2:
    chart_readmission_by_gender(filters)

ctrl1, ctrl2 = st.columns([1.2, 1])
with ctrl1:
    if "dash_diag_top_n" not in st.session_state:
        st.session_state.dash_diag_top_n = 10
    top_n = st.slider(
        "Top diagnoses to show",
        min_value=5,
        max_value=15,
        value=st.session_state.dash_diag_top_n,
        key="dash_diag_top_n",
    )
with ctrl2:
    rank_by = st.radio(
        "Rank diagnoses by",
        ["Readmission rate", "Encounter volume"],
        horizontal=True,
        index=0,
        key="dash_diag_rank_by",
    )

chart_readmission_by_diagnosis(filters, top_n=top_n, rank_by=rank_by)

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
