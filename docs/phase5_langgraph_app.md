# Phase 5 — Clinician Tool (Streamlit + LangGraph + MCP)

## Artifacts

| Item | Path |
|------|------|
| Notebook | [`notebooks/phase5_langgraph_app.ipynb`](../notebooks/phase5_langgraph_app.ipynb) |
| App entry | [`app_streamlit.py`](../app_streamlit.py) (Home / Setup) |
| Multipage UI | [`pages/`](../pages/) + [`streamlit_app/`](../streamlit_app/) |
| Theme | [`.streamlit/config.toml`](../.streamlit/config.toml), `streamlit_app/theme.css` |
| Chat scripts | `chatbot/scripts/*.json` |
| Advanced inference | `inference/`, `governance/dq_rules.py` |

## Safety

Persistent disclaimer: **analytics decision-support only** — not a medical device.

## Launch

```powershell
streamlit run app_streamlit.py
```

Optional: `ollama pull deepseek-r1` and `ollama pull llama3`

## Multipage app

| Page | Purpose |
|------|---------|
| **Home** (`app_streamlit.py`) | System health, artifact checklist, Chroma index bootstrap |
| **Hospital Overview** | KPI cards from `data/exports/kpi_snapshot.json` |
| **Risk Analysis** | Readmission by age / gender / diagnosis (master CSV charts) |
| **Patient Behavior** | Visit frequency and medication patterns |
| **Model Insights** | Feature importance, prediction distribution, model card |
| **ML Performance** | Champion recall, actual vs predicted, experiment matrix sample |
| **Risk Prediction** | Encounter lookup, DQ gate, routing, shadow, similar cohort |
| **Grounded Chat** | Tribunal or flat router, chat history, suggested prompts |

## Setup flow (first run)

1. Run Phase 3 to produce `models/champion_pipeline.joblib` (gitignored).
2. Optional: `python scripts/train_advanced_artifacts.py` for shadow + RNN.
3. On **Home**, click **Index Chroma neighbors** (or run `scripts/index_encounter_neighbors.py`).
4. Optional: start Ollama and Redis for LLM phrasing and cache.

The app **lazy-loads** the champion pipeline so a missing model shows a setup page instead of crashing at import.

## Risk prediction page

1. **RBAC** — role must allow `predict`
2. **Encounter lookup** — select from gold features or grouped manual form
3. **DQ gate** — `governance/dq_rules.py` blocks invalid rows before scoring
4. **Champion RF** — `models/champion_pipeline.joblib`
5. **Uncertainty routing** — `inference/routing.py` escalates to RNN when RF prob in band (default 0.35–0.55)
6. **Shadow model** — `inference/shadow.py` scores tri_ensemble alongside RF; flags disagreement
7. **Similar cohort** — Chroma `encounter_neighbors` via MCP pool
8. **Risk band + explanation** — Ollama phrasing (primary/fallback) or template with visible fallback warning
9. **Audit** — `data/nosql/audit_events.json`

## Chat page

- **MCP Model Tribunal** (default on) — `inference/tribunal.py` multi-gate workflow; stages shown in UI; audit logged in tribunal
- **Flat router** (checkbox off) — scripts → metrics → RAG → SQLite → refuse; audit on each turn
- **RBAC** — SQL and FRED restricted by role (`viewer` / `clinician` blocked for SQL)
- **Similarity** — uses last scored encounter from Risk Prediction when available
- **RAG mode** — caption shows Chroma vs keyword fallback

Routes: `script_qa`, `semantic_metric_mcp`, `vector_rag_mcp`, `sqlite_mcp`, `fred_mcp`, `similarity_mcp`, `refuse`

## LLM (Ollama Desktop)

| Role | Model |
|------|-------|
| Primary | `deepseek-r1` (`OLLAMA_PRIMARY`) |
| Fallback | `llama3` (`OLLAMA_FALLBACK`) |
| Last resort | Deterministic template |

LLM **phrases** risk explanations only — never diagnoses or prescribes.

## Notebook sections (reference)

| § | Topic |
|---|-------|
| 1–3 | Setup, champion load, risk helpers |
| 4–6 | Script matcher, semantic metrics, RAG |
| 7 | Ollama phrasing |
| 8 | `predict_row` |
| 9 | LangGraph-style router |
| 10b | MCP runtime router |
| 10c | MCP Model Tribunal |
| 11 | Launch Streamlit |

## RBAC

Roles: `admin` / `analyst` / `clinician` / `viewer` — see `data/nosql/rbac_roles.json`.

## Verification checklist

1. **Cold start** — rename `champion_pipeline.joblib` temporarily → Home loads with red champion status, no traceback.
2. **Full stack** — restore model + index neighbors → similar cohort and RNN route work when artifacts exist.
3. **Chat** — Tribunal on → stages in expander; scripted question returns `script_qa`.
4. **Analytics** — all five dashboard pages render from `data/exports/` without manual upload.
5. **Theme** — dark neon via `.streamlit/config.toml` and `theme.css`.

## Related docs

- [`ADVANCED_INFERENCE.md`](ADVANCED_INFERENCE.md) — five advanced capabilities in detail
- [`mcp.md`](mcp.md) — 18-server MCP fleet and runtime pool
- [`phase4_powerbi_dashboard.md`](phase4_powerbi_dashboard.md) — parallel Power BI page spec
