from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def load_shadow_pipeline():
    path = ROOT / "models" / "shadow_tri_ensemble.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


def load_shadow_register() -> dict:
    path = ROOT / "models" / "shadow_register.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def score_shadow(X: pd.DataFrame) -> float | None:
    pipe = load_shadow_pipeline()
    if pipe is None:
        return None
    return float(pipe.predict_proba(X)[0, 1])


def disagreement(champion_prob: float, shadow_prob: float | None, tol: float | None = None) -> bool:
    if shadow_prob is None:
        return False
    if tol is None:
        tol = float(os.environ.get("SHADOW_DISAGREE_TOL", "0.15"))
    return abs(champion_prob - shadow_prob) > tol
