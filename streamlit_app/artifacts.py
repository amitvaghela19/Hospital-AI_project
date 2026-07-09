from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from streamlit_app import ROOT

MODELS = ROOT / "models"


def _tri_ensemble_metrics() -> dict:
    matrix = ROOT / "data" / "exports" / "experiments_matrix.csv"
    if not matrix.exists():
        return {}
    try:
        df = pd.read_csv(matrix)
        hit = df[
            (df["model"] == "tri_ensemble")
            & (df["horizon"] == "30d")
            & (df["split"] == "70/15/15")
        ]
        if hit.empty:
            return {}
        row = hit.iloc[0]
        return {
            "accuracy": float(row.get("accuracy", 0) or 0),
            "precision": float(row.get("precision", 0) or 0),
            "recall": float(row.get("recall", 0) or 0),
            "f1": float(row.get("f1", 0) or 0),
            "roc_auc": float(row.get("roc_auc", 0) or 0),
            "model": "tri_ensemble",
            "threshold": float(row.get("threshold", 0.35) or 0.35),
            "horizon": str(row.get("horizon", "30d")),
            "split": str(row.get("split", "70/15/15")),
            "train_size": int(row.get("train_size", 0) or 0),
            "val_size": int(row.get("val_size", 0) or 0),
            "test_size": int(row.get("test_size", 0) or 0),
            "ensemble": bool(row.get("ensemble", True)),
        }
    except Exception:
        return {}


def serving_mode() -> str:
    """Current served primary model."""
    if (MODELS / "shadow_tri_ensemble.joblib").exists():
        return "tri_ensemble"
    return load_serve_model_name()


@lru_cache(maxsize=1)
def load_register() -> dict:
    path = MODELS / "champion_register.json"
    if not path.exists():
        return {}
    reg = json.loads(path.read_text(encoding="utf-8"))
    if serving_mode() == "tri_ensemble":
        tri_metrics = _tri_ensemble_metrics()
        reg = {**reg}
        reg["champion_model"] = "tri_ensemble"
        reg["reported_matrix_winner"] = "tri_ensemble"
        reg["served_primary_model"] = "tri_ensemble"
        reg["reference_model"] = "rf"
        reg["explainability_source"] = "catboost/shap surrogate"
        if tri_metrics:
            reg["metrics"] = tri_metrics
            reg["threshold"] = tri_metrics.get("threshold", reg.get("threshold", 0.35))
            reg["split"] = tri_metrics.get("split", reg.get("split", "70/15/15"))
            reg["horizon"] = tri_metrics.get("horizon", reg.get("horizon", "30d"))
    return reg


@lru_cache(maxsize=1)
def load_feature_cols() -> list[str]:
    path = MODELS / "champion_features.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("features", []))


@lru_cache(maxsize=1)
def load_serve_model_name() -> str:
    path = MODELS / "champion_features.json"
    if not path.exists():
        return "unknown"
    return json.loads(path.read_text(encoding="utf-8")).get("serve_model", "unknown")


_pipe_cache: Any = None
_pipe_loaded: bool = False
_pipe_error: str | None = None
_reference_pipe_cache: Any = None
_reference_pipe_loaded: bool = False
_reference_pipe_error: str | None = None


def get_champion_pipeline():
    """Lazy-load champion pipeline; returns (pipe, error_message)."""
    global _pipe_cache, _pipe_loaded, _pipe_error
    if _pipe_loaded:
        return _pipe_cache, _pipe_error
    primary = MODELS / "shadow_tri_ensemble.joblib"
    fallback = MODELS / "champion_pipeline.joblib"
    path = primary if primary.exists() else fallback
    if not path.exists():
        _pipe_error = (
            "Primary scoring pipeline missing. Run Phase 3 notebook or: "
            "python scripts/train_advanced_artifacts.py"
        )
        _pipe_loaded = True
        return None, _pipe_error
    try:
        _pipe_cache = joblib.load(path)
        _pipe_error = None
    except Exception as exc:
        _pipe_error = f"Failed to load champion pipeline: {exc}"
        _pipe_cache = None
    _pipe_loaded = True
    return _pipe_cache, _pipe_error


def get_reference_pipeline():
    """Reference RF pipeline used as comparator when tri_ensemble is primary."""
    global _reference_pipe_cache, _reference_pipe_loaded, _reference_pipe_error
    if _reference_pipe_loaded:
        return _reference_pipe_cache, _reference_pipe_error
    path = MODELS / "champion_pipeline.joblib"
    if not path.exists():
        _reference_pipe_error = "Reference RF pipeline missing."
        _reference_pipe_loaded = True
        return None, _reference_pipe_error
    try:
        _reference_pipe_cache = joblib.load(path)
        _reference_pipe_error = None
    except Exception as exc:
        _reference_pipe_error = f"Failed to load reference RF pipeline: {exc}"
        _reference_pipe_cache = None
    _reference_pipe_loaded = True
    return _reference_pipe_cache, _reference_pipe_error


def artifact_status() -> dict[str, dict]:
    """Prerequisite checklist for Setup page."""
    reg = load_register()
    pipe, pipe_err = get_champion_pipeline()
    shadow_path = MODELS / "shadow_tri_ensemble.joblib"
    rnn_path = MODELS / "rnn_primary.pt"
    vectordb = ROOT / "data" / "vectordb"
    gold = ROOT / "data" / "lake" / "gold" / "model_features.parquet"

    register_model = reg.get("champion_model", "unknown")
    serve_model = serving_mode()
    pipeline_ok = pipe is not None
    register_mismatch = pipeline_ok and register_model != serve_model

    chroma_has_data = False
    if vectordb.exists():
        try:
            import chromadb
            import os

            from mcp.common import CHROMA_COLLECTION, PATHS

            neighbor_collection = os.environ.get("CHROMA_NEIGHBOR_COLLECTION", "encounter_neighbors")
            client = chromadb.PersistentClient(path=str(PATHS["vectordb"]))
            neighbor_col = client.get_or_create_collection(neighbor_collection)
            rag_col = client.get_or_create_collection(CHROMA_COLLECTION)
            chroma_has_data = neighbor_col.count() > 0 or rag_col.count() > 0
        except Exception:
            chroma_has_data = False

    return {
        "champion_pipeline": {
            "ok": pipeline_ok,
            "detail": "Loaded" if pipeline_ok else (pipe_err or "Missing"),
        },
        "champion_register": {
            "ok": bool(reg),
            "detail": f"model={register_model}" if reg else "Missing register JSON",
        },
        "register_serve_alignment": {
            "ok": not register_mismatch,
            "detail": (
                f"Register says '{register_model}', serve_model='{serve_model}', "
                f"pipeline serves runtime primary"
                if register_mismatch
                else "Register aligned with served pipeline"
            ),
        },
        "shadow_tri_ensemble": {
            "ok": shadow_path.exists(),
            "detail": "Present" if shadow_path.exists() else "Run train_advanced_artifacts.py",
        },
        "rnn_primary": {
            "ok": rnn_path.exists(),
            "detail": "Present" if rnn_path.exists() else "Run train_advanced_artifacts.py",
        },
        "gold_features": {
            "ok": gold.exists(),
            "detail": str(gold) if gold.exists() else "Run Phase 2",
        },
        "vectordb_dir": {
            "ok": vectordb.exists(),
            "detail": "Directory exists" if vectordb.exists() else "Not created yet",
        },
        "chroma_indexed": {
            "ok": chroma_has_data,
            "detail": (
                "encounter_neighbors and/or project_knowledge populated"
                if chroma_has_data
                else "Index neighbors from Setup (encounter_neighbors collection)"
            ),
        },
    }
