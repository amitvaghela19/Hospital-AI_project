# Phase 3 — ML + Model Risk Management

## Notebook

[`notebooks/phase3_ml_experiments.ipynb`](../notebooks/phase3_ml_experiments.ipynb)

## Pipeline order (do not reorder notebook cells)

1. **§4** Helper functions (`format_results_table`, RNN helpers, `RESULT_META_COLS` / `RESULT_METRIC_COLS`)
2. **§4b** Hyperparameter tuning → `models/hyperparams.yaml` (auto-skip when complete; `FORCE_TUNING=1` / `SKIP_TUNING=1`)
3. **§5** Prepare experiment cohort (`MATRIX_SAMPLE=0` = full lake, ~101,766 rows)
4. **§6** Experiment matrix (locked tuned params; tabular metrics; CSV export)
5. **§7** Stacking (LightGBM + CatBoost + XGBoost), horizon-aware members, champion selection
6. **§8** Refit serving champion on full lake (`CHAMPION_SAMPLE=0`)
7. **§9–12** Fairness, SHAP, ablation, calibration
8. **§13** Persist artifacts (pipeline, predictions, parquet, registers)
9. **§14** Summary

Tuning runs **before** the matrix so every model uses the same locked hyperparameters.

## Shared ML package (`ml/`)

| Module | Role |
|--------|------|
| `preprocess.py` | `build_preprocessor` for tabular pipelines |
| `splits.py` | Seven split protocols |
| `sample.py` | `sample_rows` for dev subsampling |
| `tuning.py` | `make_estimator`, `load_hyperparams`, `get_rnn_params` |

Standalone entry: `scripts/tune_hyperparams.py`

## Models

**Base (per horizon × split):** logreg, rf, xgboost, lightgbm, catboost, rnn (when torch available)

**Ensembles (per cell):** `gb_ensemble` (XGB + LGBM + CatBoost), `tri_ensemble` (top-3 by val recall)

**Stacking (§7, primary protocol only):** level-0 LightGBM + CatBoost + XGBoost → meta-learner `LogisticRegression`

**Serving rule:** Matrix winner may be an ensemble; served model defaults to **RF** for interpretability (see `champion_register.json`).

## Experiment matrix (§6)

- **168 runs** = 3 horizons × 7 splits × 8 model slots (6 base + 2 ensembles)
- **Horizons:** 30d (primary), 60d/90d (proxy labels)
- **Splits:** 80/20, 70/30, 75/25, 65/35, 60/40, 60/20/20, **70/15/15** (primary)
- **Thresholds:** recall-first on validation set per run
- **Metrics table:** accuracy, precision, recall, f1, roc_auc (4 decimal places)

### `experiments_matrix.csv`

Written at end of §6 to `data/exports/experiments_matrix.csv` — **168 rows × 13 columns** (matrix runs only; stacking row excluded).

| Column | Description |
|--------|-------------|
| model, horizon, split | Run identity |
| threshold | Tuned decision threshold |
| train_size, val_size, test_size | Split sizes |
| ensemble | `True` for gb/tri ensembles |
| accuracy, precision, recall, f1, roc_auc | Test metrics |

## Primary protocol

70/15/15 + 30d. Champion selected by **recall then ROC-AUC** on primary split.

Full lake defaults: `MATRIX_SAMPLE=0`, `CHAMPION_SAMPLE=0`.

## Hyperparameters

| Env | Effect |
|-----|--------|
| `SKIP_TUNING=1` | Reuse existing `models/hyperparams.yaml` |
| `FORCE_TUNING=1` | Re-run search even if yaml is complete |
| `TUNING_N_ITER` | RandomizedSearchCV iterations (default 25) |
| `TUNING_CV` | CV folds (default 3) |
| `RNN_OPTUNA_TRIALS` | Optuna trials for RNN (default 20) |

Auto-skip tuning when yaml has all tabular + RNN params (unless `FORCE_TUNING=1`).

## Model risk management

- SHAP / permutation importance (top factors)
- Fairness by gender and age buckets
- Feature ablation by clinical group
- Brier score / calibration
- Offline A/B: champion vs next-best on primary protocol
- `models/model_card.json` + `models/champion_register.json`

## Advanced inference artifacts

Produced in §13 or via `scripts/train_advanced_artifacts.py`:

- `models/rnn_primary.pt`, `models/rnn_token_maps.json`
- `models/shadow_tri_ensemble.joblib`, `models/shadow_register.json`
- `models/routing_config.json` (uncertainty band for RF→RNN routing)

See [`ADVANCED_INFERENCE.md`](ADVANCED_INFERENCE.md).

## Outputs

| Artifact | Location |
|----------|----------|
| Experiment matrix CSV | `data/exports/experiments_matrix.csv` |
| Full results (+ stacking) | `data/lake/gold/experiment_results.parquet` |
| Test predictions | `data/lake/gold/test_predictions.parquet` |
| Matrix predictions | `data/lake/gold/matrix_predictions.parquet` |
| Champion pipeline | `models/champion_pipeline.joblib` |
| Hyperparameters | `models/hyperparams.yaml` |
| Registers / cards | `models/champion_register.json`, `models/model_card.json`, `models/ab_test_result.json` |
