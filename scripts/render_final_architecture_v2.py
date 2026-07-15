#!/usr/bin/env python3
"""
Render final architecture v2.png from a detailed matplotlib layout.

Usage (from project root):
    python scripts/render_final_architecture_v2.py

Outputs:
    final architecture v2.png  (project root)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "final architecture v2.png"

# (title, color, lines)
LEFT_PHASES = [
    ("SOURCES & REGISTRY", "#E8EEF4", [
        "datafile.txt — 17 role|zone|path entries (raw→ops)",
        "data/raw/diabetic_data.csv — 101,766 encounters",
        ".venv + Jupyter kernel Hospital Project (.venv)",
        "Env: MATRIX_SAMPLE=0 | SKIP_TUNING=1 | CHAMPION_SAMPLE=0",
    ]),
    ("PHASE 0 — Ingestion & Governance", "#D4EDDA", [
        "phase0_ingestion_lake_governance.ipynb",
        "bronze/encounters_raw.parquet → DQ gates (8 checks, fail-fast)",
        "silver/encounters.parquet | manifest latest.json",
        "nosql RBAC + metadata | exports/mart_dq_scorecard.csv",
    ]),
    ("PHASE 1 — SQL, Marts & RAG Seed", "#CCE5FF", [
        "phase1_modeling_marts_sql.ipynb",
        "hospital.db — Kimball dims/facts | sql/ 12 queries",
        "mart_readmission.csv | metric_dictionary.json",
        "rag_documents.json → Chroma project_knowledge (data/vectordb)",
    ]),
    ("PHASE 2 — Stats, EDA & Gold Features", "#FFF3CD", [
        "phase2_stats_features.ipynb — inline EDA + PNG export",
        "exports/eda/ — 5 plots (readmit, age, LOS, meds, admission)",
        "gold/model_features.parquet (30 cols, leakage denylist)",
        "gold/rnn_sequences.parquet | feature_dictionary.json",
    ]),
    ("PHASE 3 — ML Matrix, Tuning & Model Risk", "#F8D7DA", [
        "phase3_ml_experiments.ipynb — cohort→tune→matrix→stack→champion",
        "ml/: preprocess splits sample tuning | hyperparams.yaml",
        "scripts/tune_hyperparams.py — tabular CV + RNN Optuna",
        "§6 matrix: 3 horizons × 7 splits × 8 models = 168 runs",
        "Models: logreg rf xgboost lightgbm catboost rnn + gb/tri ensembles",
        "exports/experiments_matrix.csv — 168×13 metrics table",
        "§7 stacking: LightGBM + CatBoost + XGB → LR meta-learner",
        "champion_pipeline.joblib (serve RF) | shadow_tri + rnn_primary.pt",
        "SHAP fairness ablation Brier | model_card champion_register ab_test",
        "gold/experiment_results.parquet | test_predictions.parquet",
    ]),
    ("PHASE 4 — Power BI Certified Exports", "#E2D5F1", [
        "phase4_powerbi_exports.ipynb — never connect to bronze",
        "mart_clinical_risk | mart_model_performance | mart_actual_vs_predicted",
        "mart_shadow_disagreement (optional) | kpi_snapshot.json",
        "powerbi/BUILD_INSTRUCTIONS.md — 5 dashboard pages",
    ]),
    ("PHASE 5 — Clinician App (Streamlit + LangGraph)", "#D1ECF1", [
        "phase5_langgraph_app.ipynb → app_streamlit.py",
        "chatbot/scripts/*.json — gold_standard governance FAQ model_cards",
        "LangGraph router + MCP Model Tribunal | RBAC guardrails",
        "Ollama deepseek-r1 / llama3 — phrasing only, not clinical decisions",
        "audit_events.json — all routes logged",
    ]),
    ("CONSUMERS", "#F5F5F5", [
        "Power BI Desktop — Overview, Readmissions, Patients, Model Perf, Cohort",
        "Clinician UI — risk band, SHAP factors, similar cohorts, grounded chat",
    ]),
]

RIGHT_PANELS = [
    ("MCP — 18-SERVER FLEET", "#E8F4FD", [
        "IDE: .cursor/mcp.json → Cursor agent during dev",
        "Runtime: mcp/client/pool.py → Streamlit + LangGraph",
        "Official: Filesystem Git SQLite Chroma Redis HTTP",
        "Custom: Pandas NumPy Logging Config Notifications Scheduler",
        "Stretch: FRED macro | MQTT IoT demo | Browser Terminal",
        "Infra: docker-compose.mcp.yml | scripts/mcp_healthcheck.py",
        "mcp/servers/*.py + mcp/services/*.py",
    ]),
    ("ADVANCED INFERENCE", "#FDE8E8", [
        "governance/dq_rules.py — DQ-gated live scoring (refuse bad input)",
        "inference/chat_router.py — RF + RNN uncertainty-band blend",
        "inference/shadow.py — shadow tri_ensemble disagreement flag",
        "inference/similarity.py — Chroma encounter_neighbors (K=5)",
        "inference/tribunal.py — multi-gate LangGraph MCP workflow",
        "scripts/index_encounter_neighbors.py | train_advanced_chat_artifacts.py",
    ]),
    ("ORCHESTRATION & OPS", "#EEEEEE", [
        "master.ipynb — Phase 0→5 sequential fail-fast",
        "models/: champion_register hyperparams chat_router_config",
        "data/nosql/: rbac audit metric_dict rag feature_dict",
        "Analytics decision-support only — NOT a medical device",
    ]),
]

FIG_W, FIG_H = 22, 28
LEFT_X, LEFT_W = 0.04, 0.58
RIGHT_X, RIGHT_W = 0.66, 0.30
TITLE_H = 0.026
LINE_H = 0.019
PAD = 0.010
GAP = 0.014


def box_height(n_lines: int) -> float:
    return TITLE_H + PAD * 2 + n_lines * LINE_H


def draw_box(ax, x: float, w: float, y_top: float, title: str, color: str, lines: list[str]) -> float:
    h = box_height(len(lines))
    y_bottom = y_top - h
    rect = FancyBboxPatch(
        (x, y_bottom), w, h,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        linewidth=1.0, edgecolor="#333333", facecolor=color, transform=ax.transAxes,
    )
    ax.add_patch(rect)
    ax.text(x + 0.015, y_top - PAD - 0.004, title,
            transform=ax.transAxes, fontsize=9.5, fontweight="bold", va="top")
    for i, line in enumerate(lines):
        ax.text(x + 0.022, y_top - TITLE_H - PAD - i * LINE_H, f"• {line}",
                transform=ax.transAxes, fontsize=7.2, va="top", color="#222222")
    return y_bottom


def draw_column(ax, x: float, w: float, y_start: float, panels: list) -> float:
    y = y_start
    prev_bottom = None
    for title, color, lines in panels:
        y_bottom = draw_box(ax, x, w, y, title, color, lines)
        if prev_bottom is not None:
            ax.add_patch(FancyArrowPatch(
                (x + w / 2, prev_bottom), (x + w / 2, y + 0.003),
                transform=ax.transAxes, arrowstyle="-|>", mutation_scale=10,
                linewidth=1.2, color="#666666",
            ))
        prev_bottom = y_bottom - 0.004
        y = y_bottom - GAP
    return y


def main() -> None:
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.985, "Healthcare Patient Readmission Analysis",
            transform=ax.transAxes, ha="center", va="top", fontsize=18, fontweight="bold")
    ax.text(0.5, 0.968,
            "Full Architecture v2 — Medallion Lake · SQL Warehouse · ML Matrix · MCP · LangGraph · Power BI",
            transform=ax.transAxes, ha="center", va="top", fontsize=10, color="#444444")

    y_left = draw_column(ax, LEFT_X, LEFT_W, 0.955, LEFT_PHASES)
    draw_column(ax, RIGHT_X, RIGHT_W, 0.955, RIGHT_PANELS)

    # Cross-links: MCP → pipeline chat_artifacts
    ax.add_patch(FancyArrowPatch(
        (RIGHT_X, 0.55), (LEFT_X + LEFT_W, 0.45),
        transform=ax.transAxes, arrowstyle="-|>", mutation_scale=10,
        linewidth=1.0, color="#888888", linestyle="dashed",
        connectionstyle="arc3,rad=-0.15",
    ))
    ax.text(0.62, 0.50, "MCP tools\nread/write", transform=ax.transAxes,
            fontsize=7, ha="center", color="#666666", style="italic")

    # master.ipynb spine
    ax.plot([LEFT_X + LEFT_W + 0.035, LEFT_X + LEFT_W + 0.035], [0.12, 0.94],
            transform=ax.transAxes, color="#999999", linewidth=2, linestyle=":")
    ax.text(LEFT_X + LEFT_W + 0.035, 0.96, "master.ipynb", transform=ax.transAxes,
            ha="center", fontsize=8, fontweight="bold", color="#555555")
    for i, label in enumerate(["P0", "P1", "P2", "P3", "P4", "P5"]):
        yy = 0.88 - i * 0.13
        ax.plot(LEFT_X + LEFT_W + 0.02, yy, "o", transform=ax.transAxes,
                color="#777777", markersize=6)
        ax.text(LEFT_X + LEFT_W + 0.05, yy, label, transform=ax.transAxes,
                fontsize=7, va="center", color="#555555")

    ax.text(0.5, 0.012,
            "Source: final architecture v2.mmd | Regenerate: python scripts/render_final_architecture_v2.py",
            transform=ax.transAxes, ha="center", fontsize=7.5, color="#888888")

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    fig.savefig(OUT, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
