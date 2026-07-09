# Power BI Dashboard — Build Instructions (Phase 4)

Dark-neon **5-page hospital readmission dashboard** from **one CSV**. Pages 1–4 are clinical; **Page 5 only** contains ML experiment metrics.

**Time estimate:** 60–90 minutes.

---

## A. Dashboard overview

| Page | Tab name | Content |
|------|----------|---------|
| 1 | Hospital Overview | Total patients, readmission rate, avg LOS (+ optional gender summary) |
| 2 | Risk Analysis | Readmission by age, gender, diagnosis |
| 3 | Patient Behavior | Visit frequency, medication patterns |
| 4 | Model Insights | Feature importance, prediction distribution |
| 5 | ML Performance | Champion KPIs, recall bar, experiment table, actual vs predicted |

### Must-have features

- **Filters (pages 1–4):** Age group (`enc_age_band`), Gender (`enc_gender`), Diagnosis (`enc_diag_1`) — left sidebar, synced across pages
- **KPI cards** on pages 1 and 5
- **Drill-down / cross-filter:** click a bar to filter other visuals on the same page

### Reference mockups (build to match)

Open the mockup for your current page **side-by-side** with Power BI Desktop.

| Page | Mockup |
|------|--------|
| 1 | [`assets/mockups/page_01_hospital_overview.png`](assets/mockups/page_01_hospital_overview.png) |
| 2 | [`assets/mockups/page_02_risk_analysis.png`](assets/mockups/page_02_risk_analysis.png) |
| 3 | [`assets/mockups/page_03_patient_behavior.png`](assets/mockups/page_03_patient_behavior.png) |
| 4 | [`assets/mockups/page_04_model_insights.png`](assets/mockups/page_04_model_insights.png) |
| 5 | [`assets/mockups/page_05_ml_performance.png`](assets/mockups/page_05_ml_performance.png) |

Regenerate after data refresh:

```powershell
cd "e:\Amit\Project\Hospital project"
python scripts/build_powerbi_master_csv.py
python scripts/render_powerbi_page_mockups.py
```

### Layout (all pages)

```text
┌──────────┬──────────────────────────────────────────────────┐
│ SIDEBAR  │  KPI ROW (pages 1 & 5) or page title           │
│ Age      ├──────────────────────────┬───────────────────────┤
│ Gender   │  MAIN CHART              │  SECONDARY CHART      │
│ Diagnosis│                          │                       │
├──────────┴──────────────────────────┴───────────────────────┤
│  BOTTOM WIDE CHART / TABLE (pages 2 & 5)                    │
├───────────────────────────────────────────────────────────────┤
│  PAGE TABS: Overview | Risk | Behavior | Model | ML          │
└───────────────────────────────────────────────────────────────┘
```

### Dark neon theme

| Element | Setting |
|---------|---------|
| Page background | `#0B1426` |
| Visual background | `#111827` |
| Border / accent | Cyan `#00D4FF` |
| KPI highlight | Pink `#FF007A` (readmission rate, recall) |
| Bars | Neon blue `#0099FF` |
| Title text | `#E8F4FD` |
| Labels | `#94A3B8` |

### Data file

Import **only:** `data/exports/powerbi_dashboard_master.csv` — no relationships, no custom DAX.

---

## B. One-time setup (~15 min)

### B.1 Install and save

1. Open **Power BI Desktop** → **Blank report**
2. **File → Save As** → `powerbi/readmission_dashboard.pbix`

### B.2 Import CSV

1. **Home → Get data → Text/CSV**
2. Select `data/exports/powerbi_dashboard_master.csv` → **Load**
3. Confirm **one table** in the Data pane (~109k rows)

### B.3 Summarization (critical)

In **Data** view, set **Don't summarize** on text columns: `record_type`, all `enc_*` labels, `chart_category`, `dq_*`, `mtx_*` text, `kpi_*_pct`, `kpi_champion_model`.

On **Card** visuals using broadcast KPI fields, set aggregation to **First** (not Sum).

### B.4 Page canvas

1. Select empty canvas → **Format page**
2. **Page size:** 16:9
3. **Canvas background color:** `#0B1426`, transparency 0%

---

## C. Global shell (~20 min, do once)

### C.1 Create 5 pages

