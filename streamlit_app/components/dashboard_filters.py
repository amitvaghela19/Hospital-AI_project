from __future__ import annotations

import streamlit as st

from streamlit_app.data_loaders import load_mart
from streamlit_app.gender_labels import expand_gender_filter, gender_filter_options
from streamlit_app.risk_labels import expand_risk_band_filter, normalize_risk_band_display, risk_band_filter_options


def _sorted_vals(series) -> list[str]:
    vals = [str(v) for v in series.dropna().astype(str).unique().tolist()]
    return sorted(vals)


def _visit_bucket(total_visits) -> str:
    """Bucket total visits into the same bands used across the app."""
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


def _med_bucket(active_med_count) -> str:
    """Medication band labels (kept small for readable UI)."""
    try:
        v = float(active_med_count) if active_med_count is not None else 0.0
    except Exception:
        v = 0.0
    if v <= 0:
        return "0 meds"
    if v == 1:
        return "1 med"
    if v == 2:
        return "2 meds"
    if v == 3:
        return "3 meds"
    if v == 4:
        return "4 meds"
    if v == 5:
        return "5 meds"
    return "6+ meds"


def _frequent_visitor_flag(mart_df) -> "pd.Series":
    # Local import to avoid hard dependency in type-checking.
    import pandas as pd

    return ((mart_df["number_inpatient"].fillna(0) >= 2) | (mart_df["total_visits"].fillna(0) >= 3)).astype(int)


def render_dashboard_filters() -> dict:
    mart = load_mart("mart_readmission")
    if mart.empty:
        return {}

    import pandas as pd

    if "time_in_hospital" in mart.columns:
        los_min = int(pd.to_numeric(mart["time_in_hospital"], errors="coerce").min(skipna=True) or 0)
        los_max = int(pd.to_numeric(mart["time_in_hospital"], errors="coerce").max(skipna=True) or 0)
        reset_los = (los_min, los_max)
    else:
        los_min, los_max = 0, 0
        reset_los = (0, 0)

    from streamlit_app.components.chart_drilldown import consume_pending_chart_filter_updates

    consume_pending_chart_filter_updates(reset_los_range=reset_los)

    age_options = _sorted_vals(mart["age"]) if "age" in mart.columns else []
    gender_options = gender_filter_options(mart["gender"]) if "gender" in mart.columns else []

    # Create base buckets for band filters.
    if "total_visits" in mart.columns:
        mart["_visit_bucket"] = mart["total_visits"].apply(_visit_bucket)
    else:
        mart["_visit_bucket"] = "0 visits"
    if "active_med_count" in mart.columns:
        mart["_med_bucket"] = mart["active_med_count"].apply(_med_bucket)
    else:
        mart["_med_bucket"] = "0 meds"

    if "number_inpatient" in mart.columns and "total_visits" in mart.columns:
        mart["_frequent_visitor"] = _frequent_visitor_flag(mart)
    else:
        mart["_frequent_visitor"] = 0

    # Widgets
    st.sidebar.markdown("---")
    st.sidebar.subheader("Dashboard Filters (Cohort Slice)")
    st.sidebar.caption(
        "Click or double-click any chart bar/slice to toggle filters here. "
        "Use **Reset cohort view** under a chart or **Clear filters** here to go back to the full cohort."
    )

    age = st.sidebar.multiselect("Age band", age_options, default=[], key="dash_age")
    gender = st.sidebar.multiselect("Gender", gender_options, default=[], key="dash_gender")

    # Diagnosis options cascade by age/gender selection to reduce noise.
    diag_base = mart
    if age:
        diag_base = diag_base[diag_base["age"].astype(str).isin([str(v) for v in age])]
    if gender:
        raw_genders = expand_gender_filter(gender, mart["gender"])
        if raw_genders:
            diag_base = diag_base[diag_base["gender"].astype(str).isin(raw_genders)]

    diag_all = _sorted_vals(diag_base["diag_1"]) if "diag_1" in diag_base.columns else []
    diag_search = st.sidebar.text_input("Diagnosis search (optional)", value="", key="dash_diag_search")
    if diag_search:
        s = diag_search.lower().strip()
        diag_options = [d for d in diag_all if s in d.lower()]
    else:
        diag_options = diag_all

    diag = st.sidebar.multiselect("Diagnosis", diag_options, default=[], key="dash_diag")

    # Readmission flag
    readmit_options = ["Readmitted (30d)", "Not readmitted (30d)"]
    readmit_selection = st.sidebar.multiselect("30-day readmission", readmit_options, default=[], key="dash_readmit")

    # LOS range
    if "time_in_hospital" in mart.columns:
        los_range = st.sidebar.slider("LOS (days) range", min_value=los_min, max_value=los_max, value=(los_min, los_max), key="dash_los_range")
    else:
        los_range = None

    # Visit frequency
    visit_bands = ["0 visits", "1-2 visits", "3-5 visits", "6+ visits"]
    visit_selection = st.sidebar.multiselect("Visit frequency band", visit_bands, default=[], key="dash_visit_band")

    # Frequent visitor
    frequent_options = ["Frequent visitor (Yes)", "Frequent visitor (No)"]
    frequent_selection = st.sidebar.multiselect("Frequent visitor", frequent_options, default=[], key="dash_frequent_visitor")

    # Medication bands
    med_bands = ["0 meds", "1 med", "2 meds", "3 meds", "4 meds", "5 meds", "6+ meds"]
    med_selection = st.sidebar.multiselect("Medication count band", med_bands, default=[], key="dash_med_band")

    risk_cr = load_mart("mart_clinical_risk")
    if not risk_cr.empty and "horizon" in risk_cr.columns:
        sub30 = risk_cr[risk_cr["horizon"].astype(str).str.lower() == "30d"]
        if not sub30.empty:
            risk_cr = sub30
    risk_band_options = (
        risk_band_filter_options(risk_cr["risk_band"])
        if not risk_cr.empty and "risk_band" in risk_cr.columns
        else list(risk_band_filter_options(None))
    )
    risk_band = st.sidebar.multiselect(
        "Risk band (model)",
        risk_band_options,
        default=[],
        key="dash_risk_band",
        help="Filters to scored encounters in mart_clinical_risk (30d horizon). "
        "Also set by clicking the risk-band chart on Model Insights.",
    )

    clear = st.sidebar.button("Clear filters", key="dash_clear")
    if clear:
        from streamlit_app.components.chart_drilldown import queue_clear_chart_filters

        queue_clear_chart_filters()

    return {
        "age": age,
        "gender": gender,
        "diag_1": diag,
        "readmit_30d": readmit_selection,
        "los_range": los_range,
        "visit_band": visit_selection,
        "frequent_visitor": frequent_selection,
        "med_band": med_selection,
        "risk_band": risk_band,
    }


