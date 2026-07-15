import sys

from streamlit_app import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from streamlit_app.charts import (
    chart_feature_importance,
    chart_prediction_distribution,
    chart_risk_band_distribution,
    render_dashboard_kpis,
)
from streamlit_app.components.dashboard_filters import cohort_filter_active
from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.chat_artifacts import load_register
from streamlit_app.data_loaders import load_model_card
from streamlit_app.rbac import require_page_access
from streamlit_app.page_registry import page_header_from_script
from streamlit_app.theme import inject_theme

inject_theme()
role, filters = render_sidebar()
page_header_from_script(__file__)

if not require_page_access(role, "model_insights"):
    st.stop()

render_dashboard_kpis(filters)

filters_active = cohort_filter_active(filters)
if filters_active:
    st.caption(
        "Cohort filters are applied to 'Risk band distribution'. "
        "Feature importance and prediction distribution are global model chat_artifacts "
        "(not recalculated per cohort filter)."
    )

chart_feature_importance()
chart_prediction_distribution()
chart_risk_band_distribution(filters)

reg = load_register()
_champion = reg.get("champion_model") or reg.get("served_primary_model") or "champion"
_horizon = reg.get("horizon") or reg.get("metrics", {}).get("horizon") or "30d"
_threshold = reg.get("threshold")
if _threshold is None:
    _threshold = reg.get("metrics", {}).get("threshold", 0.45)
try:
    _threshold_fmt = f"{float(_threshold):.2f}"
except (TypeError, ValueError):
    _threshold_fmt = "0.45"
_explain = reg.get("explainability_source", "")

with st.expander("How to read these charts", expanded=False):
    st.markdown(
        f"Model Insights summarizes how the **served primary model** behaves on the certified "
        f"readmission cohort. These charts support operational review only — they are **not** "
        f"clinical directives.\n\n"
        f"**Current primary model:** {_champion} ({_horizon} horizon, recall-first threshold "
        f"**{_threshold_fmt}**).\n\n"
        "### Feature importance (SHAP)\n"
        "- Bars show **mean absolute SHAP** — how strongly each feature pushes 30-day readmission "
        "risk scores up or down on average.\n"
        "- A longer bar means a **larger typical influence** on the model output, not necessarily "
        "a causal clinical effect.\n"
        "- Common top drivers in this project include **prior inpatient visits**, "
        "**discharge disposition**, and **total visits**.\n"
        "- Sourced from global model chat_artifacts (`CHART_FEATURE` / champion register); "
        "**not recalculated** when sidebar cohort filters change.\n"
        + (
            f"- When a shadow ensemble is served, importance may still reflect the "
            f"**{_explain}** explainability path.\n"
            if _explain
            else ""
        )
        + "\n### Prediction score distribution\n"
        "- Histogram of **predicted probability (`y_prob`)** across scored encounters, "
        "grouped in **0.1-wide bins** (e.g. 0.3–0.4).\n"
        "- A **flat** shape means scores are spread across the cohort; a **tall peak** means "
        "many encounters cluster in one probability range.\n"
        f"- Compare mass **below vs above {_threshold_fmt}** (champion threshold) to see how many "
        "encounters sit near the readmission decision boundary.\n"
        "- Global artifact — sidebar filters **do not** re-bin this chart.\n\n"
        "### Risk band distribution\n"
        "- Counts encounters in operational triage bands: **Low** (<0.33), **Medium** (0.33–0.66), "
        "and **High** (>0.66) on predicted probability.\n"
        "- Use this to estimate **triage load** — e.g. how many High-band encounters may need "
        "follow-up outreach or care-management resources.\n"
        "- **Responds to sidebar cohort filters** (age, gender, risk band, etc.). "
        "Click a bar to apply that band in the sidebar drill-down.\n"
        "- Triage bands prioritize review; they are **distinct** from the binary readmission "
        f"threshold ({_threshold_fmt}) used for recall-first classification."
    )

st.divider()
card = load_model_card()
with st.expander("Model card & fairness summary"):
    if card:
        st.json(card)
    else:
        st.json({
            "champion": reg.get("champion_model"),
            "metrics": reg.get("metrics"),
            "fairness_sample": reg.get("fairness", [])[:4],
        })