Rename tabs: `Hospital Overview`, `Risk Analysis`, `Patient Behavior`, `Model Insights`, `ML Performance`.

### C.2 Left sidebar slicers (pages 1–4)

On **Page 1**:

1. **Insert → Slicer** → field `enc_age_band` — place left panel, title **Age Band**
2. **Insert → Slicer** → `enc_gender` — title **Gender**
3. **Insert → Slicer** → `enc_diag_1` — title **Diagnosis** (list or dropdown)

Format each slicer: background `#111827`, border cyan `#00D4FF`, white text.

**Sync slicers:**

1. Select all three slicers on Page 1
2. **View → Sync slicers**
3. Check **Risk Analysis**, **Patient Behavior**, **Model Insights** for all three fields
4. Leave **ML Performance** unchecked (uses matrix slicers instead)

### C.3 Bottom page navigation

1. **Insert → Buttons → Navigator**
2. Choose **Page navigator** → horizontal tab style at bottom
3. Format: white bar, active tab teal underline `#2DD4BF`

### C.4 Visual default formatting

For every chart/card/table:

- Background `#111827`, border on `#00D4FF`, 8px rounded corners
- Title on, color `#E8F4FD`, Segoe UI Semibold
- Use **Format painter** to copy across visuals

---

## D. Page-by-page baby steps

Use **Filters on this visual** → `record_type` on each chart (do not filter the whole page to one type unless noted).

---

### D.1 Page 1 — Hospital Overview

**Mockup:** `page_01_hospital_overview.png`

#### KPI cards (3 only — no ML metrics)

| # | Title | Field | Aggregation | Filter |
|---|-------|-------|-------------|--------|
| 1 | Total Patients | `kpi_total_patients` | First | `ENCOUNTER` |
| 2 | 30-Day Readmission Rate | `kpi_readmission_rate_pct` | First | `ENCOUNTER` |
| 3 | Avg Length of Stay | `kpi_avg_los` | First | `ENCOUNTER` |

Place in a row below the page title (top-right area).

#### Optional summary chart

- **Clustered bar** → `chart_category` (axis), `chart_rate_pct` (values)
- Filter: `record_type` = **CHART_GENDER**
- Title: **Readmission Rate by Gender**

#### Do NOT add on this page

- Champion recall / ROC-AUC (those go on Page 5)
- DQ scorecard
- Experiment matrix

---

### D.2 Page 2 — Risk Analysis

**Mockup:** `page_02_risk_analysis.png`

| # | Visual | Fields | record_type filter |
|---|--------|--------|-------------------|
| 1 | Horizontal bar | `chart_category`, `chart_rate_pct` | **CHART_AGE** |
| 2 | Horizontal bar | `chart_category`, `chart_rate_pct` | **CHART_GENDER** |
| 3 | Horizontal bar (wide, bottom) | `chart_category`, `chart_rate_pct` | **CHART_DIAG** |

Titles: *Readmission by Age*, *Readmission by Gender*, *Readmission by Diagnosis (Top 10)*.

**Drill-through target (optional):** add a hidden **Table** visual with `enc_encounter_id`, `enc_age_band`, `enc_gender`, `enc_diag_1`, filter `ENCOUNTER`. Right-click a bar → **Drill through** → this table.

---

### D.3 Page 3 — Patient Behavior

**Mockup:** `page_03_patient_behavior.png`

| # | Visual | Fields | record_type filter |
|---|--------|--------|-------------------|
| 1 | Horizontal bar | `chart_category`, `chart_rate_pct` | **CHART_VISIT** |
| 2 | Horizontal bar | `chart_category`, `chart_rate_pct` | **CHART_MEDICATION** |

Titles: *Visit Frequency*, *Medication Patterns*.

Visit buckets: `0 visits`, `1-2 visits`, `3-5 visits`, `6+ visits`.

---

### D.4 Page 4 — Model Insights (clinical — no ML experiment grid)

**Mockup:** `page_04_model_insights.png`

| # | Visual | Fields | record_type filter |
|---|--------|--------|-------------------|
| 1 | Horizontal bar | `chart_category`, `chart_value` | **CHART_FEATURE** |
| 2 | Column chart | `chart_category`, `chart_count` | **CHART_PRED_BUCKET** |

Titles: *Feature Importance*, *Prediction Distribution*.

