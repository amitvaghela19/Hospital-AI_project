from __future__ import annotations

import pandas as pd

from mcp.common import PATHS, ROOT


def load_mart(name: str = "mart_readmission") -> pd.DataFrame:
    path = ROOT / "data" / "exports" / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Mart not found: {path}")
    return pd.read_csv(path)


def top_high_risk_encounters(n: int = 10) -> list[dict]:
    """
    Return top-N high-risk encounters from `mart_clinical_risk.csv`.
    Sorted by model probability (`y_prob`) descending.
    """
    mart = load_mart("mart_clinical_risk")
    if mart.empty:
        return []

    # Prefer the 30-day horizon when present.
    if "horizon" in mart.columns:
        sub = mart[mart["horizon"].astype(str).str.lower() == "30d"]
        if not sub.empty:
            mart = sub

    if "risk_band" not in mart.columns or "y_prob" not in mart.columns or "encounter_id" not in mart.columns:
        return []

    mart = mart[mart["risk_band"].astype(str).str.lower() == "high"]
    if mart.empty:
        return []

    mart = mart.sort_values("y_prob", ascending=False).head(int(n))

    top_cols = [f"top_factor_{i}" for i in range(1, 6)]
    records: list[dict] = []
    for _, r in mart.iterrows():
        top_factors: list[str] = []
        for c in top_cols:
            v = r.get(c)
            if pd.notna(v):
                s = str(v).strip()
                if s:
                    top_factors.append(s)

        records.append(
            {
                "encounter_id": int(r["encounter_id"]) if pd.notna(r["encounter_id"]) else None,
                "patient_nbr": int(r["patient_nbr"]) if "patient_nbr" in r and pd.notna(r["patient_nbr"]) else None,
                "gender": str(r["gender"]) if "gender" in r and pd.notna(r["gender"]) else "",
                "age": str(r["age"]) if "age" in r and pd.notna(r["age"]) else "",
                "risk_band": str(r["risk_band"]) if pd.notna(r["risk_band"]) else "High",
                "y_prob": float(r["y_prob"]) if pd.notna(r["y_prob"]) else None,
                "top_factors": top_factors,
            }
        )
    return records


def encounter_detail(encounter_id: int, mask_patient_nbr: bool = False) -> dict | None:
    """
    Return encounter-level details from `mart_clinical_risk.csv`.

    Note: routing layer should enforce RBAC; this function includes a `mask_patient_nbr`
    parameter as a defense-in-depth safeguard.
    """
    mart = load_mart("mart_clinical_risk")
    if mart.empty or "encounter_id" not in mart.columns:
        return None

    # Prefer the 30-day horizon when present.
    if "horizon" in mart.columns:
        sub = mart[mart["horizon"].astype(str).str.lower() == "30d"]
        if not sub.empty:
            mart = sub

    sub = mart[mart["encounter_id"].astype(str) == str(encounter_id)]
    if sub.empty:
        return None

    r = sub.iloc[0]
    top_cols = [f"top_factor_{i}" for i in range(1, 6)]
    top_factors: list[str] = []
    for c in top_cols:
        v = r.get(c)
        if pd.notna(v):
            s = str(v).strip()
            if s:
                top_factors.append(s)

    detail = {
        "encounter_id": int(r["encounter_id"]) if pd.notna(r["encounter_id"]) else None,
        "patient_nbr": int(r["patient_nbr"]) if "patient_nbr" in r and pd.notna(r["patient_nbr"]) else None,
        "gender": str(r["gender"]) if "gender" in r and pd.notna(r["gender"]) else "",
        "age": str(r["age"]) if "age" in r and pd.notna(r["age"]) else "",
        "risk_band": str(r["risk_band"]) if "risk_band" in r and pd.notna(r["risk_band"]) else "",
        "y_prob": float(r["y_prob"]) if "y_prob" in r and pd.notna(r["y_prob"]) else None,
        "top_factors": top_factors,
    }
    if mask_patient_nbr:
        detail.pop("patient_nbr", None)
    return detail


