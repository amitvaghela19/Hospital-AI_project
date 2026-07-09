#!/usr/bin/env python3
"""Build single Power BI master CSV from certified exports (stacked record_type rows)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EXPORTS = ROOT / "data" / "exports"
OUT_PATH = EXPORTS / "powerbi_dashboard_master.csv"
DATAFILE = ROOT / "datafile.txt"


def _pct_label(value: float, decimals: int = 1) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value) * 100:.{decimals}f}%"


def _upsert_registry(role: str, zone: str, rel_path: str, description: str) -> None:
    lines = DATAFILE.read_text(encoding="utf-8").splitlines()
    new_line = f"{role}|{zone}|{rel_path}|{description}"
    out, found = [], False
    for line in lines:
        if line.startswith("#") or not line.strip():
            out.append(line)
            continue
        parts = line.split("|")
        if len(parts) >= 3 and parts[0].strip() == role and parts[2].strip() == rel_path:
            out.append(new_line)
            found = True
        else:
            out.append(line)
    if not found:
        out.append(new_line)
    DATAFILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def _empty_row() -> dict:
    return {
        "record_type": "",
        "row_key": "",
        "page_filter": "",
        "sort_order": 0,
        "chart_category": "",
        "chart_value": np.nan,
        "chart_rate_pct": np.nan,
        "chart_rate_label": "",
        "chart_count": np.nan,
        "enc_encounter_id": np.nan,
        "enc_patient_nbr": np.nan,
        "enc_age": np.nan,
        "enc_gender": "",
        "enc_race": "",
        "enc_admission_type_id": np.nan,
        "enc_time_in_hospital": np.nan,
        "enc_diag_1": "",
        "enc_number_inpatient": np.nan,
        "enc_number_emergency": np.nan,
        "enc_number_outpatient": np.nan,
        "enc_total_visits": np.nan,
        "enc_readmit_30d": np.nan,
        "enc_readmit_any": np.nan,
        "enc_readmitted": "",
        "enc_active_med_count": np.nan,
        "enc_readmit_label": "",
        "enc_age_band": "",
        "enc_los_band": "",
        "enc_frequent_visitor": 0,
        "enc_has_risk_score": 0,
        "enc_risk_band": "",
        "enc_alert_high_risk_label": "",
        "enc_y_prob": np.nan,
        "enc_y_pred": np.nan,
        "enc_top_factors": "",
        "enc_shadow_prob": np.nan,
        "enc_shadow_disagree": np.nan,
        "mtx_model": "",
        "mtx_horizon": "",
        "mtx_split": "",
        "mtx_threshold": np.nan,
        "mtx_train_size": np.nan,
        "mtx_val_size": np.nan,
        "mtx_test_size": np.nan,
        "mtx_ensemble": "",
        "mtx_accuracy": np.nan,
        "mtx_precision": np.nan,
        "mtx_recall": np.nan,
        "mtx_f1": np.nan,
        "mtx_roc_auc": np.nan,
        "mtx_is_primary_protocol": 0,
        "mtx_model_category": "",
        "mtx_recall_pct": np.nan,
        "mtx_roc_auc_pct": np.nan,
        "mtx_f1_pct": np.nan,
        "mtx_metrics_label": "",
        "avp_idx": np.nan,
        "avp_y_true": np.nan,
        "avp_y_pred": np.nan,
        "avp_y_prob": np.nan,
        "avp_actual_cum_rate": np.nan,
        "avp_predicted_cum_rate": np.nan,
        "dq_check": "",
        "dq_dimension": "",
        "dq_passed": "",
        "dq_passed_label": "",
        "dq_detail": "",
        "dq_critical": "",
        "dq_run_id": "",
        "kpi_total_patients": np.nan,
        "kpi_total_encounters": np.nan,
        "kpi_readmission_rate": np.nan,
        "kpi_readmission_rate_pct": "",
        "kpi_avg_los": np.nan,
        "kpi_high_risk_rate": np.nan,
        "kpi_high_risk_rate_pct": "",
        "kpi_champion_model": "",
        "kpi_champion_recall": np.nan,
        "kpi_champion_recall_pct": "",
        "kpi_champion_roc_auc": np.nan,
        "kpi_champion_roc_auc_pct": "",
    }


def _load_kpi() -> dict:
    path = EXPORTS / "kpi_snapshot.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    readmit = pd.read_csv(EXPORTS / "mart_readmission.csv")
    return {
        "total_patients": int(readmit["patient_nbr"].nunique()),
        "total_encounters": int(len(readmit)),
        "readmission_rate_30d": float(readmit["readmit_30d"].mean()),
        "avg_los": float(readmit["time_in_hospital"].mean()),
        "high_risk_rate": np.nan,
        "champion_model": "",
        "champion_recall": np.nan,
        "champion_roc_auc": np.nan,
    }


def _kpi_fields(kpi: dict) -> dict:
    rr = float(kpi.get("readmission_rate_30d", np.nan))
    cr = float(kpi.get("champion_recall", np.nan))
    ca = float(kpi.get("champion_roc_auc", np.nan))
    hr = float(kpi.get("high_risk_rate", np.nan))
    return {
        "kpi_total_patients": int(kpi.get("total_patients", 0)),
        "kpi_total_encounters": int(kpi.get("total_encounters", 0)),
        "kpi_readmission_rate": rr,
        "kpi_readmission_rate_pct": _pct_label(rr),
        "kpi_avg_los": round(float(kpi.get("avg_los", np.nan)), 2) if pd.notna(kpi.get("avg_los")) else np.nan,
        "kpi_high_risk_rate": hr,
        "kpi_high_risk_rate_pct": _pct_label(hr) if pd.notna(hr) else "",
        "kpi_champion_model": str(kpi.get("champion_model", "")),
        "kpi_champion_recall": cr,
        "kpi_champion_recall_pct": _pct_label(cr) if pd.notna(cr) else "",
        "kpi_champion_roc_auc": ca,
        "kpi_champion_roc_auc_pct": _pct_label(ca) if pd.notna(ca) else "",
    }


def _chart_rows_from_agg(
    categories: list,
    rates: list,
    counts: list,
    record_type: str,
    page: str,
) -> list[dict]:
    rows = []
    for i, (cat, rate, cnt) in enumerate(zip(categories, rates, counts)):
        row = _empty_row()
        rate = float(rate)
        row.update({
            "record_type": record_type,
            "row_key": f"{record_type}_{cat}",
            "page_filter": page,
            "sort_order": i,
            "chart_category": str(cat),
            "chart_value": rate,
            "chart_rate_pct": round(rate * 100, 2) if rate <= 1 else round(rate, 4),
            "chart_rate_label": _pct_label(rate) if rate <= 1 else str(rate),
            "chart_count": int(cnt),
        })
        rows.append(row)
    return rows


def _chart_diag_rows(readmit: pd.DataFrame, n: int = 10) -> list[dict]:
    g = (
        readmit.groupby("diag_1", dropna=False)["readmit_30d"]
        .agg(rate="mean", count="count")
        .reset_index()
        .sort_values("count", ascending=False)
        .head(n)
    )
    return _chart_rows_from_agg(
        g["diag_1"].astype(str).tolist(),
        g["rate"].tolist(),
        g["count"].tolist(),
        "CHART_DIAG",
        "2",
    )


def _visit_bucket(v: float) -> str:
    v = float(v) if pd.notna(v) else 0
    if v <= 0:
        return "0 visits"
    if v <= 2:
        return "1-2 visits"
    if v <= 5:
        return "3-5 visits"
    return "6+ visits"


def _chart_visit_rows(readmit: pd.DataFrame) -> list[dict]:
    tmp = readmit.copy()
    tmp["_bucket"] = tmp["total_visits"].apply(_visit_bucket)
    order = ["0 visits", "1-2 visits", "3-5 visits", "6+ visits"]
    g = tmp.groupby("_bucket", dropna=False)["readmit_30d"].agg(rate="mean", count="count").reindex(order).dropna(subset=["rate"])
    return _chart_rows_from_agg(g.index.tolist(), g["rate"].tolist(), g["count"].tolist(), "CHART_VISIT", "3")


def _chart_medication_rows(readmit: pd.DataFrame) -> list[dict]:
    return _chart_rows(readmit, "active_med_count", "CHART_MEDICATION", "3", sort_key="active_med_count")


def _chart_feature_rows() -> list[dict]:
    reg_path = ROOT / "models" / "champion_register.json"
    if not reg_path.exists():
        return []
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    features = reg.get("top_features", [])
    rows = []
    for i, feat in enumerate(features):
        row = _empty_row()
        val = float(feat.get("mean_abs_shap", 0))
        name = str(feat.get("feature", "")).replace("num__", "")
        row.update({
            "record_type": "CHART_FEATURE",
            "row_key": f"CHART_FEATURE_{i}_{name}",
            "page_filter": "4",
            "sort_order": i,
            "chart_category": name,
            "chart_value": val,
            "chart_rate_pct": round(val * 100, 2),
            "chart_rate_label": f"{val:.3f}",
            "chart_count": np.nan,
        })
        rows.append(row)
    return rows


def _chart_pred_bucket_rows(risk: pd.DataFrame) -> list[dict]:
    if len(risk) == 0 or "y_prob" not in risk.columns:
        return []
    probs = risk["y_prob"].dropna()
    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
    labels = ["0.0-0.1", "0.1-0.2", "0.2-0.3", "0.3-0.4", "0.4-0.5", "0.5-0.6", "0.6-0.7", "0.7-0.8", "0.8-0.9", "0.9-1.0"]
    cats = pd.cut(probs, bins=bins, labels=labels, right=False)
    g = cats.value_counts().sort_index()
    rows = []
    for i, (cat, cnt) in enumerate(g.items()):
        row = _empty_row()
        row.update({
            "record_type": "CHART_PRED_BUCKET",
            "row_key": f"CHART_PRED_{cat}",
            "page_filter": "4",
            "sort_order": i,
            "chart_category": str(cat),
            "chart_value": np.nan,
            "chart_rate_pct": np.nan,
            "chart_rate_label": "",
            "chart_count": int(cnt),
        })
        rows.append(row)
    return rows


def _chart_gender_rows(readmit: pd.DataFrame, page: str = "1,2") -> list[dict]:
    from streamlit_app.gender_labels import GENDER_CHART_ORDER, prepare_gender_readmit_stats

    stats = prepare_gender_readmit_stats(readmit)
    if stats.empty:
        return []
    return _chart_rows_from_agg(
        stats["gender"].astype(str).tolist(),
        stats["readmit_30d"].tolist(),
        stats["count"].astype(int).tolist(),
        "CHART_GENDER",
        page,
    )


def _chart_rows(df: pd.DataFrame, group_col: str, record_type: str, page: str, sort_key=None) -> list[dict]:
    if group_col not in df.columns:
        return []
    g = (
        df.groupby(group_col, dropna=False)["readmit_30d"]
        .agg(rate="mean", count="count")
        .reset_index()
    )
    if sort_key:
        g = g.sort_values(sort_key)
    rows = []
    for i, r in g.iterrows():
        row = _empty_row()
        cat = str(r[group_col])
        rate = float(r["rate"])
        row.update({
            "record_type": record_type,
            "row_key": f"{record_type}_{cat}",
            "page_filter": page,
            "sort_order": int(i),
            "chart_category": cat,
            "chart_value": rate,
            "chart_rate_pct": round(rate * 100, 2),
            "chart_rate_label": _pct_label(rate),
            "chart_count": int(r["count"]),
        })
        rows.append(row)
    return rows


def build_master_csv(exports_dir: Path | None = None, out_path: Path | None = None) -> pd.DataFrame:
    exports_dir = exports_dir or EXPORTS
    out_path = out_path or OUT_PATH

    readmit = pd.read_csv(exports_dir / "mart_readmission.csv")
    risk_path = exports_dir / "mart_clinical_risk.csv"
    risk = pd.read_csv(risk_path) if risk_path.exists() else pd.DataFrame()
    matrix = pd.read_csv(exports_dir / "experiments_matrix.csv")
    avp = pd.read_csv(exports_dir / "mart_actual_vs_predicted.csv")
    dq = pd.read_csv(exports_dir / "mart_dq_scorecard.csv")
    kpi = _load_kpi()
    kpi_cols = _kpi_fields(kpi)

    shadow = pd.DataFrame()
    shadow_path = exports_dir / "mart_shadow_disagreement.csv"
    if shadow_path.exists():
        shadow = pd.read_csv(shadow_path)

    enc = readmit.copy()
    if len(risk):
        risk_cols = [c for c in risk.columns if c not in enc.columns or c == "encounter_id"]
        enc = enc.merge(risk[risk_cols], on="encounter_id", how="left")
    if len(shadow):
        enc = enc.merge(shadow, on="encounter_id", how="left")

    enc["enc_frequent_visitor"] = (
        (enc["number_inpatient"].fillna(0) >= 2) | (enc["total_visits"].fillna(0) >= 3)
    ).astype(int)
    enc["enc_readmit_label"] = enc["readmit_30d"].map({1: "Yes", 0: "No", True: "Yes", False: "No"}).fillna("No")
    enc["enc_age_band"] = enc["age"].astype(str)
    enc["enc_los_band"] = enc["time_in_hospital"].astype(str)

    has_risk = enc["risk_band"].notna() if "risk_band" in enc.columns else pd.Series(False, index=enc.index)
    enc["enc_has_risk_score"] = has_risk.astype(int)
    enc["enc_risk_band"] = enc["risk_band"].fillna("Not scored") if "risk_band" in enc.columns else "Not scored"
    if "alert_high_risk" in enc.columns:
        enc["enc_alert_high_risk_label"] = np.where(
            ~has_risk,
            "Not scored",
            np.where(enc["risk_band"] == "High", "High", np.where(enc["risk_band"] == "Medium", "Medium", "Low")),
        )
    else:
        enc["enc_alert_high_risk_label"] = "Not scored"

    factor_cols = [c for c in enc.columns if c.startswith("top_factor_")]
    if factor_cols:
        enc["enc_top_factors"] = enc[factor_cols].fillna("").astype(str).agg(" | ".join, axis=1)
    else:
        enc["enc_top_factors"] = ""

    rows: list[dict] = []

    for i, r in enc.iterrows():
        row = _empty_row()
        row.update(kpi_cols)
        row.update({
            "record_type": "ENCOUNTER",
            "row_key": f"ENC_{r['encounter_id']}",
            "page_filter": "1,2,3",
            "sort_order": int(i),
            "enc_encounter_id": r.get("encounter_id"),
            "enc_patient_nbr": r.get("patient_nbr"),
            "enc_age": r.get("age"),
            "enc_gender": r.get("gender", ""),
            "enc_race": r.get("race", ""),
            "enc_admission_type_id": r.get("admission_type_id"),
            "enc_time_in_hospital": r.get("time_in_hospital"),
            "enc_diag_1": r.get("diag_1", ""),
            "enc_number_inpatient": r.get("number_inpatient"),
            "enc_number_emergency": r.get("number_emergency"),
            "enc_number_outpatient": r.get("number_outpatient"),
            "enc_total_visits": r.get("total_visits"),
            "enc_readmit_30d": r.get("readmit_30d"),
            "enc_readmit_any": r.get("readmit_any"),
            "enc_readmitted": r.get("readmitted", ""),
            "enc_active_med_count": r.get("active_med_count"),
            "enc_readmit_label": r.get("enc_readmit_label"),
            "enc_age_band": r.get("enc_age_band"),
            "enc_los_band": r.get("enc_los_band"),
            "enc_frequent_visitor": int(r.get("enc_frequent_visitor", 0)),
            "enc_has_risk_score": int(r.get("enc_has_risk_score", 0)),
            "enc_risk_band": r.get("enc_risk_band"),
            "enc_alert_high_risk_label": r.get("enc_alert_high_risk_label"),
            "enc_y_prob": r.get("y_prob", np.nan),
            "enc_y_pred": r.get("y_pred", np.nan),
            "enc_top_factors": r.get("enc_top_factors", ""),
            "enc_shadow_prob": r.get("shadow_prob", np.nan),
            "enc_shadow_disagree": int(r["disagree"]) if pd.notna(r.get("disagree", np.nan)) else np.nan,
        })
        rows.append(row)

    rows.extend(_chart_rows(readmit, "age", "CHART_AGE", "2", sort_key="age"))
    rows.extend(_chart_gender_rows(readmit))
    rows.extend(_chart_diag_rows(readmit))
    rows.extend(_chart_visit_rows(readmit))
    rows.extend(_chart_medication_rows(readmit))
    rows.extend(_chart_feature_rows())
    rows.extend(_chart_pred_bucket_rows(risk))
    rows.extend(_chart_rows(readmit, "time_in_hospital", "CHART_LOS", "3", sort_key="time_in_hospital"))
    if "admission_type_id" in readmit.columns:
        rows.extend(_chart_rows(readmit, "admission_type_id", "CHART_ADMISSION", "3"))

    if len(risk) and "risk_band" in risk.columns:
        scored = readmit.merge(risk[["encounter_id", "risk_band"]], on="encounter_id", how="inner")
        rows.extend(_chart_rows(scored, "risk_band", "CHART_RISK_BAND", "4"))

    if len(shadow):
        disagree_rate = float(shadow["disagree"].mean())
        row = _empty_row()
        row.update({
            "record_type": "CHART_SHADOW",
            "row_key": "CHART_SHADOW",
            "page_filter": "4",
            "sort_order": 0,
            "chart_category": "Shadow disagreement rate",
            "chart_value": disagree_rate,
            "chart_rate_pct": round(disagree_rate * 100, 2),
            "chart_rate_label": _pct_label(disagree_rate),
            "chart_count": len(shadow),
        })
        rows.append(row)

    for i, r in matrix.iterrows():
        row = _empty_row()
        is_primary = (r["horizon"] == "30d") and (r["split"] == "70/15/15")
        is_ens = str(r.get("ensemble", False)).lower() in ("true", "1", "yes")
        recall = float(r["recall"])
        roc = float(r["roc_auc"])
        f1 = float(r["f1"])
        row.update({
            "record_type": "MATRIX",
            "row_key": f"MTX_{i}_{r['model']}_{r['horizon']}_{r['split']}",
            "page_filter": "5",
            "sort_order": int(i),
            "mtx_model": r["model"],
            "mtx_horizon": r["horizon"],
            "mtx_split": r["split"],
            "mtx_threshold": r["threshold"],
            "mtx_train_size": r["train_size"],
            "mtx_val_size": r["val_size"],
            "mtx_test_size": r["test_size"],
            "mtx_ensemble": "Yes" if is_ens else "No",
            "mtx_accuracy": r["accuracy"],
            "mtx_precision": r["precision"],
            "mtx_recall": recall,
            "mtx_f1": f1,
            "mtx_roc_auc": roc,
            "mtx_is_primary_protocol": int(is_primary),
            "mtx_model_category": "ensemble" if is_ens else "base",
            "mtx_recall_pct": round(recall * 100, 2),
            "mtx_roc_auc_pct": round(roc * 100, 2),
            "mtx_f1_pct": round(f1 * 100, 2),
            "mtx_metrics_label": (
                f"{r['model']} | recall={_pct_label(recall)} roc_auc={_pct_label(roc)} f1={_pct_label(f1)}"
            ),
        })
        rows.append(row)

    for i, r in avp.iterrows():
        row = _empty_row()
        row.update({
            "record_type": "ACTUAL_VS_PRED",
            "row_key": f"AVP_{i}",
            "page_filter": "5",
            "sort_order": int(i),
            "avp_idx": r.get("idx"),
            "avp_y_true": r.get("y_true"),
            "avp_y_pred": r.get("y_pred"),
            "avp_y_prob": r.get("y_prob"),
            "avp_actual_cum_rate": r.get("actual_cum_rate"),
            "avp_predicted_cum_rate": r.get("predicted_cum_rate"),
        })
        rows.append(row)

    for i, r in dq.iterrows():
        row = _empty_row()
        passed = bool(r.get("passed"))
        row.update({
            "record_type": "DQ",
            "row_key": f"DQ_{i}_{r.get('check', '')}",
            "page_filter": "1",
            "sort_order": int(i),
            "dq_check": r.get("check", ""),
            "dq_dimension": r.get("dimension", ""),
            "dq_passed": "True" if passed else "False",
            "dq_passed_label": "Pass" if passed else "Fail",
            "dq_detail": r.get("detail", ""),
            "dq_critical": str(r.get("critical", "")),
            "dq_run_id": str(r.get("run_id", "")),
        })
        rows.append(row)

    kpi_row = _empty_row()
    kpi_row.update(kpi_cols)
    kpi_row.update({
        "record_type": "KPI",
        "row_key": "KPI_0",
        "page_filter": "1",
        "sort_order": 0,
    })
    rows.append(kpi_row)

    master = pd.DataFrame(rows)
    exports_dir.mkdir(parents=True, exist_ok=True)
    master.to_csv(out_path, index=False)
    _upsert_registry(
        "mart",
        "export",
        "data/exports/powerbi_dashboard_master.csv",
        "Power BI single-file dashboard master (stacked record_type)",
    )
    return master


def main() -> int:
    master = build_master_csv()
    counts = master["record_type"].value_counts().to_dict()
    print(f"Wrote {OUT_PATH}")
    print(f"Shape: {master.shape[0]} rows x {master.shape[1]} columns")
    print("record_type counts:", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
