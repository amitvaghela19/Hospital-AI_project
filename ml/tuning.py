from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import recall_score
from sklearn.model_selection import RandomizedSearchCV
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parent.parent
SPACES_PATH = ROOT / "config" / "hyperparam_spaces.yaml"
HYPERPARAMS_PATH = ROOT / "models" / "hyperparams.yaml"
RANDOM_STATE = 42

DEFAULT_TABULAR_PARAMS: dict[str, dict[str, Any]] = {
    "logreg": {"clf__C": 1.0, "clf__max_iter": 200},
    "rf": {"clf__n_estimators": 80, "clf__max_depth": 12},
    "xgboost": {"clf__n_estimators": 80, "clf__max_depth": 5, "clf__learning_rate": 0.08},
    "lightgbm": {"clf__n_estimators": 80, "clf__max_depth": 5, "clf__learning_rate": 0.08},
    "catboost": {"clf__iterations": 80, "clf__depth": 5, "clf__learning_rate": 0.08},
}

DEFAULT_RNN_PARAMS = {"emb": 16, "hidden": 32, "lr": 0.001, "epochs": 5}

TABULAR_MODELS = ["logreg", "rf", "xgboost", "lightgbm", "catboost"]


def recall_scorer():
    return "recall"


def load_spaces(path: Path | None = None) -> dict:
    path = path or SPACES_PATH
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_hyperparams(path: Path | None = None) -> dict:
    path = path or HYPERPARAMS_PATH
    if not path.exists():
        return {
            "models": {
                name: {"best_params": dict(params), "best_cv_recall": None}
                for name, params in DEFAULT_TABULAR_PARAMS.items()
            },
            "rnn": {"best_params": dict(DEFAULT_RNN_PARAMS), "best_val_recall": None},
        }
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_hyperparams(payload: dict, path: Path | None = None) -> Path:
    path = path or HYPERPARAMS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, default_flow_style=False)
    return path


def _strip_clf_prefix(params: dict) -> dict:
    out = {}
    for k, v in params.items():
        key = k.replace("clf__", "") if k.startswith("clf__") else k
        out[key] = v
    return out


def make_estimator(name: str, params: dict | None = None):
    from catboost import CatBoostClassifier
    from lightgbm import LGBMClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from xgboost import XGBClassifier

    hp = load_hyperparams()
    if params is None:
        model_hp = hp.get("models", {}).get(name, {})
        params = model_hp.get("best_params", DEFAULT_TABULAR_PARAMS.get(name, {}))
    raw = _strip_clf_prefix(params)

    if name == "logreg":
        return LogisticRegression(
            max_iter=int(raw.get("max_iter", 200)),
            class_weight="balanced",
            random_state=RANDOM_STATE,
            C=float(raw.get("C", 1.0)),
        )
    if name == "rf":
        depth = raw.get("max_depth", 12)
        return RandomForestClassifier(
            n_estimators=int(raw.get("n_estimators", 80)),
            max_depth=None if depth is None else int(depth),
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=RANDOM_STATE,
        )
    if name == "xgboost":
        return XGBClassifier(
            n_estimators=int(raw.get("n_estimators", 80)),
            max_depth=int(raw.get("max_depth", 5)),
            learning_rate=float(raw.get("learning_rate", 0.08)),
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    if name == "lightgbm":
        return LGBMClassifier(
            n_estimators=int(raw.get("n_estimators", 80)),
            max_depth=int(raw.get("max_depth", 5)),
            learning_rate=float(raw.get("learning_rate", 0.08)),
            class_weight="balanced",
            random_state=RANDOM_STATE,
            verbose=-1,
        )
    if name == "catboost":
        return CatBoostClassifier(
            iterations=int(raw.get("iterations", raw.get("n_estimators", 80))),
            depth=int(raw.get("depth", raw.get("max_depth", 5))),
            learning_rate=float(raw.get("learning_rate", 0.08)),
            verbose=False,
            random_seed=RANDOM_STATE,
            auto_class_weights="Balanced",
        )
    raise ValueError(f"Unknown model: {name}")


def _param_distributions(space: dict) -> dict:
    dist = {}
    for k, v in space.items():
        if isinstance(v, list):
            cleaned = []
            for item in v:
                if item is None or (isinstance(item, str) and item.lower() == "null"):
                    cleaned.append(None)
                else:
                    cleaned.append(item)
            dist[k] = cleaned
        else:
            dist[k] = v
    return dist


def tune_tabular_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    pre,
    spaces: dict | None = None,
    n_iter: int | None = None,
    cv: int | None = None,
) -> dict[str, dict]:
    n_iter = n_iter or int(os.environ.get("TUNING_N_ITER", "25"))
    cv = cv or int(os.environ.get("TUNING_CV", "3"))
    spaces = spaces or load_spaces()
    tabular_spaces = spaces.get("tabular", {})
    results = {}

    for name in TABULAR_MODELS:
        print(f"Tuning {name} (n_iter={n_iter}, cv={cv})...")
        clf = make_estimator(name, DEFAULT_TABULAR_PARAMS.get(name, {}))
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        param_dist = _param_distributions(tabular_spaces.get(name, {}))
        if not param_dist:
            results[name] = {
                "best_params": DEFAULT_TABULAR_PARAMS.get(name, {}),
                "best_cv_recall": None,
            }
            continue
        search = RandomizedSearchCV(
            pipe,
            param_distributions=param_dist,
            n_iter=n_iter,
            cv=cv,
            scoring=recall_scorer(),
            random_state=RANDOM_STATE,
            n_jobs=-1,
            refit=True,
            error_score="raise",
        )
        search.fit(X_train, y_train)
        best_score = float(search.best_score_)
        results[name] = {
            "best_params": dict(search.best_params_),
            "best_cv_recall": best_score,
        }
        print(f"  {name} best_cv_recall={best_score:.4f} params={search.best_params_}")
    return results


