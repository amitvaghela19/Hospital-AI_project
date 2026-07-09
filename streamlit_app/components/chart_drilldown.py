"""Cross-page chart drill-down: click/double-click Plotly elements → synced cohort filters."""

from __future__ import annotations

import json
from typing import Any, Callable

import pandas as pd
import plotly.graph_objects as go

from streamlit_app.components.dashboard_filters import (
    _med_bucket,
    _visit_bucket,
    apply_dashboard_filters,
    cohort_filter_active,
    get_dashboard_filters_from_session,
)
from streamlit_app.data_loaders import load_mart
from streamlit_app.gender_labels import normalize_gender_display
from streamlit_app.risk_labels import normalize_risk_band_display
from streamlit_app.chart_theme import render_plotly_chart

# Session keys aligned with dashboard_filters multiselects.
DIMENSION_KEYS: dict[str, str] = {
    "age": "dash_age",
    "gender": "dash_gender",
    "diag_1": "dash_diag",
    "visit_band": "dash_visit_band",
    "med_band": "dash_med_band",
    "readmit_30d": "dash_readmit",
    "risk_band": "dash_risk_band",
    "frequent_visitor": "dash_frequent_visitor",
}

_SLICE_META_KEY = "dash_chart_slice_meta"
_SIG_PREFIX = "_chart_slice_sig_"
_PENDING_SLICE_KEY = "_pending_chart_slice_updates"
_PENDING_CLEAR_KEY = "_pending_chart_slice_clear"
_PENDING_RESTORE_KEY = "_pending_restore_baseline"
_BASELINE_KEY = "_dash_filter_baseline"
_UIREV_KEY = "_chart_uirevision_seq"


def _st():
    import streamlit as st

    return st


def _session_list(key: str) -> list:
    return list(_st().session_state.get(key, []) or [])


def _default_filter_baseline(reset_los: tuple[int, int] | None) -> dict:
    return {
        "filters": {sk: [] for sk in DIMENSION_KEYS.values()},
        "los_range": reset_los,
        "diag_search": "",
    }


def capture_filter_baseline(*, reset_los_range: tuple[int, int] | None) -> None:
    """Remember the original unfiltered cohort (empty filters + full LOS range)."""
    st = _st()
    if _BASELINE_KEY not in st.session_state:
        st.session_state[_BASELINE_KEY] = _default_filter_baseline(reset_los_range)


def refresh_filter_baseline(*, reset_los_range: tuple[int, int] | None) -> None:
    """Reset the saved baseline to the default full cohort."""
    _st().session_state[_BASELINE_KEY] = _default_filter_baseline(reset_los_range)


def _bump_uirevision() -> None:
    st = _st()
    st.session_state[_UIREV_KEY] = int(st.session_state.get(_UIREV_KEY, 0)) + 1


def chart_uirevision(chart_id: str) -> str:
    """Stable Plotly layout key; bumped when cohort filters reset so zoom returns to default."""
    seq = int(_st().session_state.get(_UIREV_KEY, 0))
    return f"{chart_id}-v{seq}"


def _chart_uirevision(chart_id: str) -> str:
    return chart_uirevision(chart_id)


def _clear_selection_tracking() -> None:
    st = _st()
    for key in list(st.session_state.keys()):
        if str(key).startswith(_SIG_PREFIX):
            st.session_state.pop(key, None)


def queue_restore_baseline() -> None:
    """Restore sidebar filters and chart zoom to the original full cohort."""
    _st().session_state[_PENDING_RESTORE_KEY] = True
    _st().rerun()


def _queue_session_toggle(session_key: str, value: str) -> None:
    """Queue a widget-safe toggle to apply before sidebar widgets render."""
    value = str(value).strip()
    if not value:
        return
    st = _st()
    pending = list(st.session_state.get(_PENDING_SLICE_KEY, []) or [])
    pending.append({"session_key": session_key, "value": value})
    st.session_state[_PENDING_SLICE_KEY] = pending


