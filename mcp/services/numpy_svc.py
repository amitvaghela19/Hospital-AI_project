from __future__ import annotations

import numpy as np
import pandas as pd

from mcp.common import PATHS


def feature_array_stats(columns: list[str] | None = None) -> dict[str, dict[str, float]]:
    path = PATHS["gold_features"]
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    numeric = df.select_dtypes(include=[np.number])
    if columns:
        numeric = numeric[[c for c in columns if c in numeric.columns]]
    out: dict[str, dict[str, float]] = {}
    for col in numeric.columns:
        arr = numeric[col].dropna().to_numpy()
        if arr.size == 0:
            continue
        out[col] = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "median": float(np.median(arr)),
        }
    return out


def correlation_pair(col_a: str, col_b: str) -> float | None:
    path = PATHS["gold_features"]
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if col_a not in df.columns or col_b not in df.columns:
        return None
    a = pd.to_numeric(df[col_a], errors="coerce")
    b = pd.to_numeric(df[col_b], errors="coerce")
    mask = a.notna() & b.notna()
    if mask.sum() < 2:
        return None
    return float(np.corrcoef(a[mask], b[mask])[0, 1])
