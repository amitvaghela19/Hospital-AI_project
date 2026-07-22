from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from streamlit_app.chat_artifacts import load_register
from streamlit_app.components.readonly_table import render_readonly_table
from streamlit_app.components.chart_drilldown import (
    attach_pie_diag_customdata,
    chart_uirevision,
    med_count_to_band,
    process_chart_selection_event,
    render_high_risk_drilldown_card,
    render_interactive_plotly,
    render_reset_cohort_control,
)
from streamlit_app.components.dashboard_filters import apply_dashboard_filters, cohort_filter_active
from streamlit_app.data_loaders import filter_master, load_kpi_snapshot, load_mart
from streamlit_app.chart_theme import (
    CHART_PALETTE,
    _RATE_HOVER_H,
    _RATE_HOVER_V,
    apply_count_bar_trace,
    apply_donut_right_legend_layout,
    apply_min_bar_display,
    apply_multitrace_legend_below,
    apply_full_width_chart_layout,
    apply_single_trace_bar_colors,
    assign_bar_customdata,
    assign_multitrace_bar_customdata,
    base_plotly_layout,
    enhance_figure,
    palette_for,
    rate_bar_text_labels,
    render_plotly_chart,
)
from streamlit_app.gender_labels import (
    GENDER_CHART_ORDER,
    GENDER_CHART_Y_ORDER,
    normalize_gender_display,
    prepare_gender_readmit_stats,
)
from streamlit_app.risk_labels import normalize_risk_band_display
from streamlit_app.rbac import ids_policy, validate_role
from streamlit_app.theme import COLORS

def _clinical_risk_cohort(filters: dict | None = None) -> pd.DataFrame:
    """Filter mart_clinical_risk to the same cohort as mart_readmission filters."""
    cr = load_mart("mart_clinical_risk")
    if cr.empty:
        return cr
    if "horizon" in cr.columns:
        sub = cr[cr["horizon"].astype(str).str.lower() == "30d"]
        if not sub.empty:
            cr = sub
    rm = load_mart("mart_readmission")
    if rm.empty or "encounter_id" not in cr.columns:
        return cr
    rm = apply_dashboard_filters(rm, filters or {})
    if filters and cohort_filter_active(filters):
        cr = cr[cr["encounter_id"].isin(rm["encounter_id"])]
    return cr


def _plotly_layout(**kwargs) -> dict:
    return base_plotly_layout(**kwargs)


def _bar(fig_df, x, y, title, horizontal=False, color_col=None, text=None):
    if horizontal:
        fig = px.bar(
            fig_df,
            x=x,
            y=y,
            orientation="h",
            title=title,
            text=text,
        )
    else:
        fig = px.bar(
            fig_df,
            x=x,
            y=y,
            title=title,
            text=text,
        )
    apply_single_trace_bar_colors(fig, len(fig_df))
    fig.update_layout(**_plotly_layout())
    return fig


def _px_bar_single(fig_df, *, horizontal: bool = False, **px_kwargs):
    """px.bar without color= grouping — one trace, multicolor via chart_theme."""
    if horizontal:
        fig = px.bar(fig_df, orientation="h", **px_kwargs)
    else:
        fig = px.bar(fig_df, **px_kwargs)
    apply_single_trace_bar_colors(fig, len(fig_df))
    fig.update_layout(**_plotly_layout())
    return fig


def _apply_rate_bar_trace(
    fig,
    sub: pd.DataFrame,
    *,
    horizontal: bool,
    text_col: str = "display_rate",
) -> None:
    rows = sub[["bar_count", "true_rate"]].values.tolist()
    assign_bar_customdata(fig, rows)
    texts = rate_bar_text_labels(sub)
    fig.update_traces(
        hovertemplate=_RATE_HOVER_H if horizontal else _RATE_HOVER_V,
        text=texts,
        texttemplate="%{text}",
    )


def render_kpi_row() -> None:
    kpi = load_kpi_snapshot()
    if not kpi:
        st.warning("KPI snapshot missing. Run Phase 4 exports.")
        return
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total patients", f"{kpi.get('total_patients', 0):,}")
    with c2:
        st.metric("Readmission rate (30d)", f"{100 * kpi.get('readmission_rate_30d', 0):.1f}%")
    with c3:
        st.metric("Avg length of stay", f"{kpi.get('avg_los', 0):.1f} days")
    with c4:
        st.metric("High-risk rate", f"{100 * kpi.get('high_risk_rate', 0):.1f}%")


def render_dashboard_kpis(filters: dict[str, list[str]] | None = None) -> None:
    mart = load_mart("mart_readmission")
    if mart.empty:
        render_kpi_row()
        return
    if filters:
        mart = apply_dashboard_filters(mart, filters)
    if mart.empty:
        st.warning("No rows match the current filters.")
        return
    patients = mart["patient_nbr"].nunique() if "patient_nbr" in mart.columns else len(mart)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total patients", f"{patients:,}")
    c2.metric("Total encounters", f"{len(mart):,}")
    c3.metric("Readmission rate", f"{100 * mart['readmit_30d'].mean():.1f}%")
    c4.metric("Avg length of stay", f"{mart['time_in_hospital'].mean():.1f}")