def apply_chart_slice(
    *,
    dimension: str,
    value: str,
    chart_id: str,
    chart_title: str,
    label: str | None = None,
) -> None:
    """Apply a chart selection to shared session filters."""
    session_key = DIMENSION_KEYS.get(dimension)
    if not session_key:
        return
    st = _st()
    _queue_session_toggle(session_key, value)
    st.session_state[_SLICE_META_KEY] = {
        "dimension": dimension,
        "value": value,
        "label": label or value,
        "chart_id": chart_id,
        "chart_title": chart_title,
    }
    st.rerun()


def clear_chart_slice_state() -> None:
    st = _st()
    st.session_state.pop(_SLICE_META_KEY, None)
    st.session_state.pop(_PENDING_SLICE_KEY, None)
    st.session_state.pop(_PENDING_CLEAR_KEY, None)
    st.session_state.pop(_PENDING_RESTORE_KEY, None)
    _clear_selection_tracking()


def consume_pending_chart_filter_updates(*, reset_los_range: tuple[int, int] | None = None) -> None:
    """Apply queued chart-driven filter changes before widget instantiation."""
    st = _st()
    capture_filter_baseline(reset_los_range=reset_los_range)

    if st.session_state.pop(_PENDING_RESTORE_KEY, False):
        baseline = st.session_state.get(_BASELINE_KEY) or _default_filter_baseline(reset_los_range)
        for sk, vals in baseline.get("filters", {}).items():
            st.session_state[sk] = list(vals)
        if reset_los_range is not None:
            st.session_state["dash_los_range"] = baseline.get("los_range", reset_los_range)
        st.session_state["dash_diag_search"] = baseline.get("diag_search", "")
        clear_chart_slice_state()
        _bump_uirevision()
        return

    if st.session_state.pop(_PENDING_CLEAR_KEY, False):
        for sk in DIMENSION_KEYS.values():
            st.session_state[sk] = []
        if reset_los_range is not None:
            st.session_state["dash_los_range"] = reset_los_range
        st.session_state["dash_diag_search"] = ""
        refresh_filter_baseline(reset_los_range=reset_los_range)
        clear_chart_slice_state()
        _bump_uirevision()
        return

    pending = list(st.session_state.pop(_PENDING_SLICE_KEY, []) or [])
    if not pending:
        return

    for item in pending:
        session_key = str(item.get("session_key") or "").strip()
        value = str(item.get("value") or "").strip()
        if not session_key or not value:
            continue
        if session_key == DIMENSION_KEYS["risk_band"]:
            value = normalize_risk_band_display(value)
        if session_key == DIMENSION_KEYS["gender"]:
            value = normalize_gender_display(value)
        current = list(st.session_state.get(session_key, []) or [])
        if session_key == DIMENSION_KEYS["risk_band"]:
            current = [normalize_risk_band_display(v) for v in current]
        if session_key == DIMENSION_KEYS["gender"]:
            current = [normalize_gender_display(v) for v in current]
        if value in current:
            st.session_state[session_key] = [v for v in current if v != value]
        else:
            st.session_state[session_key] = current + [value]


def queue_clear_chart_filters() -> None:
    st = _st()
    st.session_state[_PENDING_CLEAR_KEY] = True
    st.rerun()


def cohort_slice_active() -> bool:
    """True when chart drill-down or any cohort filter is active."""
    st = _st()
    if st.session_state.get(_SLICE_META_KEY):
        return True
    return cohort_filter_active(get_dashboard_filters_from_session())


def render_reset_cohort_control(chart_id: str) -> None:
    """Reset cohort filters and chart zoom (Plotly reset-axes equivalent for data)."""
    st = _st()
    if not cohort_slice_active():
        return
    if st.button(
        "Reset cohort view",
        key=f"reset_cohort_{chart_id}",
        type="secondary",
        help="Clear chart-driven filters and reset chart zoom to the full cohort.",
    ):
        queue_restore_baseline()