def patient_lookup(patient_nbr: str) -> dict:
    """
    Exact-match lookup of patient_nbr in `mart_clinical_risk.csv`.
    Returns found flag, encounter list, and summary fields for chat routing.
    """
    query = str(patient_nbr).strip()
    mart = load_mart("mart_clinical_risk")
    if mart.empty or "patient_nbr" not in mart.columns or "encounter_id" not in mart.columns:
        return {
            "found": False,
            "patient_nbr": query,
            "encounter_count": 0,
            "encounters": [],
        }

    if "horizon" in mart.columns:
        sub = mart[mart["horizon"].astype(str).str.lower() == "30d"]
        if not sub.empty:
            mart = sub

    mask = mart["patient_nbr"].astype(str).str.strip() == query
    sub = mart[mask]
    if sub.empty:
        return {
            "found": False,
            "patient_nbr": query,
            "encounter_count": 0,
            "encounters": [],
        }

    sub = sub.sort_values("encounter_id")
    encounters: list[dict] = []
    for _, r in sub.iterrows():
        encounters.append(
            {
                "encounter_id": int(r["encounter_id"]) if pd.notna(r["encounter_id"]) else None,
                "patient_nbr": int(r["patient_nbr"]) if pd.notna(r["patient_nbr"]) else None,
                "gender": str(r["gender"]) if "gender" in r and pd.notna(r["gender"]) else "",
                "age": str(r["age"]) if "age" in r and pd.notna(r["age"]) else "",
                "risk_band": str(r["risk_band"]) if "risk_band" in r and pd.notna(r["risk_band"]) else "",
                "y_prob": float(r["y_prob"]) if "y_prob" in r and pd.notna(r["y_prob"]) else None,
            }
        )

    return {
        "found": True,
        "patient_nbr": query,
        "encounter_count": len(encounters),
        "encounters": encounters,
    }


def semantic_metric(message: str) -> str | None:
    from mcp.services.dimensional_metrics import dimensional_metric as _dimensional_metric

    dim = _dimensional_metric(message)
    if dim:
        return dim
    msg = message.lower()
    mart = load_mart("mart_readmission")
    if ("readmission" in msg or "readmit" in msg) and (
        "rate" in msg or "percent" in msg or "%" in msg or "what is" in msg or "how many" in msg
    ):
        if "age" in msg:
            g = mart.groupby("age")["readmit_30d"].mean()
            return "Readmission rate by age: " + ", ".join(f"{i}={v:.1%}" for i, v in g.items())
        rate = mart["readmit_30d"].mean()
        n = len(mart)
        return f"The certified 30-day readmission rate is {rate:.1%} ({int(rate * n):,} readmissions / {n:,} encounters)."
    if "length of stay" in msg or "avg los" in msg or ("average" in msg and "stay" in msg):
        los = mart["time_in_hospital"].mean()
        return f"The average length of stay is {los:.1f} days across {len(mart):,} encounters."
    if "total patient" in msg or "how many patient" in msg:
        kpi_path = ROOT / "data" / "exports" / "kpi_snapshot.json"
        if kpi_path.exists():
            import json
            kpi = json.loads(kpi_path.read_text(encoding="utf-8"))
            return f"Total patients: {kpi.get('total_patients', 0):,}; total encounters: {kpi.get('total_encounters', 0):,}."
    return None


def describe_mart(name: str = "mart_readmission") -> str:
    df = load_mart(name)
    return df.describe(include="all").to_string()


def groupby_metric(name: str, column: str, metric: str = "readmit_30d") -> str:
    df = load_mart(name)
    if column not in df.columns or metric not in df.columns:
        return f"Columns {column} or {metric} not in {name}"
    g = df.groupby(column)[metric].mean()
    return ", ".join(f"{i}={v:.4f}" for i, v in g.items())


def load_gold_features_sample(n: int = 5) -> str:
    path = PATHS["gold_features"]
    if not path.exists():
        return "Gold features parquet not found. Run Phase 2 first."
    df = pd.read_parquet(path).head(n)
    return df.to_string()
