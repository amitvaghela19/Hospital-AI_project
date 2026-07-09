import sys

from streamlit_app import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from streamlit_app.charts import (
    chart_medication_pattern_rate,
    chart_medication_patterns,
    chart_visit_frequency,
    chart_visit_frequency_rate,
    render_dashboard_kpis,
)
from streamlit_app.components.dashboard_filters import cohort_filter_active
from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.page_registry import page_header_from_script
from streamlit_app.theme import inject_theme

inject_theme()
_, filters = render_sidebar()
page_header_from_script(__file__)

if cohort_filter_active(filters):
    st.caption("Cohort filters are active — behavior charts use the same filtered cohort.")

render_dashboard_kpis(filters)

c1, c2 = st.columns(2)
with c1:
    chart_visit_frequency_rate(filters)
with c2:
    chart_medication_pattern_rate(filters)

c3, c4 = st.columns(2)
with c3:
    chart_visit_frequency(filters)
with c4:
    chart_medication_patterns(filters)
