import sys

from streamlit_app import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from streamlit_app.chat_artifacts import load_register
from streamlit_app.charts import (
    chart_actual_vs_predicted,
    chart_model_metrics_leaderboard,
    chart_model_precision_recall_landscape,
)
from streamlit_app.components.readonly_table import render_readonly_table
from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.data_loaders import load_experiments_matrix, load_kpi_snapshot
from streamlit_app.rbac import require_page_access
from streamlit_app.page_registry import page_header_from_script
from streamlit_app.theme import inject_theme

inject_theme()
role, _ = render_sidebar()
page_header_from_script(__file__)

if not require_page_access(role, "ml_performance"):
    st.stop()

kpi = load_kpi_snapshot()
register = load_register()
metrics = register.get("metrics", {})
_champion = register.get("champion_model", kpi.get("champion_model", "—"))
_horizon = register.get("horizon") or metrics.get("horizon") or "30d"
_split = register.get("split") or metrics.get("split") or "70/15/15"
_recall = metrics.get("recall", kpi.get("champion_recall", 0))
_roc = metrics.get("roc_auc", kpi.get("champion_roc_auc", 0))

if kpi or register:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Champion model", _champion)
    c2.metric("Horizon", _horizon)
    c3.metric("Recall", f"{100 * float(_recall):.1f}%")
    c4.metric("ROC AUC", f"{100 * float(_roc):.1f}%")

with st.expander("How to read these charts", expanded=False):
    st.markdown(
        f"ML Performance compares candidate models on the **same {_horizon} holdout** "
        f"({_split} split) used to certify **{_champion}** as champion.\n\n"
        "### Recall vs precision trade-off\n"
        "- Each dot is one trained model. **Up and right** means catching more readmissions "
        "(higher recall) with fewer false alarms (higher precision).\n"
        "- The **star** marks the deployed champion. We prioritized **recall** so fewer "
        "high-risk discharges are missed — precision is intentionally lower.\n"
        "- Models clustered lower-left trade recall for precision; upper-left models catch "
        "more events but flag more patients.\n\n"
        "### Model ranking\n"
        "- Side-by-side bars show **Recall** (teal/pink for champion) and **ROC AUC** "
        "(discrimination across all scores).\n"
        "- Recall drives champion selection; ROC AUC confirms the model separates risk "
        "better than chance (~50%).\n\n"
        "### Calibration curve\n"
        "- Standard **reliability diagram**: patients are grouped into 10 score deciles.\n"
        "- **X-axis** = average predicted readmission probability in each bin; **Y-axis** = "
        "actual readmission rate in that bin.\n"
        "- Points on the **dashed diagonal** mean perfect calibration; above the line = "
        "under-predicting risk, below = over-predicting.\n"
        "- The champion model is recall-tuned, so probabilities can sit above the diagonal "
        "at higher scores (more events observed than predicted)."
    )

left, right = st.columns(2)
with left:
    chart_model_precision_recall_landscape("30d")
with right:
    chart_model_metrics_leaderboard("30d")

chart_actual_vs_predicted()

st.subheader("Experiment matrix — top 10 by recall")
matrix = load_experiments_matrix()
if matrix.empty:
    st.info("experiments_matrix.csv not found.")
else:
    show_cols = [
        c
        for c in [
            "model",
            "horizon",
            "split",
            "recall",
            "roc_auc",
            "f1",
            "accuracy",
            "ensemble",
        ]
        if c in matrix.columns
    ]
    if not show_cols:
        show_cols = list(matrix.columns[:8])
    table = matrix.copy()
    if "recall" in table.columns:
        table = table.sort_values("recall", ascending=False).head(10)
    else:
        table = table.head(10)
    render_readonly_table(table[show_cols], show_caption=False)
