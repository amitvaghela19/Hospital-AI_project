# Healthcare Patient Readmission Analysis

Gold-standard **enterprise healthcare analytics** for **30-day hospital readmission** risk using the **Diabetes 130-US Hospitals** dataset (~101,766 encounters).

> **Intended use:** Analytics decision-support for training and portfolio demonstration only. **Not** a medical device and **not** for standalone clinical decisions.

---

## Highlights

| Area | What you get |
|------|----------------|
| **Data** | Medallion lake → SQLite Kimball warehouse → certified CSV marts |
| **ML** | 168-run experiment matrix; CatBoost champion (recall-first); SHAP factors |
| **BI** | Power BI mockups + `powerbi_dashboard_master.csv` |
| **App** | 8-page Streamlit dashboard with RBAC, interactive charts, grounded chat |
| **Security** | **Read-only in all modes** — Viewer, Clinician, and Analyst cannot add/update/delete patient data |
| **Tests** | 70 smoke tests (`scripts/smoke_test_gold_standard.py`) |

**Architecture:** [`docs/PROJECT_ARCHITECTURE.md`](docs/PROJECT_ARCHITECTURE.md) · **Master report:** [`docs/MASTER_REPORT.md`](docs/MASTER_REPORT.md)

---

## Streamlit app (8 pages)

| Page | Access | Purpose |
|------|--------|---------|
| Hospital Overview | All | KPIs, gender chart, top high-risk encounters |
| Risk Analysis | All | Age/gender/diagnosis charts, high-risk table |
| Patient Behavior | All | Visit frequency and medication patterns |
| Model Insights | Clinician+ | Feature importance, prediction distribution, risk bands |
| ML Performance | Analyst | Champion metrics, experiment matrix (sorted by recall) |
| Risk Prediction | Clinician+ | 8-step inference pipeline + clinical report |
| Grounded Chat | All | Scripts, metrics, RAG, SQL read-only (Analyst) |
| System Health Diagnose | All | Prerequisites, diagnostics, LLM provider setup |

### RBAC (password-gated)

| Mode | Dashboards | Encounter IDs | Patient IDs | SQL chat | Live scoring |
|------|------------|---------------|-------------|----------|--------------|
| **Viewer** (default) | Aggregate | Hidden | Hidden | No | No |
| **Clinician** | + Model Insights, Prediction | Yes | Masked | No | Yes |
| **Analyst** | + ML Performance | Yes | Yes | SELECT only | Yes |

Unlock via **Access control** in the sidebar. Default demo passwords work on **local and Streamlit Cloud** (`baguvix` / Clinician, `aezakmi` / Analyst). Override via [`.streamlit/secrets.toml`](.streamlit/secrets.toml) locally or **Streamlit Cloud Secrets** for production.

### Read-only data policy (all modes)

- Certified marts and tables are **display-only** (`st.table` — no in-app editing).
- Chatbot **refuses** add/update/delete/falsify requests with a security message.
- Analyst SQL is **SELECT-only** — write keywords are blocked.
- See [`streamlit_app/security.py`](streamlit_app/security.py).

---

## Quick start (local)

### 1. Environment

**Python 3.11+** recommended (matches Streamlit Cloud).

```powershell
cd "path\to\Hospital project"
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m ipykernel install --user --name hospital-dotvenv --display-name "Hospital Project (.venv)"
```

Select kernel **Hospital Project (.venv)** in Jupyter/Cursor before running notebooks.

### 2. Run the app

```powershell
streamlit run app_streamlit.py
```

Open `http://localhost:8501`. Default mode is **Viewer**.

### 3. Run the full pipeline (optional — rebuild artifacts)

```powershell
# Open master.ipynb or notebooks/phase0…phase5 and Run All
# Or execute master.ipynb headless (see notebook docs)
```

Paths are registered in [`datafile.txt`](datafile.txt) — edit that file to add/remove datasets without code changes.

### 4. Verify before deploy

```powershell
python -m unittest scripts.smoke_test_gold_standard -v
python scripts/mcp_healthcheck.py   # optional; needs Docker MCP stack
```

---

## Deploy to GitHub + Streamlit Cloud

### What to commit

| Include | Exclude (`.gitignore`) |
|---------|-------------------------|
| `app_streamlit.py`, `streamlit_app/` (includes `app_pages/`) | `.venv/`, `.env` |
| `data/exports/*.csv`, `kpi_snapshot.json` | `data/lake/`, `data/warehouse/` |
| `models/*.json`, `models/hyperparams.yaml` | `.streamlit/secrets.toml`, `.venv/` |
| `models/champion_pipeline.joblib`, `shadow_tri_ensemble.joblib`, `rnn_primary.pt` (~1 MB) | Runtime nosql (audit, chat sessions) |
| `data/nosql/` seed JSON (rag, metrics, rbac) | Large raw CSV / zip, `catboost_info/` |
| `chatbot/`, `mcp/`, `requirements.txt` | |
| `docs/`, `sql/`, `powerbi/` instructions | |

> **Risk Prediction on Cloud:** Small scoring artifacts above are included in the repo so live inference works after deploy without Git LFS. Re-run `python scripts/train_advanced_artifacts.py` locally if you change the champion model.

### First-time Git (if not initialized)

