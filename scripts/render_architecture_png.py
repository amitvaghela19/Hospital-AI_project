#!/usr/bin/env python3
"""
Render project_architecture.png from a matplotlib flowchart.

Usage (from project root):
    python scripts/render_architecture_png.py

Output:
    docs/diagrams/project_architecture.png

Fallback if PNG looks wrong or matplotlib is unavailable:
  1. Open https://mermaid.live
  2. Paste docs/diagrams/project_architecture.mmd
  3. Actions -> Export PNG

Perplexity prompt:
  "Render the following Mermaid flowchart as a high-resolution PNG suitable
   for a presentation slide. Use a clean top-to-bottom layout with readable
   labels and light phase-colored bands."
  (then paste project_architecture.mmd contents)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "diagrams" / "project_architecture.png"

# (label, color) — top to bottom
PHASES = [
    ("SOURCES", "#E8EEF4", [
        "datafile.txt  (path registry)",
        "data/raw/diabetic_data.csv",
    ]),
    ("PHASE 0 — Ingestion & Governance", "#D4EDDA", [
        "phase0_ingestion_lake_governance.ipynb",
        "bronze/encounters_raw.parquet",
        "DQ gates (fail-fast) -> silver/encounters.parquet",
        "manifest, RBAC, metadata, mart_dq_scorecard.csv",
    ]),
    ("PHASE 1 — SQL Modeling & Marts", "#CCE5FF", [
        "phase1_modeling_marts_sql.ipynb",
        "hospital.db SQLite (Kimball dims/facts)",
        "sql/ — 12 queries | Chroma project_knowledge",
        "mart_readmission.csv, metric_dictionary.json",
    ]),
    ("PHASE 2 — Stats & Features", "#FFF3CD", [
        "phase2_stats_features.ipynb",
        "EDA plots (exports/eda/)",
        "gold/model_features.parquet, rnn_sequences.parquet",
    ]),
    ("PHASE 3 — ML & Model Risk", "#F8D7DA", [
        "phase3_ml_experiments.ipynb — tune → matrix → stack → champion",
        "ml/ package + hyperparams.yaml + experiments_matrix.csv (168×13)",
        "Models: logreg rf xgb lgb cat rnn + gb/tri ensembles",
        "Stacking: LightGBM + CatBoost + XGB → LR meta-learner",
        "champion_pipeline.joblib | SHAP fairness model_card | advanced chat_artifacts",
    ]),
    ("PHASE 4 — Power BI Exports", "#E2D5F1", [
        "phase4_powerbi_exports.ipynb",
        "exports/mart_*.csv, kpi_snapshot.json",
        "powerbi/BUILD_INSTRUCTIONS.md",
    ]),
    ("PHASE 5 — Clinician App", "#D1ECF1", [
        "phase5_langgraph_app.ipynb + app_streamlit.py",
        "Predict: DQ gate → RF → RNN chat_router → shadow → Chroma cohort",
        "Chat: MCP Model Tribunal + scripts/RAG/SQLite",
        "Ollama: deepseek-r1, llama3 (phrasing only)",
    ]),
    ("CONSUMERS", "#F5F5F5", [
        "Power BI Desktop — 5 dashboard pages",
        "Clinician UI — risk score + grounded chat",
    ]),
]

FIG_W, FIG_H = 14, 22
MARGIN_X = 0.08
BOX_W = 0.84
TITLE_H = 0.028
LINE_H = 0.022
PAD = 0.012
GAP = 0.018


def box_height(n_lines: int) -> float:
    return TITLE_H + PAD * 2 + n_lines * LINE_H


def draw_box(ax, y_top: float, title: str, color: str, lines: list[str]) -> float:
    h = box_height(len(lines))
    y_bottom = y_top - h
    rect = FancyBboxPatch(
        (MARGIN_X, y_bottom), BOX_W, h,
        boxstyle="round,pad=0.01,rounding_size=0.015",
        linewidth=1.2, edgecolor="#333333", facecolor=color, transform=ax.transAxes,
    )
    ax.add_patch(rect)
    ax.text(MARGIN_X + 0.02, y_top - PAD - 0.005, title,
            transform=ax.transAxes, fontsize=11, fontweight="bold", va="top", family="sans-serif")
    for i, line in enumerate(lines):
        ax.text(MARGIN_X + 0.03, y_top - TITLE_H - PAD - i * LINE_H, f"• {line}",
                transform=ax.transAxes, fontsize=9, va="top", family="sans-serif", color="#222222")
    return y_bottom


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    total_h = sum(box_height(len(p[2])) for p in PHASES) + GAP * (len(PHASES) - 1) + 0.12
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.98, "Healthcare Patient Readmission Analysis",
            transform=ax.transAxes, ha="center", va="top", fontsize=16, fontweight="bold")
    ax.text(0.5, 0.955, "End-to-End Architecture (Phase 0 → 5)",
            transform=ax.transAxes, ha="center", va="top", fontsize=11, color="#444444")

    y = 0.92
    prev_center = None
    for title, color, lines in PHASES:
        y_bottom = draw_box(ax, y, title, color, lines)
        center_y = (y + y_bottom) / 2
        if prev_center is not None:
            ax.add_patch(FancyArrowPatch(
                (0.5, prev_center), (0.5, y + 0.005),
                transform=ax.transAxes, arrowstyle="-|>", mutation_scale=14,
                linewidth=1.5, color="#555555",
            ))
        prev_center = y_bottom - 0.005
        y = y_bottom - GAP

    # master.ipynb side note
    ax.text(0.94, 0.5, "master.ipynb\norchestrates\nall phases",
            transform=ax.transAxes, ha="center", va="center", fontsize=8,
            bbox=dict(boxstyle="round", facecolor="#EEEEEE", edgecolor="#999999"),
            rotation=90, color="#333333")

    ax.text(0.5, 0.02,
            "Analytics decision-support only — not a medical device  |  "
            "Regenerate: python scripts/render_architecture_png.py",
            transform=ax.transAxes, ha="center", fontsize=8, color="#666666")

    plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
    fig.savefig(OUT, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