def chart_readmit_by_dimension(dimension: str, title: str) -> None:
    record_map = {
        "age": "CHART_AGE",
        "gender": "CHART_GENDER",
        "diagnosis": "CHART_DIAG",
    }
    record_type = record_map.get(dimension, "CHART_DIAG")
    df = filter_master(record_type)
    if df.empty:
        st.info(f"{record_type} rows not found in master CSV.")
        return
    sub = df.copy()
    sub = sub.dropna(subset=["chart_category"])
    if "chart_value" in sub.columns:
        sub["rate"] = pd.to_numeric(sub["chart_value"], errors="coerce") * 100
    elif "chart_rate_pct" in sub.columns:
        sub["rate"] = pd.to_numeric(
            sub["chart_rate_pct"].astype(str).str.replace("%", "", regex=False),
            errors="coerce",
        )
    else:
        st.info("Rate columns missing from chart export.")
        return
    sub = sub.dropna(subset=["rate"])
    if dimension == "gender":
        sub["chart_category"] = sub["chart_category"].map(normalize_gender_display)
        sub = (
            sub.groupby("chart_category", as_index=False)["rate"]
            .mean()
            .rename(columns={"chart_category": "gender"})
        )
        sub = sub.rename(columns={"gender": "chart_category"})
        present = [g for g in GENDER_CHART_ORDER if g in sub["chart_category"].astype(str).tolist()]
        sub["chart_category"] = pd.Categorical(sub["chart_category"], categories=present, ordered=True)
        sub = sub.sort_values("chart_category")
    else:
        sub = sub.sort_values("rate", ascending=False).head(12)
    fig = px.bar(
        sub,
        x="chart_category",
        y="rate",
        title=title,
    )
    apply_single_trace_bar_colors(fig, len(sub))
    fig.update_layout(**_plotly_layout(xaxis_title=dimension.title(), yaxis_title="Readmit %"))
    if dimension == "gender":
        present = [g for g in GENDER_CHART_Y_ORDER if g in sub["chart_category"].astype(str).tolist()]
        fig.update_layout(xaxis=dict(categoryorder="array", categoryarray=list(reversed(present))))
    render_plotly_chart(fig)


def chart_readmission_by_age(filters: dict[str, list[str]] | None = None) -> None:
    mart = load_mart("mart_readmission")
    if mart.empty:
        st.info("mart_readmission.csv not found.")
        return
    mart = apply_dashboard_filters(mart, filters or {})
    sub = mart.groupby("age", as_index=False).agg(
        readmit_30d=("readmit_30d", "mean"),
        count=("readmit_30d", "count"),
    )
    sub["rate"] = sub["readmit_30d"] * 100
    sub = apply_min_bar_display(sub, "rate", "count")
    fig = _bar(sub, "display_rate", "age", "Readmission by age", horizontal=True)
    _apply_rate_bar_trace(fig, sub, horizontal=True)
    fig.update_layout(xaxis_title="Rate %", yaxis_title="")
    render_interactive_plotly(
        fig,
        chart_id="readmit_age",
        chart_title="Readmission by age",
        dimension="age",
        value_fn=lambda pt: str(pt.get("y") or pt.get("label") or ""),
    )


def chart_readmission_by_gender(filters: dict[str, list[str]] | None = None) -> None:
    mart = load_mart("mart_readmission")
    if mart.empty:
        st.info("mart_readmission.csv not found.")
        return
    mart = apply_dashboard_filters(mart, filters or {})
    sub = prepare_gender_readmit_stats(mart)
    if sub.empty:
        st.info("No gender rows available for the selected cohort.")
        return
    sub = apply_min_bar_display(sub, "rate", "count")
    y_present = [g for g in GENDER_CHART_Y_ORDER if g in sub["gender"].astype(str).tolist()]
    sub = sub.set_index("gender").reindex(y_present).reset_index()
    fig = _bar(sub, "display_rate", "gender", "Readmission by gender", horizontal=True)
    _apply_rate_bar_trace(fig, sub, horizontal=True)
    fig.update_layout(
        xaxis_title="Rate %",
        yaxis_title="",
        yaxis=dict(categoryorder="array", categoryarray=y_present),
    )
    render_interactive_plotly(
        fig,
        chart_id="readmit_gender",
        chart_title="Readmission by gender",
        dimension="gender",
        value_fn=lambda pt: normalize_gender_display(str(pt.get("y") or pt.get("label") or "")),
    )


