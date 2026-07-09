# Master Report — Healthcare Patient Readmission Analysis

**Project:** Hospital Readmission Risk Analytics (Diabetes 130-US Hospitals)  
**Report date:** July 2026  
**Status:** Ready for GitHub upload and Streamlit Cloud deploy (with notes below)  
**Smoke tests:** 59/59 passing (`python -m unittest scripts.smoke_test_gold_standard`)

---

## 1. Executive summary

This project delivers an end-to-end **30-day readmission** analytics platform: medallion data lake, SQL warehouse, statistical feature engineering, ML experiment matrix with model risk management, Power BI exports, and a production-style **Streamlit** clinician dashboard with **RBAC**, **grounded chat**, and **read-only security** for patient confidentiality.

| Dimension | Summary |
|-----------|---------|
| **Dataset** | ~101,766 encounters; ~11.2% 30-day readmission rate |
| **Champion model** | CatBoost; recall ~71.6%; ROC AUC ~66.4% |
| **App** | 8 Streamlit pages; 3 RBAC modes; 59 automated smoke tests |
| **Security** | Read-only in Viewer, Clinician, and Analyst; chatbot refuses data mutation |
| **Deploy target** | GitHub + Streamlit Cloud (`app_streamlit.py`) |

> **Disclaimer:** Analytics decision-support only. Not a medical device. Not for standalone clinical decisions.

---

## 2. Pre-deploy audit checklist

| Check | Result | Notes |
|-------|--------|-------|
| Streamlit entrypoint | ✅ | `app_streamlit.py` |
| Certified exports present | ✅ | 8 files in `data/exports/` (~45 MB total) |
| Champion register | ✅ | `models/champion_register.json` |
| Hyperparameters | ✅ | `models/hyperparams.yaml` |
| SQL analytical queries | ✅ | 12 files in `sql/` |
| App pages | ✅ | 8 pages in `streamlit_app/app_pages/` |
| Smoke test suite | ✅ | 59 tests OK |
| RBAC secrets example | ✅ | `.streamlit/secrets.toml.example` |
| Secrets not committed | ✅ | `.streamlit/secrets.toml` in `.gitignore` |
| Read-only security module | ✅ | `streamlit_app/security.py` |
| Chat mutation refusal | ✅ | Viewer, Clinician, Analyst tested |
| SQL write blocked | ✅ | `mcp/services/sqlite_svc.py` |
| Read-only UI tables | ✅ | `render_readonly_table()` — no dataframe editing UI |
| Git initialized | ⚠️ | Run `git init` before first push |
| Scoring joblib on Cloud | ✅ | Small joblib/pt files committed (~1 MB) |

---

## 3. Architecture (condensed)

```
diabetic_data.csv
    → Phase 0: Bronze/Silver lake + DQ
    → Phase 1: SQLite warehouse + Kimball marts
    → Phase 2: Gold features + EDA
    → Phase 3: 168-run ML matrix + champion + SHAP
    → Phase 4: Certified CSV exports + KPI snapshot
    → Phase 5: Streamlit app + MCP + grounded chat
```

