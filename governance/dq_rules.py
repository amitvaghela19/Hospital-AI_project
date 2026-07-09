from __future__ import annotations

PLACEHOLDERS = {"?", "Unknown", "unknown", "-", ""}
ALLOWED_GENDERS = {"Female", "Male", "Unknown/Invalid"}


def validate_inference_row(row: dict) -> dict:
    """Validate a single patient row before live scoring."""
    failures: list[str] = []

    los = row.get("time_in_hospital")
    if los is not None and str(los).strip() not in PLACEHOLDERS:
        try:
            los_v = float(los)
            if not (1 <= los_v <= 14):
                failures.append("los_range: time_in_hospital must be between 1 and 14")
        except (TypeError, ValueError):
            failures.append("los_range: time_in_hospital must be numeric")

    gender = row.get("gender")
    if gender is not None and str(gender).strip() not in PLACEHOLDERS:
        if str(gender) not in ALLOWED_GENDERS:
            failures.append(f"gender_domain: invalid gender '{gender}'")

    for key in ("total_visits", "number_inpatient", "num_medications"):
        val = row.get(key)
        if val is None or (isinstance(val, float) and val != val):
            failures.append(f"completeness: {key} is required")

    for key, val in row.items():
        if val is None:
            continue
        if str(val).strip() in PLACEHOLDERS and key in (
            "time_in_hospital", "total_visits", "num_medications", "gender", "age"
        ):
            failures.append(f"validity: placeholder value in {key}")

    return {"passed": len(failures) == 0, "failures": failures}


def batch_dq_checks(raw_df) -> list[dict]:
    """Build DQ check records for Phase 0 batch ingest (compatible list of dicts)."""
    import pandas as pd
    from datetime import datetime, timezone

    dq: list[dict] = []

    def add(name, dimension, passed, detail, critical=True):
        dq.append({
            "check": name,
            "dimension": dimension,
            "passed": bool(passed),
            "detail": detail,
            "critical": critical,
        })

    add("row_count_positive", "completeness", len(raw_df) > 0, f"rows={len(raw_df)}")
    add("has_encounter_id", "validity", "encounter_id" in raw_df.columns, "encounter_id present")
    add("has_readmitted", "validity", "readmitted" in raw_df.columns, "readmitted present")
    if "encounter_id" in raw_df.columns:
        nuniq = raw_df["encounter_id"].nunique()
        add("encounter_id_unique", "uniqueness", nuniq == len(raw_df), f"unique={nuniq} total={len(raw_df)}")
    if "readmitted" in raw_df.columns:
        allowed = {"NO", "<30", ">30"}
        vals = set(raw_df["readmitted"].astype(str).unique())
        add("readmitted_domain", "validity", vals.issubset(allowed), f"values={sorted(vals)}")
    if "time_in_hospital" in raw_df.columns:
        los = pd.to_numeric(raw_df["time_in_hospital"], errors="coerce")
        add("los_range", "consistency", ((los >= 1) & (los <= 14)).mean() > 0.95, f"mean_los={los.mean():.2f}")
    if "gender" in raw_df.columns:
        g = set(raw_df["gender"].astype(str).unique())
        add("gender_domain", "validity", g.issubset(ALLOWED_GENDERS), f"gender={g}")
    add("ingest_timestamp", "timeliness", True, datetime.now(timezone.utc).isoformat())
    return dq
