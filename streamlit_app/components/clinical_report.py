from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from streamlit_app import ROOT

# Diabetes 130-US hospitals — common code labels (analytics display only).
ADMISSION_TYPE = {
    1: "Emergency",
    2: "Urgent",
    3: "Elective",
    4: "Newborn",
    5: "Not available",
    6: "Unknown",
    7: "Trauma center",
    8: "Not mapped",
}

DISCHARGE_DISPOSITION = {
    1: "Discharged to home",
    2: "Discharged to short-term hospital",
    3: "Discharged to SNF",
    4: "Discharged to ICF",
    5: "Discharged to another facility",
    6: "Discharged to home with home health",
    7: "Left AMA",
    8: "Discharged to home under hospice",
    9: "Admitted as inpatient",
    10: "Neonate discharged",
    11: "Expired",
    12: "Hospice",
    13: "Discharged to home — diabetic supplies",
    14: "Discharged to psychiatric facility",
    15: "Discharged to federal facility",
    16: "Cancer center",
    17: "Swing bed",
    18: "Expired at home",
    19: "Expired at medical facility",
    20: "Expired — unknown location",
    22: "Rehab",
    23: "Long-term care",
    24: "Nursing facility",
    25: "Other institution",
    28: "Other",
}

ADMISSION_SOURCE = {
    1: "Physician referral",
    2: "Clinic referral",
    3: "HMO referral",
    4: "Transfer from hospital",
    5: "Transfer from SNF",
    6: "Transfer from another facility",
    7: "Emergency room",
    8: "Court/law enforcement",
    9: "Not available",
    10: "Transfer from critical access",
    11: "Normal delivery",
    12: "Premature delivery",
    13: "Sick baby",
    14: "Extramural birth",
    15: "Not available",
    17: "Not available",
    20: "Not available",
    18: "Transfer from another home health",
    19: "Readmission",
    22: "Transfer from rehab",
    23: "Not mapped",
    25: "Not mapped",
    26: "Transfer from hospice",
}

MEDICATION_COLUMNS = [
    "metformin", "repaglinide", "nateglinide", "chlorpropamide", "glimepiride",
    "acetohexamide", "glipizide", "glyburide", "tolbutamide", "pioglitazone",
    "rosiglitazone", "acarbose", "miglitol", "troglitazone", "tolazamide",
    "examide", "citoglipton", "insulin", "glyburide-metformin", "glipizide-metformin",
    "glimepiride-pioglitazone", "metformin-rosiglitazone", "metformin-pioglitazone",
]


@st.cache_data(show_spinner=False)
def load_silver_encounter(encounter_id: int | str) -> dict:
    path = ROOT / "data" / "lake" / "silver" / "encounters.parquet"
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    if "encounter_id" not in df.columns:
        return {}
    hit = df[df["encounter_id"] == int(encounter_id)]
    if hit.empty:
        return {}
    return hit.iloc[0].to_dict()


def _fmt(val: Any, default: str = "Not recorded") -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    s = str(val).strip()
    if s in ("", "?", "nan", "None"):
        return default
    return s


def _code_label(val: Any, mapping: dict[int, str]) -> str:
    try:
        key = int(float(val))
        label = mapping.get(key)
        if label:
            return f"{label} (code {key})"
        return f"Code {key}"
    except (TypeError, ValueError):
        return _fmt(val)


def _active_medications(silver: dict) -> list[str]:
    meds = []
    for col in MEDICATION_COLUMNS:
        if col not in silver:
            continue
        v = _fmt(silver.get(col), "")
        if v and v.lower() not in ("no", "not recorded", "?"):
            meds.append(f"{col.replace('-', ' / ').title()}: {v}")
    if not meds and silver:
        for key in ("insulin", "metformin"):
            if key in silver:
                v = _fmt(silver.get(key), "")
                if v.lower() not in ("no", "not recorded"):
                    meds.append(f"{key.title()}: {v}")
    return meds or ["No active diabetes medications documented on encounter record."]