def get_dashboard_filters_from_session() -> dict:
    """Rebuild cohort filters from session_state (keeps pages in sync without re-rendering widgets)."""
    mart = load_mart("mart_readmission")
    if mart.empty:
        return {}

    import pandas as pd

    los_range = None
    if "time_in_hospital" in mart.columns:
        los_min = int(pd.to_numeric(mart["time_in_hospital"], errors="coerce").min(skipna=True) or 0)
        los_max = int(pd.to_numeric(mart["time_in_hospital"], errors="coerce").max(skipna=True) or 0)
        los_range = st.session_state.get("dash_los_range", (los_min, los_max))

    return {
        "age": list(st.session_state.get("dash_age", []) or []),
        "gender": list(st.session_state.get("dash_gender", []) or []),
        "diag_1": list(st.session_state.get("dash_diag", []) or []),
        "readmit_30d": list(st.session_state.get("dash_readmit", []) or []),
        "los_range": los_range,
        "visit_band": list(st.session_state.get("dash_visit_band", []) or []),
        "frequent_visitor": list(st.session_state.get("dash_frequent_visitor", []) or []),
        "med_band": list(st.session_state.get("dash_med_band", []) or []),
        "risk_band": list(st.session_state.get("dash_risk_band", []) or []),
    }


def _coerce_los_range(val):
    if val is None:
        return None
    try:
        lo, hi = val
        return lo, hi
    except (TypeError, ValueError):
        return None


