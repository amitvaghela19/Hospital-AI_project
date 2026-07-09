# Phase 2 — Cohort, Stats, Features

## Notebook

[`notebooks/phase2_stats_features.ipynb`](../notebooks/phase2_stats_features.ipynb)

## Cohort

- Index encounter = Diabetes 130 admission row (~101,766 encounters)
- Primary outcome: `readmit_30d` (`readmitted == '<30'`)
- 60/90-day labels are **proxies** (any readmission) — not true calendar follow-up
- CMS-style exclusions (death/transfer/planned) **not available** in source fields

## Required EDA (§6)

Five plots — shown **inline** in the notebook and exported to `data/exports/eda/`:

| Plot | Topic |
|------|-------|
| Readmission distribution | 30-day rate |
| Age | Readmission by age band |
| LOS | Length of stay (line chart) |
| Medications | Active med count vs readmission |
| Admission type | Admission source/type patterns |

Helper: `show_saved()` displays PNGs without breaking `matplotlib.use("Agg")`.

## Inferential stats

Chi-square and Mann-Whitney tests on key categorical/numeric factors (documented in notebook).

## Leakage denylist

Excluded from model features: `encounter_id`, `patient_nbr`, `readmitted`, `readmit_*` labels

## Gold outputs

| Artifact | Description |
|----------|-------------|
| `data/lake/gold/model_features.parquet` | ~30 leakage-controlled columns |
| `data/lake/gold/rnn_sequences.parquet` | Diagnosis + medication token sequences per encounter |
| `data/nosql/feature_dictionary.json` | Feature definitions and dtypes |

## Consumers

Phase 3 (ML matrix), Phase 5 (default form values in Streamlit).
