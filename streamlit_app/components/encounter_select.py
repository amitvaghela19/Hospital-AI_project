from __future__ import annotations

import pandas as pd
import streamlit as st

from streamlit_app import ROOT
from streamlit_app.data_loaders import load_gold_features, sort_encounters_by_certified_risk
from streamlit_app.risk_labels import normalize_risk_band_display

FEATURE_GROUPS = {
    "Demographics": ["race", "gender", "age"],
    "Admission": [
        "admission_type_id",
        "discharge_disposition_id",
        "admission_source_id",
        "time_in_hospital",
    ],
    "Utilization": [
        "number_outpatient",
        "number_emergency",
        "number_inpatient",
        "total_visits",
        "number_diagnoses",
    ],
    "Medications": [
        "num_medications",
        "active_med_count",
        "change",
        "diabetesMed",
        "insulin",
        "metformin",
    ],
    "Labs": [
        "num_lab_procedures",
        "num_procedures",
        "has_A1C",
        "has_max_glu",
        "A1Cresult",
        "max_glu_serum",
    ],
    "Diagnoses": ["diag_1"],
}


@st.cache_data(show_spinner=False)
def encounter_index() -> pd.DataFrame:
    gold = load_gold_features()
    if gold.empty or "encounter_id" not in gold.columns:
        return pd.DataFrame()
    cols = ["encounter_id", "patient_nbr", "gender", "age", "time_in_hospital", "readmit_30d"]
    cols = [c for c in cols if c in gold.columns]
    return gold[cols].drop_duplicates("encounter_id")


def _exact_id_mask(df: pd.DataFrame, query: str, *, include_patient: bool) -> pd.Series:
    """Match encounter_id or patient_nbr exactly — no substring/partial matches."""
    q = query.strip()
    enc_match = df["encounter_id"].astype(str).str.strip() == q
    if not include_patient or "patient_nbr" not in df.columns:
        return enc_match
    pat_match = df["patient_nbr"].astype(str).str.strip() == q
    return enc_match | pat_match


def pick_encounter_row(feature_cols: list[str], role: str = "clinician") -> dict | None:
    from streamlit_app.rbac import ids_policy
    from streamlit_app.rbac_auth import validate_role

    role = validate_role(role)
    can_ids, mask_patient = ids_policy(role)
    idx = encounter_index()
    if idx.empty:
        st.warning("Gold features parquet missing. Run Phase 2.")
        return None

    if not can_ids:
        st.error("Your role cannot access encounter identifiers.")
        return None

    st.markdown("**Encounter lookup**")
    mode = st.radio(
        "Input mode",
        ["Select encounter", "Manual entry"],
        horizontal=True,
        label_visibility="collapsed",
    )

    gold = load_gold_features()
    defaults = gold.iloc[0].to_dict() if not gold.empty else {}

    if mode == "Select encounter":
        search_label = "Search encounter ID" if mask_patient else "Search encounter or patient ID"
        search = st.text_input(search_label, placeholder="e.g. 53767290")
        if search.strip():
            filtered = idx[_exact_id_mask(idx, search, include_patient=not mask_patient)]
            if filtered.empty:
                st.error(
                    "No encounter found with that exact ID. "
                    "Please recheck the encounter or patient ID."
                )
                return None
            filtered = sort_encounters_by_certified_risk(filtered)
            if len(filtered) > 1:
                st.caption(
                    f"{len(filtered)} encounters match — sorted by **certified risk** "
                    "(highest probability first). Select the visit to score."
                )
        else:
            filtered = idx
        if mask_patient:
            options = filtered.apply(
                lambda r: f"{r['encounter_id']} | {r.get('gender','')} | {r.get('age','')} | LOS={r.get('time_in_hospital','')}",
                axis=1,
            ).tolist()
        else:
            def _option_label(r) -> str:
                band = normalize_risk_band_display(r.get("risk_band")) if pd.notna(r.get("risk_band")) else "—"
                prob = r.get("y_prob")
                prob_s = f"{float(prob) * 100:.1f}%" if pd.notna(prob) else "—"
                return (
                    f"{int(r['encounter_id'])} | pt={r.get('patient_nbr','')} | "
                    f"{band} | {prob_s} | {r.get('gender','')} | {r.get('age','')}"
                )

            options = filtered.apply(_option_label, axis=1).tolist()
        choice = st.selectbox("Encounter", options, label_visibility="collapsed")
        eid = int(choice.split(" | ")[0])
        row_series = gold[gold["encounter_id"] == eid].iloc[0]
        row = {c: row_series.get(c) for c in feature_cols if c in row_series.index}
        row["encounter_id"] = eid
        if mask_patient:
            row.pop("patient_nbr", None)
        else:
            row["patient_nbr"] = row_series.get("patient_nbr")
        scored = dict(row_series)
        if mask_patient:
            scored.pop("patient_nbr", None)
        st.session_state["last_scored_row"] = scored
        st.session_state["selected_encounter_id"] = eid
        return row

    row = {}
    for group, fields in FEATURE_GROUPS.items():
        with st.expander(group, expanded=(group == "Demographics")):
            cols = st.columns(2)
            for i, field in enumerate(fields):
                if field not in feature_cols:
                    continue
                val = defaults.get(field, "")
                with cols[i % 2]:
                    if isinstance(val, (int, float)) and field not in ("diag_1", "age", "gender", "race"):
                        row[field] = st.number_input(
                            field,
                            value=float(val) if pd.notna(val) else 0.0,
                            key=f"manual_{field}",
                        )
                    else:
                        row[field] = st.text_input(
                            field,
                            value="" if pd.isna(val) else str(val),
                            key=f"manual_{field}",
                        )
    for c in feature_cols:
        if c not in row:
            row[c] = defaults.get(c)
    return row
