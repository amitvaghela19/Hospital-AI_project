from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from governance.dq_rules import validate_inference_row
from inference.rnn_core import load_rnn_chat_artifacts, predict_rnn_prob, row_to_seq_frame
from inference.shadow import disagreement
from mcp.client.pool import pool
from streamlit_app.rbac_auth import validate_role
from streamlit_app.data_loaders import apply_certified_prediction_overlay

StepStatus = Literal["pending", "running", "done", "skipped", "failed"]

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class PipelineStep:
    key: str
    label: str
    status: StepStatus = "pending"
    detail: str = ""
    duration_ms: int = 0


@dataclass
class PipelineResult:
    success: bool
    steps: list[PipelineStep] = field(default_factory=list)
    prediction: dict[str, Any] | None = None
    error: str | None = None


def _chat_router_config() -> dict:
    cfg_path = ROOT / "models" / "chat_router_config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {
        "uncertainty_low": float(os.environ.get("UNCERTAINTY_LOW", "0.35")),
        "uncertainty_high": float(os.environ.get("UNCERTAINTY_HIGH", "0.55")),
    }


def prepare_feature_matrix(row: dict, feature_cols: list[str]) -> pd.DataFrame:
    X = pd.DataFrame([{c: row.get(c, np.nan) for c in feature_cols}])
    for c in X.columns:
        s = X[c]
        if pd.api.types.is_numeric_dtype(s):
            continue
        orig = s.copy()
        if orig.dtype == object:
            orig = orig.replace("", np.nan)
        non_null_mask = orig.notna()
        if not bool(non_null_mask.any()):
            continue
        converted = pd.to_numeric(orig, errors="coerce")
        converted_ok_ratio = float(converted.notna()[non_null_mask].mean())
        if converted_ok_ratio >= 0.9:
            X[c] = converted
        else:
            X[c] = orig
    return X