def _filter_value_is_set(key: str, val) -> bool:
    if val is None:
        return False
    if key == "los_range":
        parsed = _coerce_los_range(val)
        if parsed is None:
            return False
        lo, hi = parsed
        return lo is not None or hi is not None
    if isinstance(val, (list, tuple)):
        return len(val) > 0
    try:
        import numpy as np

        if isinstance(val, np.ndarray):
            return val.size > 0
    except ImportError:
        pass
    return bool(val)


def cohort_filter_active(filters: dict | None) -> bool:
    if not filters:
        return False
    for key, val in filters.items():
        if _filter_value_is_set(key, val):
            return True
    return False


def apply_dashboard_filters(df, filters: dict | None):
    if not filters:
        return df

    import pandas as pd

    out = df.copy()

    # Base cohort filters (string match)
    if _filter_value_is_set("age", filters.get("age")) and "age" in out.columns:
        out = out[out["age"].astype(str).isin([str(v) for v in filters["age"]])]
    if _filter_value_is_set("gender", filters.get("gender")) and "gender" in out.columns:
        raw_genders = expand_gender_filter(filters["gender"], out["gender"])
        if raw_genders:
            out = out[out["gender"].astype(str).isin(raw_genders)]
    if _filter_value_is_set("diag_1", filters.get("diag_1")) and "diag_1" in out.columns:
        out = out[out["diag_1"].astype(str).isin([str(v) for v in filters["diag_1"]])]

    # Readmission flag
    readmit_sel = filters.get("readmit_30d") or []
    if readmit_sel and "readmit_30d" in out.columns:
        allowed = set()
        if "Readmitted (30d)" in readmit_sel:
            allowed.add(1)
        if "Not readmitted (30d)" in readmit_sel:
            allowed.add(0)
        readmit_vals = pd.to_numeric(out["readmit_30d"], errors="coerce")
        out = out[readmit_vals.isin(list(allowed))]

    # LOS range
    los_range = _coerce_los_range(filters.get("los_range"))
    if los_range is not None and "time_in_hospital" in out.columns:
        lo, hi = los_range
        out = out[
            pd.to_numeric(out["time_in_hospital"], errors="coerce").between(lo, hi, inclusive="both")
        ]

    # Visit band
    visit_sel = filters.get("visit_band") or []
    if visit_sel:
        out["_visit_bucket"] = out["total_visits"].apply(_visit_bucket) if "total_visits" in out.columns else "0 visits"
        out = out[out["_visit_bucket"].isin(visit_sel)]

    # Frequent visitor
    freq_sel = filters.get("frequent_visitor") or []
    if freq_sel:
        out["_frequent_visitor"] = _frequent_visitor_flag(out) if ("number_inpatient" in out.columns and "total_visits" in out.columns) else 0
        allowed = set()
        if "Frequent visitor (Yes)" in freq_sel:
            allowed.add(1)
        if "Frequent visitor (No)" in freq_sel:
            allowed.add(0)
        out = out[out["_frequent_visitor"].isin(list(allowed))]

    # Medication band
    med_sel = filters.get("med_band") or []
    if med_sel:
        out["_med_bucket"] = out["active_med_count"].apply(_med_bucket) if "active_med_count" in out.columns else "0 meds"
        out = out[out["_med_bucket"].isin(med_sel)]

    # Model risk band (via clinical risk mart join)
    risk_sel = filters.get("risk_band") or []
    if risk_sel and "encounter_id" in out.columns:
        cr = load_mart("mart_clinical_risk")
        if not cr.empty and "horizon" in cr.columns:
            sub30 = cr[cr["horizon"].astype(str).str.lower() == "30d"]
            if not sub30.empty:
                cr = sub30
        if not cr.empty and "risk_band" in cr.columns:
            raw_bands = expand_risk_band_filter(risk_sel)
            enc = cr[cr["risk_band"].astype(str).str.casefold().isin(raw_bands)]["encounter_id"]
            out = out[out["encounter_id"].isin(enc)]

    # Cleanup helper columns
    for col in ["_visit_bucket", "_frequent_visitor", "_med_bucket"]:
        if col in out.columns:
            out = out.drop(columns=[col])

    return out