def chart_readmission_by_diagnosis(
    filters: dict[str, list[str]] | None = None,
    top_n: int = 10,
    rank_by: str = "Readmission rate",
) -> None:
    mart = load_mart("mart_readmission")
    if mart.empty:
        st.info("mart_readmission.csv not found.")
        return
    if "diag_1" not in mart.columns or "readmit_30d" not in mart.columns:
        st.info("Required diagnosis/readmission columns missing from mart_readmission.")
        return

    mart = apply_dashboard_filters(mart, filters or {})
    if mart.empty:
        st.info("No rows match the current filters.")
        return

    count_col = "encounter_id" if "encounter_id" in mart.columns else "readmit_30d"
    sub = mart.groupby("diag_1", as_index=False).agg(
        rate=("readmit_30d", "mean"),
        count=(count_col, "count"),
        readmit_count=("readmit_30d", "sum"),
    )
    sort_col = "rate" if rank_by == "Readmission rate" else "count"
    sub = sub.sort_values(sort_col, ascending=False).head(top_n)
    if sub.empty:
        st.info("No diagnosis rows available for the selected cohort.")
        return

    sub["rate_pct"] = sub["rate"] * 100
    value_col = "readmit_count" if rank_by == "Readmission rate" else "count"
    if sub[value_col].sum() <= 0:
        sub[value_col] = sub[value_col].clip(lower=1)

    display = sub.sort_values("rate_pct", ascending=False).reset_index(drop=True)
    display["diag_code"] = display["diag_1"].astype(str)

    title = (
        f"Readmission by diagnosis (top {top_n} by "
        f"{'readmission rate' if rank_by == 'Readmission rate' else 'encounter volume'})"
    )
    pie_title = (
        "Share of 30-day readmissions by diagnosis"
        if rank_by == "Readmission rate"
        else "Share of encounters by diagnosis"
    )

    fig = go.Figure(
        data=[
            go.Pie(
                labels=display["diag_code"],
                values=display[value_col],
                hole=0.44,
                sort=False,
                marker=dict(colors=CHART_PALETTE[: len(display)], line=dict(color="rgba(11, 20, 38, 0.85)", width=1.5)),
                textinfo="percent",
                textposition="inside",
                insidetextorientation="radial",
                hovertemplate=(
                    "<b>ICD-9: %{customdata}</b><br>"
                    "Share: %{percent}<br>"
                    "Value: %{value:,}<extra></extra>"
                ),
            )
        ]
    )
    fig.update_layout(**_plotly_layout(title=f"{title} — {pie_title}"))
    apply_donut_right_legend_layout(fig, height=580)
    fig = attach_pie_diag_customdata(fig, display["diag_code"].tolist())
    render_interactive_plotly(
        fig,
        chart_id="readmit_diag",
        chart_title="Readmission by diagnosis",
        dimension="diag_1",
        height=580,
        value_fn=lambda pt: (
            str((pt.get("customdata") or [None])[0])
            if pt.get("customdata") is not None
            else str(pt.get("label", "")).strip()
        ),
    )

    display_sort = "rate_pct" if rank_by == "Readmission rate" else "count"
    table = sub[["diag_1", "count", "readmit_count", "rate_pct"]].copy()
    table = table.sort_values(display_sort, ascending=False)
    table.columns = ["Diagnosis (ICD-9)", "Encounters", "30d readmits", "Readmit rate %"]
    table["Readmit rate %"] = table["Readmit rate %"].map(lambda v: f"{v:.1f}%")
    render_readonly_table(table)