```powershell
git init
git add .
git status   # confirm secrets.toml and .venv are NOT listed
git commit -m "feat: hospital readmission analytics platform"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Full pre-deploy checklist: [`docs/MASTER_REPORT.md`](docs/MASTER_REPORT.md) §2 and §8.

### Streamlit Cloud setup

1. Push repo to GitHub.
2. [share.streamlit.io](https://share.streamlit.io) → **New app** → select repo.
3. **Main file path:** `app_streamlit.py`
4. **Secrets (optional)** — RBAC works out of the box with demo passwords (`baguvix` / `aezakmi`). Set Secrets to override (see [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example)):

```toml
# Optional — omit to use demo defaults (baguvix / aezakmi)
RBAC_CLINICIAN_PASSWORD = "your-strong-clinician-password"
RBAC_ANALYST_PASSWORD = "your-strong-analyst-password"
RBAC_AUTH_SECRET = "long-random-string-for-session-hmac"
```

5. **Optional LLM** (for chat formatting): configure a custom OpenAI-compatible API in the sidebar after unlocking Clinician/Analyst, or tunnel Ollama:

```toml
OLLAMA_URL = "https://your-tunnel.example.com"
OLLAMA_PRIMARY = "deepseek-r1:latest"
OLLAMA_FALLBACK = "llama3:latest"
```

6. Deploy. Run **System Health Diagnose** in the app to confirm exports and register load.

> **Build time:** `requirements.txt` includes ML stack (CatBoost, PyTorch). First Cloud deploy may take several minutes. Dashboards work without local Ollama or Docker MCP.

---

## Phase map

| Phase | Notebook | Document |
|------:|----------|----------|
| 0 | `notebooks/phase0_ingestion_lake_governance.ipynb` | `docs/phase0_ingestion_lake_governance.md` |
| 1 | `notebooks/phase1_modeling_marts_sql.ipynb` | `docs/phase1_modeling_marts_sql.md` |
| 2 | `notebooks/phase2_stats_features.ipynb` | `docs/phase2_stats_features.md` |
| 3 | `notebooks/phase3_ml_experiments.ipynb` | `docs/phase3_ml_experiments.md` |
| 4 | `notebooks/phase4_powerbi_exports.ipynb` | `docs/phase4_powerbi_dashboard.md` |
| 5 | `notebooks/phase5_langgraph_app.ipynb` | `docs/phase5_langgraph_app.md` |

Orchestrator: [`master.ipynb`](master.ipynb)

---

## Model & metrics (current register)

| Metric | Value |
|--------|-------|
| Champion | CatBoost (30d horizon) |
| Recall | ~71.6% |
| ROC AUC | ~66.4% |
| Threshold | ~0.45 (recall-first) |

Artifacts: `models/champion_register.json`, `data/exports/experiments_matrix.csv` (168 rows), `data/exports/mart_clinical_risk.csv`.

Top SHAP drivers (typical): prior inpatient visits, discharge disposition, total visits, diagnoses count, length of stay.

---

## Configuration

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy URL (default SQLite warehouse) |
| `OLLAMA_URL` | Default `http://localhost:11434` |
| `OLLAMA_PRIMARY` / `OLLAMA_FALLBACK` | LLM models for chat formatting |
| `RBAC_CLINICIAN_PASSWORD` / `RBAC_ANALYST_PASSWORD` | Override demo passwords (defaults: `baguvix` / `aezakmi`) |
| `RBAC_AUTH_SECRET` | Session HMAC for elevation proof |
| `MATRIX_SAMPLE` / `CHAMPION_SAMPLE` | Dev sampling (`0` = full lake) |
| `SKIP_TUNING` | `1` reuses `models/hyperparams.yaml` |
| `REDIS_URL` | Optional Ollama response cache |
| `FRED_API_KEY` | Optional macro data (Analyst chat) |

See [`docs/ADVANCED_INFERENCE.md`](docs/ADVANCED_INFERENCE.md) for uncertainty routing, shadow model, DQ gate, and MCP tribunal.

---

## Power BI

See [`powerbi/BUILD_INSTRUCTIONS.md`](powerbi/BUILD_INSTRUCTIONS.md). Connect to marts in `data/exports/` or the stacked `powerbi_dashboard_master.csv`.

---

## MCP integration (local / IDE)

18 MCP servers for Cursor + runtime pool (`mcp/client/pool.py`):

```powershell
docker compose -f docker-compose.mcp.yml up -d
python scripts/mcp_healthcheck.py
```

See [`docs/mcp.md`](docs/mcp.md) and [`.cursor/mcp.json`](.cursor/mcp.json).

---

## Repository layout

```
app_streamlit.py          # Streamlit entry
streamlit_app/            # Charts, RBAC, routing, security, theme
  app_pages/              # 8 dashboard pages
data/exports/             # Certified marts (commit for Cloud)
models/                   # Register JSON + hyperparams (joblib optional)
notebooks/                # Phase 0–5
scripts/                  # Smoke tests, Power BI build, tuning
sql/                      # 12 analytical queries
chatbot/                  # Scripts + training Q&A
docs/                     # Phase docs + MASTER_REPORT.md
powerbi/                  # Build instructions + mockups
```

---

## License & disclaimer

Portfolio / educational project. Do not use for real patient care decisions without institutional governance, IRB, and validated clinical workflows.