def _lab_line(silver: dict, row: dict) -> list[str]:
    lines = []
    a1c = silver.get("A1Cresult") if silver else row.get("A1Cresult")
    glu = silver.get("max_glu_serum") if silver else row.get("max_glu_serum")
    if _fmt(a1c, "") not in ("", "Not recorded"):
        lines.append(f"Hemoglobin A1c: {_fmt(a1c)}")
    elif row.get("has_A1C"):
        lines.append("Hemoglobin A1c: ordered / result flagged present (value not in extract)")
    else:
        lines.append("Hemoglobin A1c: not available for this encounter")
    if _fmt(glu, "") not in ("", "Not recorded"):
        lines.append(f"Max serum glucose: {_fmt(glu)}")
    elif row.get("has_max_glu"):
        lines.append("Serum glucose: ordered / result flagged present")
    else:
        lines.append("Max serum glucose: not available")
    labs = int(row.get("num_lab_procedures", silver.get("num_lab_procedures", 0)) or 0)
    procs = int(row.get("num_procedures", silver.get("num_procedures", 0)) or 0)
    lines.append(f"Laboratory procedures during stay: {labs}")
    lines.append(f"Non-lab procedures during stay: {procs}")
    return lines


def build_report_text(
    row: dict,
    pred: dict,
    register: dict,
    silver: dict | None = None,
    role: str = "clinician",
) -> str:
    from streamlit_app.rbac import ids_policy
    from streamlit_app.rbac_auth import validate_role

    role = validate_role(role)
    silver = silver or {}
    can_ids, mask_patient = ids_policy(role)
    eid = row.get("encounter_id", silver.get("encounter_id", "—")) if can_ids else "REDACTED"
    mrn = row.get("patient_nbr", silver.get("patient_nbr", "—"))
    if not can_ids or mask_patient:
        mrn = "MASKED"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    band = pred["band"]
    prob = pred["prob"]
    routed = pred["routed"]
    score_source = pred.get("score_source", "live_pipeline")
    live_prob = pred.get("live_prob", prob)
    certified_block = ""
    pipeline_block = ""
    divergence_note = ""

    if score_source == "certified_mart":
        certified_block = f"""  Certified risk band:    {band}
  Certified probability:  {prob:.1%}
  Score source:           mart_clinical_risk.csv (dashboard-aligned)
"""
        pipeline_block = f"""  Pipeline re-score (live):
  Primary tri_ensemble score: {routed.get('primary_prob', 0):.4f}
  Live blended probability:   {live_prob:.1%}
  Inference route:            {routed.get('route', 'tri_only')}
  RNN score (if used):        {f"{routed.get('rnn_prob'):.4f}" if routed.get('rnn_prob') is not None else "N/A"}
  Reference RF score:         {f"{pred.get('reference_prob'):.4f}" if pred.get('reference_prob') is not None else "N/A"}
  Model disagreement:         {"Yes — manual review advised" if pred.get('disagree') else "No"}
"""
        if pred.get("score_divergence"):
            divergence_note = (
                "\n  Note: Live pipeline score differs from certified mart — "
                "dashboards and Risk Analysis use the certified export.\n"
            )
    else:
        certified_block = f"""  Risk band:              {band}
  Model probability:      {prob:.1%}
  Champion threshold:     {float(register.get('threshold', 0.5)):.3f}
  Score source:           live inference pipeline
"""
        pipeline_block = f"""  Primary tri_ensemble score: {routed.get('primary_prob', 0):.4f}
  Inference route:        {routed.get('route', 'tri_only')}
  RNN score (if used):    {f"{routed.get('rnn_prob'):.4f}" if routed.get('rnn_prob') is not None else "N/A"}
  Reference RF score:     {f"{pred.get('reference_prob'):.4f}" if pred.get('reference_prob') is not None else "N/A"}
  Model disagreement:     {"Yes — manual review advised" if pred.get('disagree') else "No"}
"""

    diag_lines = []
    for i in (1, 2, 3):
        d = silver.get(f"diag_{i}") or row.get(f"diag_{i}")
        if _fmt(d, "") not in ("", "Not recorded"):
            diag_lines.append(f"  · ICD-9 {i}: {_fmt(d)}")
    if not diag_lines:
        d1 = _fmt(row.get("diag_1"))
        diag_lines = [f"  · Primary diagnosis (ICD-9): {d1}"]

    med_lines = [f"  · {m}" for m in _active_medications(silver)]
    lab_lines = [f"  · {ln}" for ln in _lab_line(silver, row)]

    actual_readmit = silver.get("readmitted")
    outcome_line = ""
    if actual_readmit and _fmt(actual_readmit) not in ("Not recorded",):
        outcome_line = f"\nHistorical outcome (dataset): readmitted = {_fmt(actual_readmit)}"

    similar = pred.get("similar_cohort") or "Similar cohort not available."

    report = f"""
══════════════════════════════════════════════════════════════════
        READMISSION RISK — CLINICAL DECISION SUPPORT REPORT
              (Analytics only — not a medical device)
══════════════════════════════════════════════════════════════════
Generated: {now}
Encounter ID: {eid}          Medical record #: {mrn}

──────────────────────────────────────────────────────────────────
PATIENT DEMOGRAPHICS
──────────────────────────────────────────────────────────────────
  Gender:     {_fmt(row.get('gender', silver.get('gender')))}
  Age:        {_fmt(row.get('age', silver.get('age')))}
  Race:       {_fmt(row.get('race', silver.get('race')))}

──────────────────────────────────────────────────────────────────
ENCOUNTER SUMMARY
──────────────────────────────────────────────────────────────────
  Admission type:     {_code_label(row.get('admission_type_id', silver.get('admission_type_id')), ADMISSION_TYPE)}
  Admission source:   {_code_label(row.get('admission_source_id', silver.get('admission_source_id')), ADMISSION_SOURCE)}
  Discharge disposition: {_code_label(row.get('discharge_disposition_id', silver.get('discharge_disposition_id')), DISCHARGE_DISPOSITION)}
  Length of stay:     {_fmt(row.get('time_in_hospital', silver.get('time_in_hospital')))} days
  Diagnoses coded:    {_fmt(row.get('number_diagnoses', silver.get('number_diagnoses')))}

──────────────────────────────────────────────────────────────────
UTILIZATION HISTORY (PRIOR TO / INCLUDING INDEX VISIT)
──────────────────────────────────────────────────────────────────
  Outpatient visits:   {_fmt(row.get('number_outpatient', silver.get('number_outpatient')))}
  Emergency visits:    {_fmt(row.get('number_emergency', silver.get('number_emergency')))}
  Inpatient visits:    {_fmt(row.get('number_inpatient', silver.get('number_inpatient')))}
  Total visits (12 mo): {_fmt(row.get('total_visits', silver.get('total_visits')))}

──────────────────────────────────────────────────────────────────
DIAGNOSES
──────────────────────────────────────────────────────────────────
{chr(10).join(diag_lines)}

──────────────────────────────────────────────────────────────────
MEDICATIONS & DIABETES MANAGEMENT
──────────────────────────────────────────────────────────────────
  Diabetes medication prescribed: {_fmt(row.get('diabetesMed', silver.get('diabetesMed')))}
  Medication change this visit:   {_fmt(row.get('change', silver.get('change')))}
  Total medications on chart:   {_fmt(row.get('num_medications', silver.get('num_medications')))}
  Active med count (feature):     {_fmt(row.get('active_med_count'))}

  Active / documented therapies:
{chr(10).join(med_lines)}

──────────────────────────────────────────────────────────────────
LABORATORY & PROCEDURES
──────────────────────────────────────────────────────────────────
{chr(10).join(lab_lines)}

──────────────────────────────────────────────────────────────────
READMISSION RISK STRATIFICATION (30-DAY)
──────────────────────────────────────────────────────────────────
{certified_block}{divergence_note}{pipeline_block}
  Key risk drivers (model):
{chr(10).join(f"    · {f}" for f in pred.get('top', [])[:5]) or "    · Not available"}

  Similar historical cohort:
    {similar}

──────────────────────────────────────────────────────────────────
CLINICAL IMPRESSION (DECISION SUPPORT NARRATIVE)
──────────────────────────────────────────────────────────────────
{pred.get('text', 'No narrative generated.')}

──────────────────────────────────────────────────────────────────
RECOMMENDED ACTIONS (RULE-BASED CARE PATHWAY HINTS)
──────────────────────────────────────────────────────────────────
{chr(10).join(f"  · {r}" for r in pred.get('recs', []))}

──────────────────────────────────────────────────────────────────
MODEL & GOVERNANCE
──────────────────────────────────────────────────────────────────
  Served primary model: {register.get('champion_model', '—')}
  Reference model: {register.get('reference_model', 'rf')}
  Explanation source: {pred.get('model_id', '—')}
  Intended use: {register.get('intended_use', 'Analytics decision-support only')}{outcome_line}

──────────────────────────────────────────────────────────────────
DISCLAIMER
──────────────────────────────────────────────────────────────────
This report is generated by an analytics decision-support system.
It is NOT a medical device and must NOT be used as the sole basis
for clinical decisions. All findings require review by a licensed
clinician. Do not use for diagnosis or prescribing.
══════════════════════════════════════════════════════════════════
""".strip()
    return report


