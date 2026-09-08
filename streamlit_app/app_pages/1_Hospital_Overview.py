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
    st.markdown("#### What the numbers say")
    st.markdown(
        "- About **1 in 9** diabetic inpatient stays come back within 30 days "
        "(**~11.2%** overall; average stay **~4.4** days).\n"
        "- **Prior hospital use is the strongest signal.** Patients with two or more "
        "prior inpatient stays return at **~38%**, versus **~8%** with no prior stays.\n"
        "- A small high-utilization group carries outsized load: roughly **2%** of patients "
        "account for nearly **19%** of 30-day readmissions.\n"
        "- Risk rises with longer stays (**~9%** for 1–2 days vs **~16%** when stay exceeds 10 days) "
        "and concentrates in units such as **Nephrology (~25%)** and **Cardiology (~15%)**.\n"
        "- Older adults (roughly ages **70–90**) sit above the baseline; younger cohorts "
        "(about **20–40**) stay well below **~7.5%**. Discharge destination and comorbidity "
        "burden also matter when planning follow-up."
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