**Full diagrams:** [`docs/PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md) · [`final architecture v2.png`](../final%20architecture%20v2.png)

**Path registry:** [`datafile.txt`](../datafile.txt) (17 registered artifacts)

---

## 4. Streamlit application

### 4.1 Pages

| # | Page | RBAC | Key features |
|---|------|------|--------------|
| 1 | Hospital Overview | All | KPIs, gender chart, top high-risk table |
| 2 | Risk Analysis | All | Age/gender/diagnosis donuts, high-risk chart |
| 3 | Patient Behavior | All | Visit/med patterns with drill-down filters |
| 4 | Model Insights | Clinician+ | SHAP importance, prediction buckets, risk bands |
| 5 | ML Performance | Analyst | Recall chart, actual vs predicted, full experiment matrix (recall descending) |
| 6 | Risk Prediction | Clinician+ | Encounter select, 8-step pipeline, clinical report |
| 7 | Grounded Chat | All | Tribunal, scripts, RAG, SQL (Analyst), mutation refusal |
| 8 | System Health | All | Artifact checklist, diagnostics, LLM provider |

### 4.2 RBAC matrix

| Capability | Viewer | Clinician | Analyst |
|------------|:------:|:---------:|:-------:|
| Aggregate dashboards | ✅ | ✅ | ✅ |
| Encounter ID in tables | ❌ | ✅ | ✅ |
| Patient ID (3rd column) | ❌ | ❌ | ✅ |
| Model Insights page | ❌ | ✅ | ✅ |
| ML Performance page | ❌ | ❌ | ✅ |
| Risk Prediction / scoring | ❌ | ✅ | ✅ |
| SQL chat (SELECT only) | ❌ | ❌ | ✅ |
| High-risk list in chat | ❌ | ✅ | ✅ |
| **Add/update/delete data** | ❌ | ❌ | ❌ |

Elevation: password in sidebar Access control. Demo defaults (`baguvix` / `aezakmi`) work on local and Streamlit Cloud; Streamlit Secrets override when set. Session proof signed with `RBAC_AUTH_SECRET` (auto-generated per session if omitted).

### 4.3 Dashboard UX (recent)

- Full-width professional Plotly charts with consistent margins and legends
- Diagnosis donut: large chart, right-side legend
- High-risk table: no “Top risk factors” column; Patient ID as 3rd column (Analyst only)
- Experiment matrix: all rows, sorted by recall descending
- Cohort filters sync across pages; chart drill-down to sidebar filters

---

## 5. Security & confidentiality

### 5.1 Design principles

1. **Certified data is immutable in the app** — no UI path writes to CSV, SQLite warehouse, or nosql stores from Streamlit.
2. **All RBAC modes are read-only** for patient/encounter records.
3. **Chatbot enforces policy** before routing to SQL, RAG, or LLM.
4. **Analyst SQL is SELECT-only** — INSERT/UPDATE/DELETE/DROP rejected.

### 5.2 Implementation map

| Layer | File | Behavior |
|-------|------|----------|
| Mutation detection | `streamlit_app/security.py` | Pattern match on chat input |
| Chat routing | `streamlit_app/routing.py` | Early refuse + audit log |
| Tribunal | `inference/tribunal.py` | `clinical_guard` blocks mutations |
| SQL | `mcp/services/sqlite_svc.py` | SELECT-only + write keyword block |
| UI tables | `streamlit_app/components/readonly_table.py` | Static `st.table` |
| LLM prompts | `mcp/services/http_svc.py` | Hard rule: never modify records |

### 5.3 Chatbot refusal (example)

> **No — for security reasons this cannot be done.** The hospital readmission platform is **read-only** in Viewer, Clinician, and Analyst modes…

### 5.4 What is NOT exposed to end users

- RBAC passwords (server-side Secrets only)
- Raw `.env` / `secrets.toml` (gitignored)
- Ability to alter audit trail via chat (append-only audit at runtime)

---

## 6. Data inventory (committed for deploy)

| File | Size (approx.) | Purpose |
|------|----------------|---------|
| `mart_readmission.csv` | 6.8 MB | Hospital/readmission KPIs |
| `mart_clinical_risk.csv` | 1.7 MB | Scored encounters + risk bands |
| `mart_model_performance.csv` | 18 KB | Champion metrics |
| `mart_actual_vs_predicted.csv` | 498 KB | Calibration curve |
| `experiments_matrix.csv` | 13 KB | 168 × 13 experiment rows |
| `mart_dq_scorecard.csv` | small | DQ export |
| `kpi_snapshot.json` | small | Dashboard KPIs |
| `powerbi_dashboard_master.csv` | 37 MB | Stacked Power BI master (optional) |

**Seed nosql (committed):** `rag_documents.json`, `metric_dictionary.json`, `feature_dictionary.json`, `metadata_catalog.json`, `rbac_roles.json`, `learned_answers.json`

**Runtime nosql (gitignored):** `audit_events.json`, `chat_sessions.json`, `chat_feedback.json`, `pipeline_runs.json`

---

## 7. Model performance

| Field | Value |
|-------|-------|
| Champion | CatBoost |
| Horizon | 30d |
| Split | 70/15/15 |
| Recall | 71.6% |
| ROC AUC | 66.4% |
| Precision | ~15.5% |
| F1 | ~25.4% |
| Threshold | ~0.45 (recall-first) |

**Top SHAP features:** `number_inpatient`, `discharge_disposition_id`, `total_visits`, `number_diagnoses`, `time_in_hospital`

**Fairness:** Subgroup recall tracked in register (gender, age bands) — see `models/champion_register.json`

**Experiment matrix:** 168 configurations across models, horizons, splits — full table on ML Performance page.

---

## 8. Deploy notes & limitations

### 8.1 GitHub first push

```powershell
cd "path\to\Hospital project"
git init
git add .
git commit -m "feat: hospital readmission analytics platform"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Review `git status` — confirm `.streamlit/secrets.toml` and `.venv/` are **not** staged.

### 8.2 Streamlit Cloud

| Setting | Value |
|---------|-------|
| Repository | Your GitHub repo |
| Branch | `main` |
| Main file | `app_streamlit.py` |
| Python | 3.11+ recommended |
| First deploy build | Allow 5–10 min (`requirements.txt` includes CatBoost + PyTorch) |

**Optional Secrets (recommended for production):** `RBAC_CLINICIAN_PASSWORD`, `RBAC_ANALYST_PASSWORD`, `RBAC_AUTH_SECRET`

If omitted, demo passwords apply: Clinician `baguvix`, Analyst `aezakmi` (same as local).

### 8.3 Live scoring on Cloud

Small scoring artifacts are **committed** (~1 MB total):

- `models/champion_pipeline.joblib`
- `models/shadow_tri_ensemble.joblib`
- `models/rnn_primary.pt`

Risk Prediction and the 8-step pipeline work on Streamlit Cloud without Git LFS. Re-run `python scripts/train_advanced_artifacts.py` after retraining.

### 8.4 Ollama / LLM on Cloud

Streamlit Cloud cannot run Ollama locally. Use:

- Sidebar **custom LLM provider** (OpenAI-compatible API), or
- `OLLAMA_URL` pointing to a secure tunnel you operate

Chat still returns deterministic answers when LLM is unavailable.

### 8.5 Optional local-only services

Redis, MQTT, Docker MCP stack — enhance caching and IDE tooling but **not required** for Cloud dashboard deploy.

---

## 9. Testing

```powershell
python -m unittest scripts.smoke_test_gold_standard -v
```

| Suite | Tests | Coverage |
|-------|------:|----------|
| Imports / pages | 2+ | All modules and app pages load |
| RBAC / auth | 10+ | Elevation, lockout, masking |
| Charts / theme | 11+ | Donut layout, margins, labels |
| Security | 3 | Mutation detect, SQL block, chat refuse (all roles) |
| Routing / chat | 5+ | High-risk, SQL gate, scripts |
| **Total** | **70** | All passing at report time |

---

## 10. Repository deliverables

| Deliverable | Location |
|-------------|----------|
| Phase notebooks (0–5) | `notebooks/` |
| Master orchestrator | `master.ipynb` |
| SQL queries (12) | `sql/` |
| Streamlit app | `app_streamlit.py`, `streamlit_app/` (incl. `app_pages/`) |
| Power BI | `powerbi/BUILD_INSTRUCTIONS.md`, mockups |
| MCP docs | `docs/mcp.md` |
| Architecture | `docs/PROJECT_ARCHITECTURE.md` |
| Smoke tests | `scripts/smoke_test_gold_standard.py` |
| This report | `docs/MASTER_REPORT.md` |

---

## 11. Sign-off

| Area | Ready for GitHub | Ready for Streamlit Cloud |
|------|:----------------:|:-------------------------:|
| README & docs | ✅ | ✅ |
| Certified exports | ✅ | ✅ |
| Model register JSON | ✅ | ✅ |
| RBAC + security | ✅ | ✅ (demo passwords or Secrets) |
| Smoke tests | ✅ | ✅ (run locally pre-push) |
| Live ML scoring | ✅ local | ✅ with committed joblib |
| Ollama chat formatting | ✅ local | ⚠️ needs external LLM/tunnel |

**Recommendation:** Push to GitHub with current exports and register. Deploy to Streamlit Cloud with Secrets configured. Use **System Health Diagnose** as the first post-deploy check. Add joblib via LFS or release if Risk Prediction scoring is required in production.

---

*Generated as part of pre-release audit. Update this report when champion model, exports, or RBAC policy changes.*
