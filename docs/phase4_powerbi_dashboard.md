# Phase 4 — Power BI Certified Exports

## Notebook

[`notebooks/phase4_powerbi_exports.ipynb`](../notebooks/phase4_powerbi_exports.ipynb)

## Certified sources

Connect Power BI **only** to `data/exports/` — never bronze or raw.

**Prerequisites:** Phase 1 (`mart_readmission.csv`), Phase 3 (predictions, `experiment_results.parquet`, champion register).

## Marts built in Phase 4

| File | Purpose |
|------|---------|
| `mart_readmission.csv` | From Phase 1 — hospital/readmission KPIs (~101k rows) |
| `mart_clinical_risk.csv` | Risk scores, bands, top factors |
| `mart_model_performance.csv` | All experiment metrics |
| `mart_actual_vs_predicted.csv` | Cumulative actual vs predicted rate series |
| `experiments_matrix.csv` | From Phase 3 §6 — 168×13 matrix |
| `mart_dq_scorecard.csv` | From Phase 0 |
| `kpi_snapshot.json` | Executive KPI rollup |
| `powerbi_dashboard_master.csv` | **Single Power BI import** — stacked `record_type` rows |

## Dashboard pages (Phase 4 spec)

| Page | Content |
|------|---------|
| 1. Hospital Overview | Total patients, readmission rate, avg LOS |
| 2. Risk Analysis | Readmission by age, gender, diagnosis |
| 3. Patient Behavior | Visit frequency, medication patterns |
| 4. Model Insights | Feature importance, prediction distribution |
| 5. ML Performance | Champion KPIs, recall bar, experiment matrix, actual vs predicted (**ML only**) |

**Must-haves:** Age / gender / diagnosis filters (synced pages 1–4), KPI cards, drill-down.

## Build instructions

Follow [`powerbi/BUILD_INSTRUCTIONS.md`](../powerbi/BUILD_INSTRUCTIONS.md). Import **only** `data/exports/powerbi_dashboard_master.csv`.

Reference mockups: `powerbi/assets/mockups/page_01_*.png` … `page_05_*.png` (dark neon layout).

## MCP (optional ops)

Phase 4 can use SQLite + Pandas MCP for mart refresh checks; Notifications MCP for KPI drift alerts. See [`mcp.md`](mcp.md).