**Do NOT use on this page:** `mtx_*`, `ACTUAL_VS_PRED`, experiment table, champion KPI cards.

---

### D.5 Page 5 — ML Performance (ML only)

**Mockup:** `page_05_ml_performance.png`

#### KPI cards

| Title | Field | Filter |
|-------|-------|--------|
| Champion Model | `kpi_champion_model` | `ENCOUNTER` → First |
| Champion Recall | `kpi_champion_recall_pct` | First |
| Champion ROC-AUC | `kpi_champion_roc_auc_pct` | First |

#### Charts and table

| # | Visual | Fields | Filter |
|---|--------|--------|--------|
| 1 | Clustered bar | `mtx_model`, `mtx_recall_pct` | `MATRIX` + `mtx_is_primary_protocol` = 1 |
| 2 | Line chart | X: `avp_idx`, Y: `avp_actual_cum_rate`, `avp_predicted_cum_rate` | `ACTUAL_VS_PRED` |
| 3 | Table | `mtx_model`, `mtx_horizon`, `mtx_split`, `mtx_ensemble`, `mtx_recall_pct`, `mtx_roc_auc_pct`, `mtx_f1_pct` | `MATRIX` |

#### Left sidebar slicers (this page only)

- `mtx_model`, `mtx_horizon`, `mtx_split`, `mtx_ensemble`
- Do **not** sync these with clinical pages

---

## E. Drill-down and cross-filtering

### Cross-filter (default)

Click a bar on Page 2 → other visuals on Page 2 filter to that category (if they share encounter-level data). Pre-aggregated `CHART_*` visuals do not cross-filter each other unless you build encounter-level versions — **expected behavior**.

### Drill down on bars

1. Select bar chart → **Format visual → General → Drill down** → On
2. Add hierarchy if needed (e.g. age band → gender) using encounter-level matrix on `ENCOUNTER` rows

### Synced slicers

Changing **Age / Gender / Diagnosis** on any page 1–4 updates all synced pages — use this as your primary drill path.

---

## F. Refresh workflow

1. Run pipeline Phases 0–4 (or `python scripts/build_powerbi_master_csv.py`)
2. Power BI → **Home → Refresh**
3. Optional: `python scripts/render_powerbi_page_mockups.py` to update reference PNGs

---

## Appendix — record_type reference

| record_type | Rows | Page(s) |
|-------------|-----:|---------|
| ENCOUNTER | 101,766 | Slicers, KPI source (pages 1–4) |
| CHART_GENDER | 3 | 1 (optional), 2 |
| CHART_AGE | 10 | 2 |
| CHART_DIAG | 10 | 2 |
| CHART_VISIT | 4 | 3 |
| CHART_MEDICATION | 7 | 3 |
| CHART_FEATURE | 5 | 4 |
| CHART_PRED_BUCKET | 10 | 4 |
| MATRIX | 168 | 5 |
| ACTUAL_VS_PRED | 7,501 | 5 |
| KPI | 1 | 1 (optional row) |
| DQ | 8 | Not on dashboard (pipeline only) |

---

## Appendix — Troubleshooting

| Symptom | Fix |
|---------|-----|
| KPI shows billions | Use **First**, not Sum |
| Chart blank | Check `record_type` filter on visual |
| Slicer doesn't affect chart | Chart uses pre-agg `CHART_*` rows — use encounter matrix for slicer-driven charts |
| ML charts on wrong page | `MATRIX` / `ACTUAL_VS_PRED` only on Page 5 |
| Feature chart empty | Re-run builder; needs `models/champion_register.json` |

---

## Appendix — Checklist

### Global
- [ ] Single CSV import
- [ ] Page background `#0B1426`
- [ ] Sidebar slicers synced pages 1–4
- [ ] Bottom page navigator (5 tabs)
- [ ] Dark neon visual formatting

### Page 1
- [ ] 3 KPI cards only (patients, readmit %, avg LOS)

### Page 2
- [ ] Age, gender, diagnosis bars

### Page 3
- [ ] Visit frequency + medication bars

### Page 4
- [ ] Feature importance + prediction distribution
- [ ] No ML experiment visuals

### Page 5
- [ ] Champion KPIs + recall bar + line + matrix table
- [ ] Matrix slicers (not synced to clinical pages)

### Save
- [ ] `powerbi/readmission_dashboard.pbix`
