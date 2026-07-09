#!/usr/bin/env python3
"""Train and persist RNN + shadow tri-ensemble + routing config for advanced inference."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import VotingClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inference.rnn_core import build_seq_frame, train_rnn_model
from ml.sample import sample_rows
from ml.tuning import get_rnn_params, make_estimator

RANDOM_STATE = 42
CHAMPION_SAMPLE = int(os.environ.get("CHAMPION_SAMPLE", "0"))


def load_features():
    feat_path = ROOT / "data" / "lake" / "gold" / "model_features.parquet"
    seq_path = ROOT / "data" / "lake" / "gold" / "rnn_sequences.parquet"
    features = pd.read_parquet(feat_path)
    seq = pd.read_parquet(seq_path)
    feature_cols = json.loads((ROOT / "models" / "champion_features.json").read_text(encoding="utf-8"))["features"]
    return features, seq, feature_cols


def train_rnn_artifacts(df, seq_raw, feature_cols):
    champ = sample_rows(df, CHAMPION_SAMPLE, random_state=RANDOM_STATE)
    y = champ["readmit_30d"].astype(int)
    X = champ[feature_cols]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, stratify=y, random_state=RANDOM_STATE)
    X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.15, stratify=y_train, random_state=RANDOM_STATE)

    tr_ids = champ.loc[X_train.index, "encounter_id"]
    seq_frame, token_maps = build_seq_frame(champ, seq_raw)
    s_train = seq_frame.set_index("encounter_id").loc[tr_ids.values].reset_index(drop=True)
    y_tr = y_train.reset_index(drop=True)

    rnn_hp = get_rnn_params()
    model, torch_mod = train_rnn_model(
        s_train,
        y_tr,
        emb=int(rnn_hp.get("emb", 16)),
        hidden=int(rnn_hp.get("hidden", 32)),
        lr=float(rnn_hp.get("lr", 0.001)),
        epochs=int(rnn_hp.get("epochs", 5)),
        token_maps=token_maps,
    )
    models_dir = ROOT / "models"
    models_dir.mkdir(exist_ok=True)
    if model is not None:
        import torch
        torch.save(model.state_dict(), models_dir / "rnn_primary.pt")
        (models_dir / "rnn_token_maps.json").write_text(json.dumps(token_maps), encoding="utf-8")
        print("Saved rnn_primary.pt")
    else:
        print("RNN training skipped (torch unavailable)")

    routing = {
        "uncertainty_low": float(os.environ.get("UNCERTAINTY_LOW", "0.35")),
        "uncertainty_high": float(os.environ.get("UNCERTAINTY_HIGH", "0.55")),
        "blend_mode": "average",
    }
    (models_dir / "routing_config.json").write_text(json.dumps(routing, indent=2), encoding="utf-8")
    print("Saved routing_config.json")


def train_shadow_ensemble(df, feature_cols):
    from ml.preprocess import build_preprocessor

    champ = sample_rows(df, CHAMPION_SAMPLE, random_state=RANDOM_STATE)
    y = champ["readmit_30d"].astype(int)
    X = champ[feature_cols]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, stratify=y, random_state=RANDOM_STATE)

    pre, _, _ = build_preprocessor(X_train)

    from sklearn.base import clone

    def make_pipe(name):
        return Pipeline([("pre", clone(pre)), ("clf", make_estimator(name))])

    xgb = make_pipe("xgboost")
    lgb = make_pipe("lightgbm")
    cat = make_pipe("catboost")

    shadow = VotingClassifier(
        estimators=[("xgb", xgb), ("lgb", lgb), ("cat", cat)],
        voting="soft",
    )
    shadow.fit(X_train, y_train)
    val_prob = shadow.predict_proba(X_test)[:, 1]
    thr = 0.45
    models_dir = ROOT / "models"
    joblib.dump(shadow, models_dir / "shadow_tri_ensemble.joblib")
    shadow_reg = {
        "model": "tri_ensemble_shadow",
        "members": ["xgboost", "lightgbm", "catboost"],
        "threshold": thr,
        "mean_val_prob": float(val_prob.mean()),
    }
    (models_dir / "shadow_register.json").write_text(json.dumps(shadow_reg, indent=2), encoding="utf-8")
    print("Saved shadow_tri_ensemble.joblib")


def main():
    features, seq, feature_cols = load_features()
    train_rnn_artifacts(features, seq, feature_cols)
    train_shadow_ensemble(features, feature_cols)
    print("Advanced inference artifacts complete.")


if __name__ == "__main__":
    main()