def _selection_signature(chart_id: str, points: list[dict]) -> str:
    payload = {"chart_id": chart_id, "points": points}
    return json.dumps(payload, sort_keys=True, default=str)


def _process_point_selection(
    chart_id: str,
    chart_title: str,
    dimension: str,
    points: list[dict],
    value_fn: Callable[[dict], str | None],
) -> None:
    if not points:
        return
    sig = _selection_signature(chart_id, points)
    sig_key = f"{_SIG_PREFIX}{chart_id}"
    session = _st().session_state
    if session.get(sig_key) == sig:
        return
    session[sig_key] = sig

    for pt in points:
        raw = value_fn(pt)
        if raw is None:
            continue
        apply_chart_slice(
            dimension=dimension,
            value=str(raw),
            chart_id=chart_id,
            chart_title=chart_title,
            label=str(raw),
        )


def render_interactive_plotly(
    fig,
    *,
    chart_id: str,
    chart_title: str,
    dimension: str,
    value_fn: Callable[[dict], str | None] | None = None,
    height: int | None = None,
) -> None:
    """
    Render Plotly with selection → cohort filter sync across dashboard pages.
    Click or double-click a bar/slice/point to toggle that dimension in the sidebar filters.
    """
    fig.update_layout(clickmode="event+select", uirevision=_chart_uirevision(chart_id))
    if height:
        fig.update_layout(height=height)

    def _default_value_fn(pt: dict) -> str | None:
        for key in ("y", "x", "label", "legendgroup"):
            if pt.get(key) not in (None, ""):
                return str(pt[key])
        custom = pt.get("customdata")
        if isinstance(custom, (list, tuple)) and custom:
            return str(custom[0])
        if custom not in (None, ""):
            return str(custom)
        return None

    extractor = value_fn or _default_value_fn
    event = render_plotly_chart(
        fig,
        on_select="rerun",
        key=f"plotly_{chart_id}",
    )

    selection = getattr(event, "selection", None) if event is not None else None
    points = []
    if selection is not None:
        if hasattr(selection, "points"):
            points = list(selection.points or [])
        elif isinstance(selection, dict):
            points = list(selection.get("points") or [])

    if points:
        _process_point_selection(chart_id, chart_title, dimension, points, extractor)

    render_reset_cohort_control(chart_id)


def attach_pie_diag_customdata(fig: go.Figure, diag_values: list[str]) -> go.Figure:
    """Ensure pie selections return ICD diagnosis codes, not legend labels."""
    if fig.data:
        fig.data[0].customdata = [[d] for d in diag_values]
    return fig


def med_count_to_band(count: int | str) -> str:
    try:
        n = int(float(count))
    except Exception:
        return _med_bucket(0)
    if n <= 0:
        return "0 meds"
    if n == 1:
        return "1 med"
    if n == 2:
        return "2 meds"
    if n == 3:
        return "3 meds"
    if n == 4:
        return "4 meds"
    if n == 5:
        return "5 meds"
    return "6+ meds"


def cohort_summary(filters: dict | None = None) -> dict[str, Any]:
    """Quick stats for the active cohort slice."""
    mart = load_mart("mart_readmission")
    if mart.empty:
        return {}
    filtered = apply_dashboard_filters(mart, filters or {})
    if filtered.empty:
        return {"encounters": 0, "patients": 0, "readmit_rate": 0.0, "avg_los": 0.0}
    patients = (
        int(filtered["patient_nbr"].nunique())
        if "patient_nbr" in filtered.columns
        else len(filtered)
    )
    return {
        "encounters": len(filtered),
        "patients": patients,
        "readmit_rate": float(filtered["readmit_30d"].mean() * 100)
        if "readmit_30d" in filtered.columns
        else 0.0,
        "avg_los": float(filtered["time_in_hospital"].mean())
        if "time_in_hospital" in filtered.columns
        else 0.0,
    }


