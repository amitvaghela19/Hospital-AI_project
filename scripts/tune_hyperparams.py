#!/usr/bin/env python3
"""Tune tabular models (RandomizedSearchCV) and RNN (Optuna); save models/hyperparams.yaml."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inference.rnn_core import build_seq_frame
from ml.preprocess import build_preprocessor
from ml.sample import sample_rows
from ml.splits import make_split
from ml.tuning import (
    build_hyperparams_payload,
    load_hyperparams,
    load_spaces,
    save_hyperparams,
    tune_rnn_optuna,
    tune_tabular_models,
)

RANDOM_STATE = 42
PRIMARY_SPLIT = "70/15/15"
PRIMARY_HORIZON = "30d"
SPLITS = {
    "80/20": (0.80, None),
    "70/30": (0.70, None),
    "75/25": (0.75, None),
    "65/35": (0.65, None),
    "60/40": (0.60, None),
    "60/20/20": (0.60, 0.20),
    "70/15/15": (0.70, 0.15),
}
HORIZONS = {"30d": "readmit_30d", "60d": "readmit_60d_proxy", "90d": "readmit_90d_proxy"}
CHAMPION_SAMPLE = int(os.environ.get("CHAMPION_SAMPLE", "0"))


def main():
    if os.environ.get("SKIP_TUNING", "0") == "1":
        hp = load_hyperparams()
        print("SKIP_TUNING=1; using existing hyperparams.yaml")
        print("models:", list(hp.get("models", {}).keys()))
        return

    feat_path = ROOT / "data" / "lake" / "gold" / "model_features.parquet"
    seq_path = ROOT / "data" / "lake" / "gold" / "rnn_sequences.parquet"
    features = pd.read_parquet(feat_path)
    seq_raw = pd.read_parquet(seq_path)
    feature_cols = json.loads(
        (ROOT / "models" / "champion_features.json").read_text(encoding="utf-8")
    )["features"]

    champ = sample_rows(features, CHAMPION_SAMPLE, random_state=RANDOM_STATE)
    ycol = HORIZONS[PRIMARY_HORIZON]
    X = champ[feature_cols]
    y = champ[ycol].astype(int)
    X_train, X_val, X_test, y_train, y_val, y_test = make_split(
        X, y, PRIMARY_SPLIT, SPLITS, random_state=RANDOM_STATE,
    )
    print(f"Tuning on train={len(X_train)} val={len(X_val)} (full sample={len(champ)})")

    pre, _, _ = build_preprocessor(X_train)
    spaces = load_spaces()
    tabular_results = tune_tabular_models(X_train, y_train, pre, spaces=spaces)

    rnn_result = {"best_params": {}, "best_val_recall": None}
    try:
        tr_ids = champ.loc[X_train.index, "encounter_id"]
        va_ids = champ.loc[X_val.index, "encounter_id"]
        seq_frame, token_maps = build_seq_frame(champ, seq_raw)
        s_train = seq_frame.set_index("encounter_id").loc[tr_ids.values].reset_index(drop=True)
        s_val = seq_frame.set_index("encounter_id").loc[va_ids.values].reset_index(drop=True)
        y_tr = y_train.reset_index(drop=True)
        y_va = y_val.reset_index(drop=True)
        rnn_result = tune_rnn_optuna(s_train, y_tr, s_val, y_va, token_maps)
    except Exception as e:
        print(f"RNN Optuna skipped: {e}")

    payload = build_hyperparams_payload(
        tabular_results,
        rnn_result,
        protocol={
            "horizon": PRIMARY_HORIZON,
            "split": PRIMARY_SPLIT,
            "scoring": "recall",
        },
        train_rows=len(X_train),
    )
    out = save_hyperparams(payload)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
