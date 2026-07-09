# Phase 1 — Modeling Layer, Metric Dictionary, Marts, SQL

## Notebook

[`notebooks/phase1_modeling_marts_sql.ipynb`](../notebooks/phase1_modeling_marts_sql.ipynb)

## Objective

Build Kimball-style dimensional model and certified analytics marts.

## Data dictionary (grain)

| Table | Grain |
|-------|-------|
| `dim_patient` | One row per `patient_nbr` |
| `fact_admission` | One row per `encounter_id` |
| `fact_medication` | Medication flags per encounter |
| `fact_lab` | Lab fields per encounter |

## Metric dictionary

| Metric | Definition |
|--------|------------|
| readmission_rate_30d | sum(readmit_30d) / count(encounters) |
| avg_los | avg(time_in_hospital) |
| high_risk_rate | share risk_band=High in scored mart |
| frequent_visitor | number_inpatient >= 2 OR total_visits >= 3 |

## SQL

Twelve queries in `sql/` including the seven brief-required analyses.

## Database (warehouse)

**Default:** portable **SQLite** at `data/warehouse/hospital.db` via SQLAlchemy.

Set `DATABASE_URL` for PostgreSQL/MySQL. This is a **dimensional analytics warehouse** at portfolio scale (~101k rows), not a distributed big-data platform.

## Vector / RAG seed

Phase 1 seeds:

- `data/nosql/rag_documents.json`
- `data/nosql/metric_dictionary.json`
- Chroma collection `project_knowledge` in `data/vectordb/`

Used by Phase 5 chat RAG and MCP semantic tools.

## Outputs

| Artifact | Zone |
|----------|------|
| `data/warehouse/hospital.db` | Warehouse |
| `data/exports/mart_readmission.csv` | Certified export |
| `data/nosql/metric_dictionary.json` | Ops |
| `data/nosql/rag_documents.json` | Ops |
| `data/vectordb/` | Ops (Chroma) |

## Consumers

Phase 4 (Power BI), Phase 5 (metrics chat, SQLite MCP), MCP Pandas/SQLite servers.