def tune_rnn_optuna(
    s_train: pd.DataFrame,
    y_train: pd.Series,
    s_val: pd.DataFrame,
    y_val: pd.Series,
    token_maps: dict,
    n_trials: int | None = None,
) -> dict:
    import optuna
    from inference.rnn_core import predict_rnn_prob, train_rnn_model

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    n_trials = n_trials or int(os.environ.get("RNN_OPTUNA_TRIALS", "20"))
    spaces = load_spaces().get("rnn", DEFAULT_RNN_PARAMS)

    def objective(trial):
        emb = trial.suggest_categorical("emb", spaces.get("emb", [16]))
        hidden = trial.suggest_categorical("hidden", spaces.get("hidden", [32]))
        lr = trial.suggest_categorical("lr", spaces.get("lr", [0.001]))
        epochs = trial.suggest_categorical("epochs", spaces.get("epochs", [5]))
        model, torch_mod = train_rnn_model(
            s_train, y_train, emb=emb, hidden=hidden, lr=lr, epochs=epochs, token_maps=token_maps,
        )
        if model is None:
            return 0.0
        probs = predict_rnn_prob(model, torch_mod, s_val)
        if len(probs) == 0:
            return 0.0
        pred = (probs >= 0.3).astype(int)
        return float(recall_score(y_val, pred, zero_division=0))

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    best = study.best_params
    best_recall = float(study.best_value)
    print(f"RNN Optuna best_val_recall={best_recall:.4f} params={best}")
    return {"best_params": best, "best_val_recall": best_recall}


def get_model_params(name: str) -> dict:
    hp = load_hyperparams()
    return hp.get("models", {}).get(name, {}).get("best_params", DEFAULT_TABULAR_PARAMS.get(name, {}))


def get_rnn_params() -> dict:
    hp = load_hyperparams()
    return hp.get("rnn", {}).get("best_params", dict(DEFAULT_RNN_PARAMS))


def build_hyperparams_payload(
    tabular_results: dict,
    rnn_result: dict,
    protocol: dict,
    train_rows: int,
) -> dict:
    return {
        "tuned_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {**protocol, "train_rows": train_rows},
        "models": tabular_results,
        "rnn": rnn_result,
    }
