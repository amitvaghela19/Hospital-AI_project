# Documentation index

All project documentation lives in this folder. Start with [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md). For GitHub + Streamlit Cloud deploy, see [`MASTER_REPORT.md`](MASTER_REPORT.md).

## Phase guides

| Phase | Doc | Notebook |
|------:|-----|----------|
| 0 | [`phase0_ingestion_lake_governance.md`](phase0_ingestion_lake_governance.md) | `notebooks/phase0_ingestion_lake_governance.ipynb` |
| 1 | [`phase1_modeling_marts_sql.md`](phase1_modeling_marts_sql.md) | `notebooks/phase1_modeling_marts_sql.ipynb` |
| 2 | [`phase2_stats_features.md`](phase2_stats_features.md) | `notebooks/phase2_stats_features.ipynb` |
| 3 | [`phase3_ml_experiments.md`](phase3_ml_experiments.md) | `notebooks/phase3_ml_experiments.ipynb` |
| 4 | [`phase4_powerbi_dashboard.md`](phase4_powerbi_dashboard.md) | `notebooks/phase4_powerbi_exports.ipynb` |
| 5 | [`phase5_langgraph_app.md`](phase5_langgraph_app.md) | `notebooks/phase5_langgraph_app.ipynb` |

## Cross-cutting

| Topic | Doc |
|-------|-----|
| Full architecture | [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md) |
| **Master report (deploy audit)** | [`MASTER_REPORT.md`](MASTER_REPORT.md) |
| Architecture v2 diagram | [`../final architecture v2.mmd`](../final%20architecture%20v2.mmd) |
| MCP (18 servers) | [`mcp.md`](mcp.md) |
| Advanced inference | [`ADVANCED_INFERENCE.md`](ADVANCED_INFERENCE.md) |

## Diagrams

| File | Purpose |
|------|---------|
| [`diagrams/project_architecture.mmd`](diagrams/project_architecture.mmd) | Compact pipeline Mermaid |
| [`diagrams/mcp_architecture.mmd`](diagrams/mcp_architecture.mmd) | MCP two-layer Mermaid |
| [`diagrams/project_architecture.png`](diagrams/project_architecture.png) | Compact PNG (regenerate via `scripts/render_architecture_png.py`) |

## Key artifacts (registry)

See [`../datafile.txt`](../datafile.txt) for the canonical path list (17 entries including `experiments_matrix.csv` and `hyperparams.yaml`).
