from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from streamlit_app import ROOT

EXPORTS = ROOT / "data" / "exports"


@st.cache_data(show_spinner=False)
def load_kpi_snapshot() -> dict:
    path = EXPORTS / "kpi_snapshot.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_master_csv() -> pd.DataFrame:
    path = EXPORTS / "powerbi_dashboard_master.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


@st.cache_data(show_spinner=False)
def load_mart(name: str) -> pd.DataFrame:
    path = EXPORTS / f"{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def load_experiments_matrix() -> pd.DataFrame:
    return load_mart("experiments_matrix")


@st.cache_data(show_spinner=False)
def load_gold_features() -> pd.DataFrame:
    path = ROOT / "data" / "lake" / "gold" / "model_features.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def load_model_card() -> dict:
    path = ROOT / "models" / "model_card.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_rbac() -> dict:
    path = ROOT / "data" / "nosql" / "rbac_roles.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def filter_master(record_type: str) -> pd.DataFrame:
    df = load_master_csv()
    if df.empty or "record_type" not in df.columns:
        return df
    return df[df["record_type"] == record_type].copy()


def clinical_risk_mart_30d() -> pd.DataFrame:
    """Certified clinical risk mart, preferring 30d horizon when present."""
    mart = load_mart("mart_clinical_risk")
    if mart.empty:
        return mart
    if "horizon" in mart.columns:
        sub = mart[mart["horizon"].astype(str).str.lower() == "30d"]
        if not sub.empty:
            return sub
    return mart


def get_certified_encounter(encounter_id: int) -> dict | None:
    """Return certified y_prob, risk_band, and top factors from mart_clinical_risk."""
    mart = clinical_risk_mart_30d()
    if mart.empty or "encounter_id" not in mart.columns:
        return None
    sub = mart[mart["encounter_id"].astype(str) == str(int(encounter_id))]
    if sub.empty:
        return None
    r = sub.iloc[0]
    top_factors: list[str] = []
    for i in range(1, 6):
        col = f"top_factor_{i}"
        if col in r.index and pd.notna(r.get(col)):
            s = str(r[col]).strip()
            if s:
                top_factors.append(s.replace("num__", ""))
    out: dict = {
        "encounter_id": int(r["encounter_id"]) if pd.notna(r.get("encounter_id")) else int(encounter_id),
        "y_prob": float(r["y_prob"]) if "y_prob" in r and pd.notna(r["y_prob"]) else None,
        "risk_band": str(r["risk_band"]) if "risk_band" in r and pd.notna(r["risk_band"]) else "",
        "top_factors": top_factors,
    }
    if "patient_nbr" in r and pd.notna(r["patient_nbr"]):
        out["patient_nbr"] = int(r["patient_nbr"])
    return out


def rank_encounter_ids_by_certified_risk(encounter_ids: list[int]) -> list[int]:
    """Sort encounter IDs by certified y_prob descending; unscored encounters last."""
    if not encounter_ids:
        return []
    mart = clinical_risk_mart_30d()
    if mart.empty:
        return list(encounter_ids)
    sub = mart[mart["encounter_id"].isin(encounter_ids)].copy()
    if sub.empty:
        return list(encounter_ids)
    sub = sub.sort_values("y_prob", ascending=False, na_position="last")
    ranked = [int(x) for x in sub["encounter_id"].tolist()]
    missing = [eid for eid in encounter_ids if eid not in ranked]
    return ranked + missing


def sort_encounters_by_certified_risk(df: pd.DataFrame) -> pd.DataFrame:
    """Join encounter index rows with certified y_prob and sort highest risk first."""
    if df.empty:
        return df
    mart = clinical_risk_mart_30d()
    if mart.empty or "encounter_id" not in mart.columns:
        return df
    cols = ["encounter_id", "y_prob", "risk_band"]
    cols = [c for c in cols if c in mart.columns]
    merged = df.merge(mart[cols], on="encounter_id", how="left")
    return merged.sort_values("y_prob", ascending=False, na_position="last")


def apply_certified_prediction_overlay(prediction: dict, row: dict) -> dict:
    """
    When encounter exists in mart_clinical_risk, use certified scores for display
    (dashboard-aligned). Keep live pipeline prob in live_prob for comparison.
    """
    from streamlit_app.risk_labels import normalize_risk_band_display

    out = dict(prediction)
    live_prob = float(out.get("prob", 0))
    out["live_prob"] = live_prob

    enc_id = row.get("encounter_id")
    if enc_id is None:
        out["score_source"] = "live_pipeline"
        return out

    certified = get_certified_encounter(int(enc_id))
    if not certified or certified.get("y_prob") is None:
        out["score_source"] = "live_pipeline"
        return out

    cert_prob = float(certified["y_prob"])
    out["certified"] = certified
    out["prob"] = cert_prob
    out["band"] = normalize_risk_band_display(certified.get("risk_band"))
    out["score_source"] = "certified_mart"
    if certified.get("top_factors"):
        out["top"] = certified["top_factors"]
    out["score_divergence"] = abs(live_prob - cert_prob) > 0.05
    return out