def render_chart_drilldown_banner(filters: dict | None = None) -> None:
    """Top-of-page banner: active chart slice + cohort KPIs (synced on every dashboard page)."""
    st = _st()
    filters = filters or get_dashboard_filters_from_session()
    meta = st.session_state.get(_SLICE_META_KEY) or {}
    active = cohort_filter_active(filters)

    if not active and not meta:
        st.caption(
            "💡 **Chart drill-down:** click or double-click any bar, slice, or point on a chart "
            "to add/remove that value in **Dashboard Filters** — all dashboard pages stay in sync."
        )
        return

    summary = cohort_summary(filters)
    title_bits = []
    if meta:
        title_bits.append(
            f"Last chart slice: **{meta.get('chart_title', 'Chart')}** → "
            f"`{meta.get('label', meta.get('value', ''))}`"
        )
    if active:
        parts = []
        for dim, key in [
            ("Age", "age"),
            ("Gender", "gender"),
            ("Diagnosis", "diag_1"),
            ("Visit band", "visit_band"),
            ("Med band", "med_band"),
            ("Risk band", "risk_band"),
            ("Readmit", "readmit_30d"),
        ]:
            vals = filters.get(key) or []
            if vals:
                parts.append(f"{dim}: {', '.join(map(str, vals))}")
        if parts:
            title_bits.append("Active filters: " + " · ".join(parts))

    st.info(" · ".join(title_bits) if title_bits else "Cohort filters active.")

    if summary.get("encounters", 0) > 0:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cohort encounters", f"{summary['encounters']:,}")
        c2.metric("Cohort patients", f"{summary['patients']:,}")
        c3.metric("Readmit rate", f"{summary['readmit_rate']:.1f}%")
        c4.metric("Avg LOS", f"{summary['avg_los']:.1f} d")

    if st.button("Clear chart-driven filters", key="dash_clear_chart_slice", type="secondary"):
        queue_clear_chart_filters()


def render_high_risk_drilldown_card(
    point: dict,
    plot_df: pd.DataFrame,
    *,
    can_ids: bool,
    mask_patient: bool,
) -> None:
    """Show encounter-level detail when a high-risk bar is selected."""
    st = _st()
    idx = point.get("point_index", point.get("point_number"))
    if idx is None or plot_df.empty:
        return
    try:
        row = plot_df.iloc[int(idx)]
    except Exception:
        return

    st.markdown("#### Selected encounter (chart drill-down)")
    cols = st.columns(4)
    cols[0].metric("Probability", f"{float(row.get('y_prob', 0) or 0) * 100:.1f}%")
    cols[1].metric("Risk band", str(row.get("risk_band", "—")))
    cols[2].metric("Age", str(row.get("age", "—")))
    cols[3].metric("Gender", str(row.get("gender", "—")))
    if can_ids and "encounter_id" in row.index:
        st.caption(f"Encounter ID: `{int(row['encounter_id'])}`")
    if can_ids and not mask_patient and "patient_nbr" in row.index and pd.notna(row.get("patient_nbr")):
        st.caption(f"Patient ID: `{int(row['patient_nbr'])}`")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Sync age/gender to cohort filters", key="hr_sync_demo"):
            if pd.notna(row.get("age")):
                apply_chart_slice(
                    dimension="age",
                    value=str(row["age"]),
                    chart_id="high_risk",
                    chart_title="High-risk encounters",
                )
            if pd.notna(row.get("gender")):
                apply_chart_slice(
                    dimension="gender",
                    value=str(row["gender"]),
                    chart_id="high_risk",
                    chart_title="High-risk encounters",
                )
            st.rerun()
    with b2:
        if st.button("Dismiss selection", key="hr_dismiss"):
            st.session_state.pop(f"{_SIG_PREFIX}high_risk_encounters", None)
            st.rerun()


def process_chart_selection_event(
    chart_id: str,
    points: list,
    *,
    on_select_points: Callable[[list], None] | None = None,
) -> None:
    """Shared handler for raw plotly_chart selection events."""
    if points and on_select_points is not None:
        on_select_points(points)
