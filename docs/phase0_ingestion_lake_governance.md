# Phase 0 — Ingestion, Lake, Governance, DQ, Metadata, RBAC

## Notebook

[`notebooks/phase0_ingestion_lake_governance.ipynb`](../notebooks/phase0_ingestion_lake_governance.ipynb)

## Objective

Land raw hospital encounter files into an immutable medallion lake with DQ gates.

## Intended use

Analytics only. Not a medical device.

## Inputs

All `role=raw` paths in [`datafile.txt`](../datafile.txt) (primary: `data/raw/diabetic_data.csv`, ~101,766 rows).

## Steps

1. Load every registered raw CSV
2. Write bronze landing file `data/lake/bronze/encounters_raw.parquet` (refreshed each run)
3. Run DQ checks (completeness, uniqueness, validity, consistency, timeliness)
4. Fail fast on critical failures
5. Promote silver parquet and update registry
6. Write manifest, metadata catalog, RBAC role definitions

Batch DQ logic is also available in `governance/dq_rules.py` (`batch_dq_checks`) for reuse.

## Outputs

| Artifact | Path |
|----------|------|
| Silver encounters | `data/lake/silver/encounters.parquet` |
| DQ scorecard | `data/exports/mart_dq_scorecard.csv` |
| Manifest | `data/lake/bronze/_manifests/latest.json` |
| RBAC + metadata | `data/nosql/*` |

## PHI patterns

`encounter_id` and `patient_nbr` are restricted identifiers. Viewer role must not display them.

## Live inference DQ (Phase 5)

`governance/dq_rules.py` → `validate_inference_row()` applies scoring-time checks (LOS range, gender domain, completeness). See [`ADVANCED_INFERENCE.md`](ADVANCED_INFERENCE.md).

## Sign-off

- [ ] DQ scorecard has no critical failures
- [ ] Registry updated in `datafile.txt`