def run_predict_pipeline(
    row: dict,
    feature_cols: list[str],
    pipe,
    reference_pipe,
    register: dict,
    role: str,
    *,
    risk_band_fn,
    rule_recommendations_fn,
    template_explanation_fn,
    tick_delay: float = 0.15,
    on_step_update=None,
) -> PipelineResult:
    """Execute the full inference pipeline with per-step status for the UI."""
    role = validate_role(role)

    def _notify():
        if on_step_update:
            on_step_update(steps)

    steps: list[PipelineStep] = [
        PipelineStep("dq", "1 · Data quality gate"),
        PipelineStep("features", "2 · Feature preparation"),
        PipelineStep("champion", "3 · Primary tri_ensemble score"),
        PipelineStep("chat_router", "4 · Uncertainty chat_router (RNN)"),
        PipelineStep("shadow", "5 · Reference RF comparison"),
        PipelineStep("cohort", "6 · Similar cohort (Chroma)"),
        PipelineStep("explain", "7 · Clinician explanation"),
        PipelineStep("audit", "8 · Audit & governance log"),
    ]
    result = PipelineResult(success=False, steps=steps)

    def _run_step(idx: int, fn) -> Any:
        step = steps[idx]
        step.status = "running"
        _notify()
        t0 = time.perf_counter()
        try:
            out = fn()
            step.duration_ms = int((time.perf_counter() - t0) * 1000)
            step.status = "done"
            _notify()
            time.sleep(tick_delay)
            return out
        except Exception as exc:
            step.status = "failed"
            step.detail = str(exc)
            step.duration_ms = int((time.perf_counter() - t0) * 1000)
            _notify()
            raise

    try:
        # 1 DQ
        dq = _run_step(0, lambda: validate_inference_row(row))
        if not dq["passed"]:
            steps[0].status = "failed"
            steps[0].detail = "; ".join(dq["failures"])
            _notify()
            pool.audit(role, "dq_blocked", {"failures": dq["failures"]})
            result.error = "Data quality gate blocked scoring."
            return result
        steps[0].detail = "All DQ rules passed"

        # 2 Features
        X = _run_step(1, lambda: prepare_feature_matrix(row, feature_cols))
        steps[1].detail = f"{len(feature_cols)} features prepared"

        # 3 Primary model
        primary_prob = _run_step(2, lambda: float(pipe.predict_proba(X)[0, 1]))
        steps[2].detail = f"Primary probability = {primary_prob:.4f}"

        # 4 chat_router
        cfg = _chat_router_config()
        low, high = float(cfg["uncertainty_low"]), float(cfg["uncertainty_high"])
        routed = {"primary_prob": primary_prob, "rnn_prob": None, "final_prob": primary_prob, "route": "tri_only"}
        steps[3].status = "running"
        _notify()
        t0 = time.perf_counter()
        if not (low <= primary_prob <= high):
            steps[3].status = "skipped"
            steps[3].detail = f"Primary score {primary_prob:.3f} outside uncertainty band [{low:.2f}, {high:.2f}]"
            steps[3].duration_ms = int((time.perf_counter() - t0) * 1000)
            _notify()
        else:
            model, token_maps, torch_mod = load_rnn_chat_artifacts()
            if model is None:
                steps[3].status = "skipped"
                steps[3].detail = "RNN chat_artifacts missing — tri_ensemble only"
                steps[3].duration_ms = int((time.perf_counter() - t0) * 1000)
                _notify()
            else:
                seq_df = row_to_seq_frame(row, token_maps)
                probs = predict_rnn_prob(model, torch_mod, seq_df)
                if len(probs) == 0:
                    steps[3].status = "skipped"
                    steps[3].detail = "RNN returned no score — RF-only route"
                else:
                    rnn_prob = float(probs[0])
                    routed["rnn_prob"] = rnn_prob
                    routed["final_prob"] = float((primary_prob + rnn_prob) / 2)
                    routed["route"] = "tri_rnn_blend"
                    steps[3].status = "done"
                    steps[3].detail = f"Tri {primary_prob:.3f} + RNN {rnn_prob:.3f} → blend {routed['final_prob']:.3f}"
                steps[3].duration_ms = int((time.perf_counter() - t0) * 1000)
                _notify()
        time.sleep(tick_delay)

        prob = float(routed["final_prob"])
        reference_prob = _run_step(
            4,
            lambda: float(reference_pipe.predict_proba(X)[0, 1]) if reference_pipe is not None else None,
        )
        disagree_flag = disagreement(primary_prob, reference_prob)
        if reference_prob is None:
            steps[4].status = "skipped"
            steps[4].detail = "Reference RF pipeline not available"
        elif disagree_flag:
            steps[4].detail = f"DISAGREEMENT — tri {primary_prob:.3f} vs RF {reference_prob:.3f}"
        else:
            steps[4].detail = f"Reference RF agrees — {reference_prob:.3f}"
        _notify()

        band = risk_band_fn(prob)
        top = [f.get("feature", "").replace("num__", "") for f in register.get("top_features", [])[:5]]
        recs = rule_recommendations_fn(band, row)

        sim_text = _run_step(5, lambda: pool.similar_cohort(row))
        if sim_text:
            steps[5].detail = sim_text[:120] + ("…" if len(sim_text) > 120 else "")
        else:
            steps[5].status = "skipped"
            steps[5].detail = "No Chroma index — run System Health Diagnose → Index neighbors"
        _notify()

        facts = {
            "risk_band": band,
            "probability": round(prob, 4),
            "threshold": float(register.get("threshold", 0.5)),
            "top_factors": top,
            "recommendations": recs,
            "model_id": register.get("champion_model"),
        }

        def _explain():
            ollama_h = pool.ollama_health()
            ollama_status = ollama_h.get("status", "unknown")
            text, model_id = pool.ollama_phrase(facts)
            if not text:
                text = template_explanation_fn(band, top, recs)
                model_id = "template"
            return text, model_id, ollama_status

        text, model_id, ollama_status = _run_step(6, _explain)
        if model_id == "template":
            steps[6].detail = f"Template explanation (Ollama: {ollama_status})"
        else:
            steps[6].detail = f"Ollama phrasing via {model_id}"

        def _audit():
            pool.audit(
                role,
                "predict",
                {
                    "rf_prob": reference_prob,
                    "primary_prob": primary_prob,
                    "rnn_prob": routed.get("rnn_prob"),
                    "route": routed.get("route"),
                    "reference_prob": reference_prob,
                    "disagree": disagree_flag,
                    "encounter_id": row.get("encounter_id"),
                    "pipeline_steps": [s.key for s in steps if s.status == "done"],
                },
            )
            return True

        _run_step(7, _audit)
        steps[7].detail = "Event written to audit log"

        result.success = True
        result.prediction = apply_certified_prediction_overlay(
            {
                "prob": prob,
                "band": band,
                "routed": routed,
                "reference_prob": reference_prob,
                "disagree": disagree_flag,
                "top": top,
                "recs": recs,
                "text": text,
                "model_id": model_id,
                "ollama_status": ollama_status,
                "similar_cohort": sim_text,
            },
            row,
        )
        return result

    except Exception as exc:
        result.error = str(exc)
        return result