def _diag_html(silver: dict, row: dict) -> str:
    items = []
    d1 = silver.get("diag_1") or row.get("diag_1")
    if _fmt(d1, "") not in ("", "Not recorded"):
        items.append(f"<li>Primary: {html.escape(_fmt(d1))}</li>")
    if silver.get("diag_2") and _fmt(silver.get("diag_2"), "") not in ("", "Not recorded"):
        items.append(f"<li>Secondary: {html.escape(_fmt(silver.get('diag_2')))}</li>")
    if silver.get("diag_3") and _fmt(silver.get("diag_3"), "") not in ("", "Not recorded"):
        items.append(f"<li>Tertiary: {html.escape(_fmt(silver.get('diag_3')))}</li>")
    return "".join(items) or "<li>Not recorded</li>"


def render_clinical_report(row: dict, pred: dict, register: dict, role: str = "clinician") -> None:
    from streamlit_app.rbac import ids_policy, mask_record_ids
    from streamlit_app.rbac_auth import validate_role

    role = validate_role(role)
    can_ids, mask_patient = ids_policy(role)
    row = mask_record_ids(dict(row), role) or {}
    eid = row.get("encounter_id") or st.session_state.get("selected_encounter_id")
    silver = load_silver_encounter(eid) if eid and can_ids else {}
    if mask_patient and isinstance(silver, dict):
        silver = dict(silver)
        silver.pop("patient_nbr", None)

    report_text = build_report_text(row, pred, register, silver, role=role)

    st.markdown("### Clinical decision support report")
    st.caption("Structured encounter summary with model-assisted readmission risk narrative.")
    if mask_patient:
        st.caption("RBAC: patient number (MRN) is masked for Clinician role.")
    if not can_ids:
        st.warning("RBAC: identifiers are hidden for your role.")

    expanded_key = f"clinical_report_expanded_{eid or 'current'}"
    reading_mode_key = f"clinical_report_reading_{eid or 'current'}"

    col_dl, col_controls = st.columns([1, 3])
    with col_dl:
        st.download_button(
            label="Download report (.txt)",
            data=report_text,
            file_name=f"readmission_report_{eid or 'encounter'}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col_controls:
        left, right = st.columns([1, 1])
        with left:
            expanded = st.toggle(
                "Expand report",
                value=st.session_state.get(expanded_key, False),
                key=expanded_key,
                help="Open or minimize the full doctor-style report.",
            )
        with right:
            reading_mode = st.toggle(
                "Reading mode",
                value=st.session_state.get(reading_mode_key, False),
                key=reading_mode_key,
                help="Larger typography and spacing for easier review.",
            )

    band = pred["band"]
    band_color = {"High": "#EF4444", "Medium": "#F59E0B", "Low": "#22C55E"}[band]
    report_class = "clinical-report clinical-report-reading" if reading_mode else "clinical-report"
    mrn_display = "MASKED" if (not can_ids or mask_patient) else str(row.get("patient_nbr", silver.get("patient_nbr", "—")))
    eid_display = "REDACTED" if not can_ids else str(eid or "—")

    html_report = f"""
    <div class="{report_class}">
        <div class="cr-header">
            <div class="cr-hospital">Hospital Readmission Analytics</div>
            <div class="cr-title">Clinical Decision Support Report</div>
            <div class="cr-meta">Encounter {html.escape(eid_display)} · MRN {html.escape(mrn_display)}</div>
        </div>

        <div class="cr-section">
            <div class="cr-section-title">Patient demographics</div>
            <div class="cr-grid">
                <div><span class="cr-label">Gender</span><span class="cr-val">{html.escape(_fmt(row.get('gender', silver.get('gender'))))}</span></div>
                <div><span class="cr-label">Age</span><span class="cr-val">{html.escape(_fmt(row.get('age', silver.get('age'))))}</span></div>
                <div><span class="cr-label">Race</span><span class="cr-val">{html.escape(_fmt(row.get('race', silver.get('race'))))}</span></div>
                <div><span class="cr-label">Length of stay</span><span class="cr-val">{html.escape(_fmt(row.get('time_in_hospital', silver.get('time_in_hospital'))))} days</span></div>
            </div>
        </div>

        <div class="cr-section">
            <div class="cr-section-title">Admission & utilization</div>
            <p class="cr-prose">{html.escape(_code_label(row.get('admission_type_id', silver.get('admission_type_id')), ADMISSION_TYPE))}. Source: {html.escape(_code_label(row.get('admission_source_id', silver.get('admission_source_id')), ADMISSION_SOURCE))}. Discharged: {html.escape(_code_label(row.get('discharge_disposition_id', silver.get('discharge_disposition_id')), DISCHARGE_DISPOSITION))}.</p>
            <p class="cr-prose">Prior utilization — outpatient: {_fmt(row.get('number_outpatient', silver.get('number_outpatient')))}, emergency: {_fmt(row.get('number_emergency', silver.get('number_emergency')))}, inpatient: {_fmt(row.get('number_inpatient', silver.get('number_inpatient')))}, total visits (12 mo): {_fmt(row.get('total_visits', silver.get('total_visits')))}.</p>
        </div>

        <div class="cr-section">
            <div class="cr-section-title">Diagnoses (ICD-9)</div>
            <ul class="cr-list">
                {_diag_html(silver, row)}
            </ul>
        </div>

        <div class="cr-section">
            <div class="cr-section-title">Medications & diabetes care</div>
            <p class="cr-prose">Diabetes meds: {html.escape(_fmt(row.get('diabetesMed', silver.get('diabetesMed'))))}. Change this visit: {html.escape(_fmt(row.get('change', silver.get('change'))))}. Total medications: {html.escape(_fmt(row.get('num_medications', silver.get('num_medications'))))}.</p>
            <ul class="cr-list">
                {''.join(f'<li>{html.escape(m)}</li>' for m in _active_medications(silver))}
            </ul>
        </div>

        <div class="cr-section">
            <div class="cr-section-title">Laboratory</div>
            <ul class="cr-list">
                {''.join(f'<li>{html.escape(ln)}</li>' for ln in _lab_line(silver, row))}
            </ul>
        </div>

        <div class="cr-risk-box" style="border-color:{band_color}">
            <div class="cr-section-title">30-day readmission risk</div>
            <div class="cr-risk-band" style="color:{band_color}">{html.escape(band)} risk · {pred['prob']:.1%}</div>
            <p class="cr-prose">{html.escape(pred.get('text', ''))}</p>
        </div>

        <div class="cr-section">
            <div class="cr-section-title">Recommendations</div>
            <ul class="cr-list">
                {''.join(f'<li>{html.escape(r)}</li>' for r in pred.get('recs', []))}
            </ul>
        </div>

        <div class="cr-disclaimer">
            Analytics decision-support only — not a medical device. Not for standalone clinical decisions.
        </div>
    </div>
    """

    with st.expander("Open full report", expanded=expanded):
        st.markdown(html_report, unsafe_allow_html=True)

    with st.expander("View full plain-text report"):
        st.code(report_text, language=None)