def chart_top_high_risk_encounters(
    role: str,
    filters: dict[str, list[str]] | None = None,
    top_n: int = 10,
) -> None:
    """Top-N encounters by model probability with RBAC-aware columns."""
    role = validate_role(role)
    can_ids, mask_patient = ids_policy(role)

    df = _clinical_risk_cohort(filters)
    if df.empty:
        st.info("mart_clinical_risk.csv not found or cohort is empty after filters.")
        return
    if "y_prob" not in df.columns:
        st.info("Risk scores not available in mart_clinical_risk.")
        return

    df = df.sort_values("y_prob", ascending=False).head(int(top_n))
    if df.empty:
        st.info("No encounters match the current filters.")
        return

    st.markdown(f"#### Top {len(df)} highest-risk encounters (model probability)")
    if not can_ids:
        st.caption(
            "Viewer mode: anonymized ranking — unlock Clinician or Analyst for encounter identifiers."
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg probability", f"{df['y_prob'].mean() * 100:.1f}%")
    c2.metric("Max probability", f"{df['y_prob'].max() * 100:.1f}%")
    high_n = 0
    if "risk_band" in df.columns:
        high_n = int((df["risk_band"].astype(str).str.lower() == "high").sum())
    c3.metric("High band", f"{high_n}")
    cohort_n = len(_clinical_risk_cohort(filters))
    c4.metric("Cohort size (filtered)", f"{cohort_n:,}")

    plot_df = df.copy()
    plot_df["rank"] = range(1, len(plot_df) + 1)
    plot_df["prob_pct"] = plot_df["y_prob"] * 100
    plot_df["rank_label"] = plot_df["rank"].map(lambda i: f"Rank {i}")
    x_col = "rank_label"

    color_col = "risk_band" if "risk_band" in plot_df.columns else None
    fig = px.bar(
        plot_df,
        x=x_col,
        y="prob_pct",
        color=color_col,
        title="Readmission risk score (top encounters)",
        labels={"prob_pct": "Probability %", "rank_label": "Rank"},
        color_discrete_sequence=CHART_PALETTE,
    )
    hover_cols = [c for c in ("encounter_id", "gender", "age", "risk_band") if c in plot_df.columns]
    if not can_ids:
        hover_cols = [c for c in hover_cols if c != "encounter_id"]
    if hover_cols:
        assign_multitrace_bar_customdata(fig, plot_df, x_col=x_col, value_cols=hover_cols)
        fig.update_traces(
            hovertemplate="<b>%{x}</b><br>"
            + "<br>".join(f"{c}: %{{customdata[{i}]}}" for i, c in enumerate(hover_cols))
            + "<extra></extra>"
        )
    fig.update_layout(**_plotly_layout(xaxis_title="", yaxis_title="Readmission probability %"))
    apply_full_width_chart_layout(fig, height=460, n_categories=len(plot_df))
    if color_col:
        apply_multitrace_legend_below(fig, title="Risk band")
    fig.update_layout(uirevision=chart_uirevision("high_risk_encounters"))
    event = render_plotly_chart(
        fig,
        on_select="rerun",
        key="plotly_high_risk_encounters",
    )
    selection = getattr(event, "selection", None) if event is not None else None
    points = []
    if selection is not None:
        if hasattr(selection, "points"):
            points = list(selection.points or [])
        elif isinstance(selection, dict):
            points = list(selection.get("points") or [])
    process_chart_selection_event(
        "high_risk_encounters",
        points,
        on_select_points=lambda pts: render_high_risk_drilldown_card(
            pts[0],
            plot_df,
            can_ids=can_ids,
            mask_patient=mask_patient,
        ),
    )
    render_reset_cohort_control("high_risk_encounters")

    rows: list[dict] = []
    show_patient_id = can_ids and not mask_patient
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        row: dict = {"Rank": i}
        if can_ids:
            row["Encounter ID"] = int(r.get("encounter_id", 0) or 0)
        if show_patient_id and "patient_nbr" in r.index and pd.notna(r.get("patient_nbr")):
            row["Patient ID"] = int(r.get("patient_nbr"))
        row.update(
            {
                "Probability %": f"{float(r.get('y_prob', 0) or 0) * 100:.1f}%",
                "Risk band": str(r.get("risk_band", "") or "—"),
                "Age": str(r.get("age", "") or "—"),
                "Gender": str(r.get("gender", "") or "—"),
            }
        )
        if show_patient_id and "y_true" in r.index:
            row["Actual 30d readmit"] = "Yes" if int(r.get("y_true", 0) or 0) == 1 else "No"
        if can_ids and "model" in r.index:
            row["Model"] = str(r.get("model", "") or "—")
        rows.append(row)

    column_order = ["Rank"]
    if can_ids:
        column_order.append("Encounter ID")
    if show_patient_id:
        column_order.append("Patient ID")
    column_order.extend(["Probability %", "Risk band", "Age", "Gender"])
    if show_patient_id:
        column_order.append("Actual 30d readmit")
    if can_ids:
        column_order.append("Model")

    table = pd.DataFrame(rows)
    table = table[[c for c in column_order if c in table.columns]]
    render_readonly_table(table)

    if not can_ids:
        st.caption(
            "Encounter ID is not shown in Viewer mode — unlock **Clinician** or **Analyst** "
            "access in the sidebar to view encounter identifiers."
        )


def _visit_bucket(total_visits) -> str:
    """Bucket total visits into the same bands used by PowerBI exports."""
    try:
        v = float(total_visits) if total_visits is not None else 0.0
    except Exception:
        v = 0.0
    if v <= 0:
        return "0 visits"
    if v <= 2:
        return "1-2 visits"
    if v <= 5:
        return "3-5 visits"
    return "6+ visits"


def chart_visit_frequency(filters: dict[str, list[str]] | None = None) -> None:
    mart = load_mart("mart_readmission")
    if mart.empty:
        st.info("mart_readmission.csv not found.")
        return
    mart = apply_dashboard_filters(mart, filters or {})
    if "total_visits" not in mart.columns:
        st.info("total_visits column missing from mart_readmission.")
        return

    tmp = mart.copy()
    tmp["_bucket"] = tmp["total_visits"].apply(_visit_bucket)
    order = ["0 visits", "1-2 visits", "3-5 visits", "6+ visits"]
    vc = tmp["_bucket"].value_counts().reindex(order).fillna(0)
    sub = pd.DataFrame({"chart_category": vc.index.tolist(), "chart_count": vc.values.astype(int)})

    fig = _px_bar_single(
        sub,
        horizontal=True,
        x="chart_count",
        y="chart_category",
        title="Visit frequency distribution",
    )
    apply_count_bar_trace(fig, sub, "chart_count", horizontal=True)
    fig.update_layout(**_plotly_layout(xaxis_title="Encounters", yaxis_title=""))
    render_interactive_plotly(
        fig,
        chart_id="visit_freq_count",
        chart_title="Visit frequency distribution",
        dimension="visit_band",
        value_fn=lambda pt: str(pt.get("y") or pt.get("label") or ""),
    )


def chart_visit_frequency_rate(filters: dict[str, list[str]] | None = None) -> None:
    mart = load_mart("mart_readmission")
    if mart.empty:
        st.info("mart_readmission.csv not found.")
        return
    mart = apply_dashboard_filters(mart, filters or {})
    if "total_visits" not in mart.columns or "readmit_30d" not in mart.columns:
        st.info("Required columns missing from mart_readmission.")
        return

    tmp = mart.copy()
    tmp["_bucket"] = tmp["total_visits"].apply(_visit_bucket)
    order = ["0 visits", "1-2 visits", "3-5 visits", "6+ visits"]
    sub = tmp.groupby("_bucket", as_index=False).agg(
        rate=("readmit_30d", "mean"),
        count=("encounter_id", "count"),
    )
    # Force the band order and keep all bands.
    sub["_bucket"] = pd.Categorical(sub["_bucket"], categories=order, ordered=True)
    sub = sub.sort_values("_bucket")
    sub = sub.rename(columns={"_bucket": "chart_category"})
    sub["rate_pct"] = sub["rate"] * 100
    sub = apply_min_bar_display(sub, "rate_pct", "count")

    fig = _px_bar_single(
        sub,
        horizontal=True,
        x="display_rate",
        y="chart_category",
        title="Visit frequency (Readmission rate by band)",
    )
    _apply_rate_bar_trace(fig, sub, horizontal=True)
    fig.update_layout(xaxis_title="Readmission rate %", yaxis_title="")
    render_interactive_plotly(
        fig,
        chart_id="visit_freq_rate",
        chart_title="Visit frequency (readmission rate)",
        dimension="visit_band",
        value_fn=lambda pt: str(pt.get("y") or pt.get("label") or ""),
    )


def chart_medication_patterns(filters: dict[str, list[str]] | None = None) -> None:
    mart = load_mart("mart_readmission")
    if mart.empty:
        st.info("mart_readmission.csv not found.")
        return
    mart = apply_dashboard_filters(mart, filters or {})
    if "active_med_count" not in mart.columns:
        st.info("active_med_count column missing from mart_readmission.")
        return

    tmp = mart.copy()
    tmp["active_med_count"] = pd.to_numeric(tmp["active_med_count"], errors="coerce")
    tmp = tmp.dropna(subset=["active_med_count"])
    tmp["active_med_count"] = tmp["active_med_count"].astype(int)

    sub = (
        tmp.groupby("active_med_count", as_index=False)
        .agg(count=("encounter_id", "count"))
        .sort_values("count", ascending=False)
    )
    # Keep axis readable (there are only a few unique values, but cap for safety).
    sub = sub.head(12)

    fig = _px_bar_single(
        sub,
        x="active_med_count",
        y="count",
        title="Medication patterns (count of encounters)",
    )
    apply_count_bar_trace(fig, sub, "count", horizontal=False)
    fig.update_layout(**_plotly_layout(xaxis_title="Active meds (count)", yaxis_title="Encounters"))
    render_interactive_plotly(
        fig,
        chart_id="med_pattern_count",
        chart_title="Medication patterns (volume)",
        dimension="med_band",
        value_fn=lambda pt: med_count_to_band(pt.get("x") or pt.get("label") or 0),
    )


def chart_medication_pattern_rate(filters: dict[str, list[str]] | None = None) -> None:
    mart = load_mart("mart_readmission")
    if mart.empty:
        st.info("mart_readmission.csv not found.")
        return
    mart = apply_dashboard_filters(mart, filters or {})
    if "active_med_count" not in mart.columns or "readmit_30d" not in mart.columns:
        st.info("Required columns missing from mart_readmission.")
        return

    tmp = mart.copy()
    tmp["active_med_count"] = pd.to_numeric(tmp["active_med_count"], errors="coerce")
    tmp = tmp.dropna(subset=["active_med_count"])
    tmp["active_med_count"] = tmp["active_med_count"].astype(int)

    sub = (
        tmp.groupby("active_med_count", as_index=False)
        .agg(rate=("readmit_30d", "mean"), count=("encounter_id", "count"))
        .sort_values("active_med_count")
    )
    sub["rate_pct"] = sub["rate"] * 100
    sub = apply_min_bar_display(sub, "rate_pct", "count")

    fig = _px_bar_single(
        sub,
        horizontal=True,
        x="display_rate",
        y="active_med_count",
        title="Medication patterns (Readmission rate by active med count)",
    )
    _apply_rate_bar_trace(fig, sub, horizontal=True)
    fig.update_layout(xaxis_title="Readmission rate %", yaxis_title="Active med count")
    render_interactive_plotly(
        fig,
        chart_id="med_pattern_rate",
        chart_title="Medication patterns (readmission rate)",
        dimension="med_band",
        value_fn=lambda pt: med_count_to_band(pt.get("y") or pt.get("label") or 0),
    )


def chart_feature_importance() -> None:
    df = filter_master("CHART_FEATURE")
    if df.empty:
        reg_path = __import__("streamlit_app", fromlist=["ROOT"]).ROOT / "models" / "champion_register.json"
        if reg_path.exists():
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
            feats = reg.get("top_features", [])[:10]
            if feats:
                sub = pd.DataFrame(feats)
                sub["feature"] = sub["feature"].str.replace("num__", "", regex=False)
                fig = _px_bar_single(
                    sub,
                    horizontal=True,
                    x="mean_abs_shap",
                    y="feature",
                    title="Top feature importance (SHAP)",
                )
                apply_full_width_chart_layout(fig, horizontal=True, n_categories=len(sub))
                render_plotly_chart(fig)
                return
        st.info("Feature importance data not available.")
        return
    sub = df.dropna(subset=["chart_category", "chart_value"])
    sub = sub.sort_values("chart_value", ascending=True).tail(12)
    fig = _px_bar_single(
        sub,
        horizontal=True,
        x="chart_value",
        y="chart_category",
        title="Feature importance",
    )
    apply_full_width_chart_layout(fig, horizontal=True, n_categories=len(sub))
    render_plotly_chart(fig)


def chart_prediction_distribution() -> None:
    df = filter_master("CHART_PRED_BUCKET")
    if df.empty:
        st.info("CHART_PRED_BUCKET rows not found.")
        return
    sub = df.dropna(subset=["chart_category", "chart_count"])
    fig = _px_bar_single(
        sub,
        x="chart_category",
        y="chart_count",
        title="Prediction score distribution",
    )
    apply_full_width_chart_layout(fig, height=440, n_categories=len(sub))
    render_plotly_chart(fig)


def chart_risk_band_distribution(filters: dict[str, list[str]] | None = None) -> None:
    df = _clinical_risk_cohort(filters)
    if df.empty or "risk_band" not in df.columns:
        st.info("mart_clinical_risk.csv not found.")
        return
    df = df.copy()
    df["risk_band_display"] = df["risk_band"].map(normalize_risk_band_display)
    sub = df.groupby("risk_band_display", as_index=False).size()
    sub = sub.rename(columns={"risk_band_display": "risk_band"})
    fig = _bar(sub, "risk_band", "size", "Risk band distribution", text="size")
    fig.update_layout(xaxis_title="", yaxis_title="Encounters")
    apply_full_width_chart_layout(fig, height=440, n_categories=len(sub))
    render_interactive_plotly(
        fig,
        chart_id="risk_band_dist",
        chart_title="Risk band distribution",
        dimension="risk_band",
        value_fn=lambda pt: normalize_risk_band_display(str(pt.get("x") or pt.get("label") or "")),
    )


_MODEL_DISPLAY_NAMES = {
    "logreg": "Logistic Regression",
    "rf": "Random Forest",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",
    "rnn": "RNN",
    "gb_ensemble": "GB Ensemble",
    "tri_ensemble": "Tri Ensemble",
}


def _model_display_name(model: str) -> str:
    key = str(model or "").strip().lower()
    return _MODEL_DISPLAY_NAMES.get(key, key.replace("_", " ").title())


def _experiments_for_comparison(horizon: str = "30d") -> pd.DataFrame:
    """One row per model on the champion split (when available) for fair comparison."""
    matrix = load_mart("experiments_matrix")
    if matrix.empty:
        return matrix
    register = load_register()
    split = register.get("split") or register.get("metrics", {}).get("split")
    sub = matrix[matrix["horizon"].astype(str) == horizon].copy()
    if split and "split" in sub.columns:
        split_sub = sub[sub["split"].astype(str) == str(split)]
        if not split_sub.empty:
            sub = split_sub
    if "model" in sub.columns:
        sub = sub[sub["model"].astype(str) != "gb_ensemble"]
    if sub.empty:
        return sub
    sub = sub.sort_values("recall", ascending=False)
    sub["model_label"] = sub["model"].map(_model_display_name)
    return sub


def chart_model_precision_recall_landscape(horizon: str = "30d") -> None:
    """Model landscape: recall (y) vs precision (x); bubble size = ROC AUC; champion starred."""
    sub = _experiments_for_comparison(horizon)
    if sub.empty:
        st.info("experiments_matrix.csv not found.")
        return
    register = load_register()
    champion = str(register.get("champion_model", "catboost")).lower()
    sub = sub.copy()
    sub["precision_pct"] = pd.to_numeric(sub["precision"], errors="coerce") * 100
    sub["recall_pct"] = pd.to_numeric(sub["recall"], errors="coerce") * 100
    sub["roc_auc"] = pd.to_numeric(sub["roc_auc"], errors="coerce")
    if "f1" in sub.columns:
        sub["f1"] = pd.to_numeric(sub["f1"], errors="coerce")
    else:
        sub["f1"] = float("nan")
    sub = sub.dropna(subset=["precision_pct", "recall_pct", "roc_auc"])
    if sub.empty:
        st.info("No valid precision/recall rows for this horizon.")
        return

    sub["is_champion"] = sub["model"].astype(str).str.lower() == champion
    # Bubble size from ROC AUC (readable range ~14–28)
    auc_min = float(sub["roc_auc"].min())
    auc_max = float(sub["roc_auc"].max())
    auc_span = max(auc_max - auc_min, 1e-6)

    def _bubble_size(auc: float, *, champion_row: bool) -> float:
        scaled = 14 + 14 * ((float(auc) - auc_min) / auc_span)
        return scaled + 6 if champion_row else scaled

    colors = palette_for(len(sub))
    fig = go.Figure()

    # Soft “recall-first” band (upper half of the plot area)
    y0 = max(0.0, float(sub["recall_pct"].min()) - 6)
    y1 = min(100.0, float(sub["recall_pct"].max()) + 10)
    x0 = max(0.0, float(sub["precision_pct"].min()) - 2)
    x1 = float(sub["precision_pct"].max()) + 3
    recall_band = y0 + 0.55 * (y1 - y0)
    fig.add_hrect(
        y0=recall_band,
        y1=y1,
        fillcolor="rgba(45, 212, 191, 0.07)",
        line_width=0,
        layer="below",
    )
    fig.add_hline(
        y=float(sub["recall_pct"].median()),
        line_dash="dot",
        line_color="rgba(148, 163, 184, 0.45)",
        line_width=1,
        annotation_text="median recall",
        annotation_position="top left",
        annotation_font=dict(size=10, color=COLORS["muted"]),
    )
    fig.add_vline(
        x=float(sub["precision_pct"].median()),
        line_dash="dot",
        line_color="rgba(148, 163, 184, 0.45)",
        line_width=1,
        annotation_text="median precision",
        annotation_position="top right",
        annotation_font=dict(size=10, color=COLORS["muted"]),
    )

    # One colored marker per model (legend carries the name — no overlapping labels)
    for i, (_, row) in enumerate(sub.sort_values("recall_pct").iterrows()):
        is_champ = bool(row["is_champion"])
        label = str(row["model_label"])
        color = COLORS["tab_active"] if is_champ else colors[i % len(colors)]
        size = _bubble_size(float(row["roc_auc"]), champion_row=is_champ)
        f1_val = row["f1"]
        f1_txt = f"{100 * float(f1_val):.1f}%" if pd.notna(f1_val) else "—"
        fig.add_trace(
            go.Scatter(
                x=[float(row["precision_pct"])],
                y=[float(row["recall_pct"])],
                mode="markers",
                name=("★ " + label) if is_champ else label,
                legendgroup=label,
                marker=dict(
                    size=size,
                    color=color,
                    symbol="star" if is_champ else "circle",
                    opacity=0.95 if is_champ else 0.88,
                    line=dict(
                        width=2.2 if is_champ else 1.2,
                        color=COLORS["text"] if is_champ else "rgba(255,255,255,0.35)",
                    ),
                ),
                customdata=[[label, float(row["roc_auc"]), f1_txt, "champion" if is_champ else "candidate"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b> (%{customdata[3]})<br>"
                    "Recall: %{y:.1f}%<br>"
                    "Precision: %{x:.1f}%<br>"
                    "ROC AUC: %{customdata[1]:.1%}<br>"
                    "F1: %{customdata[2]}<extra></extra>"
                ),
                showlegend=True,
            )
        )

    # Champion callout (single annotation — keeps the plot clean)
    champ = sub[sub["is_champion"]]
    if not champ.empty:
        crow = champ.iloc[0]
        fig.add_annotation(
            x=float(crow["precision_pct"]),
            y=float(crow["recall_pct"]),
            text=f"<b>{crow['model_label']}</b><br>champion",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.5,
            arrowcolor=COLORS["tab_active"],
            ax=48,
            ay=-42,
            font=dict(size=12, color=COLORS["tab_active"]),
            bgcolor="rgba(17, 24, 39, 0.85)",
            bordercolor=COLORS["tab_active"],
            borderwidth=1,
            borderpad=6,
        )

    split = register.get("split") or register.get("metrics", {}).get("split") or "holdout"
    fig.update_layout(
        **_plotly_layout(
            title=f"Model landscape — recall vs precision ({horizon}, {split})",
            xaxis_title="Precision (%)  →  fewer false alarms",
            yaxis_title="Recall (%)  →  catch more readmissions",
        )
    )
    fig.update_xaxes(
        range=[x0, x1],
        ticksuffix="%",
        showgrid=True,
        zeroline=False,
    )
    fig.update_yaxes(
        range=[y0, y1],
        ticksuffix="%",
        showgrid=True,
        zeroline=False,
    )
    apply_multitrace_legend_below(fig)
    apply_full_width_chart_layout(fig, height=500)
    # Extra bottom room for the multi-model legend
    fig.update_layout(margin=dict(b=130))
    render_plotly_chart(fig)


def chart_model_metrics_leaderboard(horizon: str = "30d") -> None:
    """Grouped horizontal bars: recall and ROC AUC per model; champion highlighted."""
    sub = _experiments_for_comparison(horizon)
    if sub.empty:
        st.info("experiments_matrix.csv not found.")
        return
    register = load_register()
    champion = str(register.get("champion_model", "catboost")).lower()
    sub = sub.sort_values("recall", ascending=True).copy()
    sub["recall_pct"] = sub["recall"] * 100
    sub["roc_auc_pct"] = sub["roc_auc"] * 100
    models = sub["model_label"].tolist()
    recall_colors = [
        COLORS["tab_active"] if str(m).lower() == champion else COLORS["bar"] for m in sub["model"]
    ]
    auc_colors = [
        COLORS["accent"] if str(m).lower() == champion else COLORS["muted"] for m in sub["model"]
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=models,
            x=sub["recall_pct"],
            name="Recall",
            orientation="h",
            marker_color=recall_colors,
            text=[f"{v:.1f}%" for v in sub["recall_pct"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Recall: %{x:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            y=models,
            x=sub["roc_auc_pct"],
            name="ROC AUC",
            orientation="h",
            marker_color=auc_colors,
            text=[f"{v:.1f}%" for v in sub["roc_auc_pct"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>ROC AUC: %{x:.1f}%<extra></extra>",
        )
    )
    split = register.get("split") or register.get("metrics", {}).get("split") or "holdout"
    fig.update_layout(
        **_plotly_layout(title=f"Model ranking — recall & discrimination ({horizon}, {split})"),
        barmode="group",
        xaxis_title="Score %",
        yaxis_title="",
    )
    fig.update_xaxes(range=[0, 100])
    apply_multitrace_legend_below(fig)
    apply_full_width_chart_layout(fig, height=460, n_categories=len(sub))
    render_plotly_chart(fig)


def chart_champion_recall() -> None:
    """Deprecated: champion recall is shown in KPI row and leaderboard."""
    chart_model_metrics_leaderboard("30d")


def chart_model_recall_by_model(horizon: str = "30d") -> None:
    """Deprecated: use precision-recall landscape + metrics leaderboard."""
    chart_model_precision_recall_landscape(horizon)


def chart_actual_vs_predicted() -> None:
    """Reliability diagram: mean predicted probability vs observed readmission rate per bin."""
    df = load_mart("mart_actual_vs_predicted")
    if df.empty or "y_true" not in df.columns or "y_prob" not in df.columns:
        st.info("Calibration data not found (expected y_true and y_prob in mart_actual_vs_predicted.csv).")
        return

    try:
        from sklearn.calibration import calibration_curve
    except ImportError:
        st.warning("scikit-learn is required for the calibration curve.")
        return

    y_true = df["y_true"].astype(float)
    y_prob = df["y_prob"].astype(float).clip(0.0, 1.0)
    frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy="quantile")

    register = load_register()
    champion = register.get("champion_model", "champion")
    model_label = _model_display_name(str(champion))

    fig = go.Figure()
    axis_max = max(float(mean_pred.max()), float(frac_pos.max()), 0.15) * 1.12
    fig.add_trace(
        go.Scatter(
            x=[0, axis_max],
            y=[0, axis_max],
            mode="lines",
            name="Perfect calibration",
            line=dict(color=COLORS["muted"], dash="dash", width=1.5),
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=mean_pred,
            y=frac_pos,
            mode="lines+markers",
            name=model_label,
            line=dict(color=COLORS["tab_active"], width=2.5),
            marker=dict(
                size=11,
                color=COLORS["accent"],
                line=dict(width=1.5, color=COLORS["text"]),
            ),
            text=[f"Decile {i + 1}" for i in range(len(frac_pos))],
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Mean predicted: %{x:.1%}<br>"
                "Observed rate: %{y:.1%}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        **_plotly_layout(
            title="Calibration curve — predicted vs observed readmission rate",
            xaxis_title="Mean predicted probability",
            yaxis_title="Observed readmission rate",
        ),
    )
    fig.update_xaxes(range=[0, axis_max], tickformat=".0%")
    fig.update_yaxes(range=[0, axis_max], tickformat=".0%")
    apply_multitrace_legend_below(fig)
    apply_full_width_chart_layout(fig, height=460)
    render_plotly_chart(fig)

