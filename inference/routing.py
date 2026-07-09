from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from inference.rnn_core import load_rnn_artifacts, predict_rnn_prob, row_to_seq_frame

ROOT = Path(__file__).resolve().parent.parent


def _routing_config() -> dict:
    cfg_path = ROOT / "models" / "routing_config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {
        "uncertainty_low": float(os.environ.get("UNCERTAINTY_LOW", "0.35")),
        "uncertainty_high": float(os.environ.get("UNCERTAINTY_HIGH", "0.55")),
        "blend_mode": "average",
    }


def _row_to_seq_frame(row: dict, token_maps: dict | None = None) -> pd.DataFrame:
    return row_to_seq_frame(row, token_maps)


def score_with_routing(
    X: pd.DataFrame,
    row: dict,
    rf_pipe,
    feature_cols: list[str],
) -> dict:
    rf_prob = float(rf_pipe.predict_proba(X)[0, 1])
    cfg = _routing_config()
    low, high = float(cfg["uncertainty_low"]), float(cfg["uncertainty_high"])
    result = {
        "rf_prob": rf_prob,
        "rnn_prob": None,
        "final_prob": rf_prob,
        "route": "rf_only",
    }

    if not (low <= rf_prob <= high):
        return result

    model, token_maps, torch_mod = load_rnn_artifacts()
    if model is None:
        return result

    seq_df = _row_to_seq_frame(row, token_maps)
    probs = predict_rnn_prob(model, torch_mod, seq_df)
    if len(probs) == 0:
        return result

    rnn_prob = float(probs[0])
    result["rnn_prob"] = rnn_prob
    result["final_prob"] = float((rf_prob + rnn_prob) / 2)
    result["route"] = "rf_rnn_blend"
    return result
