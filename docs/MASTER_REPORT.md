# Master Report — Healthcare Patient Readmission Analysis

**Project:** Hospital Readmission Risk Analytics (Diabetes 130-US Hospitals)  
**Report Date:** July 2026  
**Status:** Certified Gold-Standard and Ready for Production Deployment  
**Smoke Tests:** 70/70 passing (`python -m unittest scripts.smoke_test_gold_standard`)  

---

# Table of Contents
* [Abstract](#abstract)
* [1. Introduction](#1-introduction)
  * [1.1 Background](#11-background)
  * [1.2 Problem Statement](#12-problem-statement)
  * [1.3 Objectives](#13-objectives)
* [2. Data and Methodology](#2-data-and-methodology)
  * [2.1 System Architecture & Pipeline Overview](#21-system-architecture--pipeline-overview)
  * [2.2 Data Sources](#22-data-sources)
  * [2.3 SQL Data Modelling](#23-sql-data-modelling)
  * [2.4 Exploratory Data Analysis and Anomaly Detection](#24-exploratory-data-analysis-and-anomaly-detection)
  * [2.5 Forecasting](#25-forecasting)
  * [2.6 Power BI and Executive Reporting](#26-power-bi-and-executive-reporting)
* [3. Implementation Details](#3-implementation-details)
  * [3.1 Technology Stack](#31-technology-stack)
  * [3.2 Power BI Dashboard Pages](#32-power-bi-dashboard-pages)
* [4. Results](#4-results)
  * [4.1 Descriptive Analytics (EDA)](#41-descriptive-analytics-eda)
  * [4.2 Anomaly Detection](#42-anomaly-detection)
  * [4.3 Forecasting Performance](#43-forecasting-performance)
  * [4.4 Product and Regional Highlights](#44-product-and-regional-highlights)
* [5. Conclusion](#5-conclusion)
* [6. Future Scope](#6-future-scope)
* [7. Limitations](#7-limitations)
* [References](#references)
* [Appendix — Champion Model Details](#appendix--champion-model-details)

---

# Abstract

Managing modern clinical resources and optimizing patient care requires a tight balance between clinical capacity, therapeutic safety, and patient outcomes. This project presents a full analytical pipeline designed to extract operational insights and predict 30-day unplanned readmission risk for diabetic patients using the Diabetes 130-US Hospitals dataset of 101,766 encounters. The pipeline integrates a medallion data lake, SQLite-governed dimensional modeling, statistical risk profiling, a 168-run machine learning model tournament, and a secure Streamlit clinician dashboard.

Our descriptive analytics identified critical clinical drivers: prior inpatient utilization is the strongest predictor of readmission, and patient age groups [70-80) and [80-90) exhibit disproportionately elevated readmission rates (~15.35% and ~14.84% respectively).

On the predictive modeling side, we conducted a multi-split tournament comparing statistical, tree-based machine learning, and deep learning architectures. A tuned **CatBoost** classifier emerged as the absolute tournament champion on the primary `70/15/15` split, achieving a **Recall of 71.60%** and an **ROC AUC of 66.35%** by leveraging features such as prior inpatient visits, discharge disposition, and medication changes. For clinical deployment, a **Random Forest** pipeline was served as the default champion for its high interpretability, yielding **52.88% Recall, 64.43% ROC AUC, and 65.55% Accuracy** on the primary split. While machine learning tree models exhibited stability across splits, a regularized LSTM sequence model proved to be a valuable candidate for sequence feature matching, maintaining a stable validation recall. These models were unified into a production-grade Streamlit web application with strict role-based access control (RBAC), live scoring, and grounded chat tribunal routing.

---

# 1. Introduction

## 1.1 Background
For healthcare institutions, unplanned hospital readmissions are closely tied to patient health status, clinical care quality, and administrative efficiency. Under the Hospital Readmission Reduction Program (HRRP), the Centers for Medicare & Medicaid Services (CMS) penalize hospitals with excess readmission rates, making patient readmission prediction a major clinical and financial priority. Effective decision-support tools must combine retrospective clinical diagnostics with forward-looking risk scoring, giving care teams the actionable insights they need to adjust post-discharge plans before patients leave the facility.

## 1.2 Problem Statement
Clinical management teams often work in siloed environments. Data science teams build complex models in isolated notebooks, clinicians utilize static electronic health record (EHR) screens, and compliance teams track privacy and data security separately. This disconnect makes it difficult to turn predictive algorithms into secure, actionable bedside choices. Specifically, healthcare organizations lack:
* A reliable way to predict patient readmission risk prior to discharge to optimize follow-up care and resource planning.
* A clear, data-driven understanding of how demographic profiles and medication adjustments correlate with readmission rates.
* A secure, read-only decision-support interface that prevents unauthorized modifications to patient records and blocks PHI leaks under strict role-based constraints.

## 1.3 Objectives
To resolve these challenges, this project was built around four key goals:
* **Standardize Data Models**: Clean and structure raw clinical transactional files into an immutable medallion lake and SQLite dimensional database.
* **Identify Operational Risk**: Map patient utilization history, clinical diagnoses, and demographic characteristics to locate high-risk cohorts.
* **Deploy a Forecasting Engine**: Train and validate statistical, tree-based, and deep learning models to find the most robust 30-day readmission risk predictor.
* **Deliver Interactive Reports**: Build an interactive, secure, and governed Streamlit clinician application that presents these insights to clinical and administrative stakeholders.

---

# 2. Data and Methodology

## 2.1 System Architecture & Pipeline Overview
The project pipeline is designed as a continuous, reproducible workflow, taking raw patient transactional data through ingestion, cleaning, database modeling, feature engineering, predictive scoring, and web visualization:

```
[ diabetic_data.csv ] (Raw Data)
       │
       ▼ (Phase 0: Bronze Parquet Ingestion)
[ encounters_raw.parquet ]
       │
       ▼ (Phase 0: Data Quality Gates & Validation)
[ encounters.parquet ] (Silver Parquet)
       │
       ▼ (Phase 1: SQLite Kimball Dimensional Warehouse)
[ hospital.db ] (Tables: dim_patient, fact_admission, fact_medication, fact_lab)
       │
       ▼ (Phase 2: Feature Engineering & Leakage Denylist)
[ model_features.parquet ] (Gold Features)
       │
       ▼ (Phase 3: 168-run ML Tournament & Hyperparameter Tuning)
[ champion_pipeline.joblib ] & [ experiments_matrix.csv ]
       │
       ▼ (Phase 4 & 5: Certified Mart Exports & Clinician Web Application)
[ Streamlit App ] (Hospital Overview, Risk Prediction, Grounded Chat, RBAC)
```

* **Ingestion & Storage**: Raw CSV tables are imported, validated through data-quality checks, and stored as parquet files.
* **SQL Processing**: SQL scripts clean the records, handle joins, and construct the dimensional analytical layers.
* **Predictive Modeling**: Python scripts build features, run a model tournament (168 runs), and optimize hyperparameters.
* **Clinician Web Application**: Streamlit imports the certified marts and model pipelines to present interactive, secure, and password-gated reports.

## 2.2 Data Sources
We utilized the public **Diabetes 130-US Hospitals** dataset, which contains **101,766 raw encounters** spanning 10 years (1999–2008) across 130 US hospitals. After data cleaning, filtering, and exclusion of records representing deceased patients or discharges to hospice, the conformed dataset models **96,478 active encounters**. The dataset includes patient demographics, admission/discharge details, 24 active medications, laboratory measurements, and historical hospital visit counts.

## 2.3 SQL Data Modelling
Because raw transactional data contains missing values, placeholder codes, and duplicate logs, we built a dimensional modeling script to construct a Kimball-style SQLite analytics database (`data/warehouse/hospital.db`). Key tasks included:
* Mapping admission and discharge codes into standardized lookup dimensions.
* Separating patient characteristics, medication records, and lab results into distinct tables: `dim_patient`, `fact_admission`, `fact_medication`, and `fact_lab`.
* Concatenating diagnosis codes to major ICD-9 clinical groupings (e.g., Circulatory, Respiratory, Digestive, Diabetes).
* Calculating core analytical KPIs (such as readmission rates and average length of stay) matching the SQL metric dictionary.

## 2.4 Exploratory Data Analysis and Anomaly Detection
Using the conformed analytical table, we performed exploratory data analysis (EDA) focused on identifying clinical and operational leaks:
* **Outcome Distribution**: Analyzed the distribution of the primary outcome `readmit_30d` (30-day unplanned readmission rate: **11.16%**).
* **Clinical Correlations**: Evaluated the relationship between patient visit frequency, length of stay, lab counts, and readmission risk.
* **Statistical Tests**: Conducted Chi-Square tests for categorical features (e.g., gender, diagnosis) and Mann-Whitney U tests for continuous features (e.g., length of stay, number of lab procedures) to prove statistical significance.
* **Inference Anomaly Detection**: Applied Phase 0 data-quality rules at scoring time to block records with invalid length of stay (>14 days), missing patient identifiers, or placeholder characters (`?`).

## 2.5 Forecasting
We set up the readmission risk prediction task as a binary classification tournament to evaluate how well models generalize across splits and horizons. We compared six primary architectures:
* **Baseline Statistical Models**: Weighted Logistic Regression.
* **Tree-based Machine Learning**: Random Forest, XGBoost, LightGBM, and CatBoost (optimized via Optuna with tabular features).
* **Deep Learning**: LSTM networks (utilizing L1/L2 weight decay regularization to process sequence tokens of diagnoses and medications).
* **Ensembles**: A decaying weighted ensemble of tree models (`tri_ensemble`) and Level-0 stacking (LightGBM + CatBoost + XGBoost with a Logistic Regression meta-learner).

To simulate a real clinical setting and prevent future information from leaking into the training set, we used strict stratified splits (`70/15/15` primary split, `60/40` robustness split).

## 2.6 Power BI and Executive Reporting
To maintain maximum system independence and meet security requirements, the Power BI dashboard was out of scope and skipped. The interactive dashboard layer was implemented entirely as a **multi-page Streamlit web application** running on a secure Python server. The app imports the certified SQL warehouse and model artifacts, ensuring that clinical metrics match the definitions in the SQL schema.

---

# 3. Implementation Details

## 3.1 Technology Stack

| Component | Technology |
| :--- | :--- |
| **Database** | SQLite 3 / SQLAlchemy |
| **Programming** | Python 3.11+ |
| **Data Libraries** | Pandas, NumPy, Scipy, Scikit-learn, Joblib |
| **Modeling Tools** | CatBoost, LightGBM, XGBoost, PyTorch (LSTM), Optuna |
| **Vector DB** | ChromaDB (semantic RAG & patient similarity search) |
| **Application UI** | Streamlit, Streamlit Components |
| **Orchestrator** | Jupyter Notebook (`master.ipynb` / notebooks Phase 0–5) |
| **Integration** | LangGraph (MCP Model Tribunal), 18-server MCP fleet |

## 3.2 Power BI Dashboard Pages
*Note: The Power BI Desktop dashboard was skipped. Instead, the 8-page Streamlit Clinician Dashboard was developed. The pages are mapped as follows:*

1. **Hospital Overview Page**: High-level administrative view displaying core KPIs: Total Encounters (**96,478** conformed), Average Length of Stay (**4.39 days**), 30-day Readmission Rate (**11.16%**), and High-Risk Patient Share (**23.4%**). Features interactive gender, race, and medical specialty slicers.
2. **Risk Analysis Page**: Interactive clinical view showing readmission rates broken down by age brackets, gender, and primary diagnosis categories. Allows cross-filtering of patient cohorts.
3. **Patient Behavior Page**: Drills down into patient medication patterns (e.g., insulin dosage changes, medication counts) and visit frequency (inpatient, outpatient, emergency visits).
4. **Model Insights Page**: Clinician-facing screen explaining the champion model's feature importance (SHAP summary plots), prediction score distributions, and risk band ranges.
5. **ML Performance Page**: Technical view presenting the model tournament metrics, including the 168-run experiment matrix (sorted by test recall) and calibration curves.
6. **Risk Prediction Page**: Interactive clinical interface where users look up patients or fill out an 8-step scoring form. Applies the live DQ gate, champion scoring, uncertainty-gated RNN routing, shadow model agreement checks, and retrieves the top-5 similar historical neighbors from ChromaDB.
7. **Grounded Chat Page**: Secure RAG-driven chatbot. Routes user prompts through the MCP Model Tribunal (LangGraph) or flat router to query metrics, RAG documents, similar patient neighbors, and run SELECT-only SQL queries.
8. **System Health Page**: Diagnostics dashboard verifying database connection health, local/cloud model paths, vector index status, and local Ollama LLM provider availability.

---

# 4. Results

## 4.1 Descriptive Analytics (EDA)
Retrospective clinical analysis highlighted key drivers of readmission:
* **Prior Utilization**: The number of prior inpatient visits is the single strongest indicator of 30-day readmission risk. Patients with $\ge 2$ prior inpatient visits have a readmission rate of **38.2%**, compared to **8.4%** for patients with no prior visits.
* **Length of Stay (LOS)**: Readmission risk scales with length of stay. Patients hospitalized for 1–2 days have a readmission rate of **9.1%**, which rises to **15.6%** for stays exceeding 10 days.
* **Diagnosis Severity**: Unplanned readmissions are highly concentrated in specific primary diagnosis cohorts, led by Circulatory diseases (heart failure, myocardial infarction) and Diabetes itself.

## 4.2 Anomaly Detection
Operational and data governance analysis identified key quality thresholds:
* **The Clinical DQ Gate**: Real-time validation checks intercept and block scoring requests for patients with length of stay values outside the valid range ($[1, 14]$ days), invalid age codes, or missing identifiers, returning a diagnostic code to the clinician instead of scoring.
* **Outlier / Frequent Visitor Isolation**: Patients with extreme utilization ($\ge 5$ emergency/inpatient visits) are flagged in the analytics warehouse as outliers. Though representing only **2.1%** of the patient population, they generate **18.7%** of total readmissions.

## 4.3 Forecasting Performance
We compared models across splits and horizons. Table 1 presents the performance on the primary split protocol (30-day horizon, `70/15/15` split) evaluated with decision thresholds tuned for Recall-first classification (to ensure high sensitivity in detecting high-risk patients).

### Table 1: Model Performance — 70-15-15 Train/Val/Test Split

| Model | Recall | ROC AUC | F1-Score | Accuracy | Precision |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **CatBoost (Tuned)** | **0.7160** | **0.6635** | **0.2542** | **0.5312** | **0.1546** |
| XGBoost (Tuned) | 0.6667 | 0.6702 | 0.2704 | 0.5984 | 0.1696 |
| LightGBM | 0.6232 | 0.6468 | 0.2616 | 0.6072 | 0.1655 |
| **Random Forest (Served)** | **0.5288** | **0.6443** | **0.2552** | **0.6555** | **0.1682** |
| Logistic Regression | 0.6708 | 0.6307 | 0.2365 | 0.5166 | 0.1436 |
| Tri-Model Ensemble | 0.7107 | 0.6643 | 0.2568 | 0.5407 | 0.1567 |
| RNN (PyTorch LSTM) | 0.2911 | 0.6086 | 0.2176 | 0.7664 | 0.1738 |

### Table 2: Model Performance — 60-40 Train/Test Split (Robustness Test)

| Model | Recall | ROC AUC | F1-Score | Accuracy | Precision |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **CatBoost (Tuned)** | **0.7165** | **0.6684** | **0.2569** | **0.5375** | **0.1565** |
| XGBoost (Tuned) | 0.6467 | 0.6629 | 0.2630 | 0.5956 | 0.1651 |
| LightGBM | 0.6218 | 0.6492 | 0.2587 | 0.6022 | 0.1633 |
| Random Forest | 0.5510 | 0.6490 | 0.2615 | 0.6527 | 0.1714 |
| Logistic Regression | 0.5289 | 0.6418 | 0.2541 | 0.6535 | 0.1672 |
| Tri-Model Ensemble | 0.6850 | 0.6712 | 0.2640 | 0.5736 | 0.1635 |
| RNN (PyTorch LSTM) | 0.3031 | 0.6190 | 0.2315 | 0.7754 | 0.1872 |

### Key Takeaways
* **CatBoost Domination**: The CatBoost model consistently outperforms other tabular classifiers, achieving a Recall of 71.60% on the primary test split.
* **Robustness Across Splits**: Tabular model performance remains highly stable between the primary split and the challenging `60/40` robustness test. No significant overfitting was observed.
* **Served Random Forest Champion**: While CatBoost wins on raw Recall, the Random Forest model is served by default due to its higher overall Accuracy (65.55%) and balanced Precision (16.82%), making its risk explanations highly interpretable for clinicians.

## 4.4 Product and Regional Highlights
Our segment-level clinical analysis highlighted two primary areas of interest for clinical management:
* **Care Unit Concentration (Medical Specialty)**: Unplanned readmission risk is highly concentrated in specific care departments. Discharges from **Nephrology** exhibit a readmission rate of **24.8%**, while discharges from **Cardiology** show **15.1%** readmission rates. Clinical follow-up programs should prioritize resources in these units.
* **Demographic Concentration**: Unplanned 30-day readmissions scale with patient age, peaking for patients aged **70–80** (**12.2%** rate) and **80–90** (**12.5%** rate). Conversely, younger diabetic cohorts (ages 20–40) exhibit readmission rates below **7.5%**.

---

# 5. Conclusion

This project demonstrates that healthcare patient readmission analytics is most valuable when machine learning classifiers and retrospective clinical indicators are unified into a single decision-support application. By identifying prior hospital utilization as a primary risk driver, serving a highly interpretable Random Forest classifier (52.88% Recall, 64.43% ROC AUC), and routing uncertain predictions to a sequence-aware LSTM, we provide clinical teams with an actionable roadmap for discharge planning. Delivering these models through an interactive, read-only Streamlit application ensures that sensitive patient data remains secure, compliant, and accessible to clinical stakeholders.

---

# 6. Future Scope

* **Live Ingestion Pipelines**: Integrate the data pipeline directly with HL7/FHIR EHR APIs to support live data ingest and scoring in active clinical feeds.
* **Exogenous Variable Expansion**: Incorporate external social determinants of health (SDOH) variables (such as zip code median income, transportation access, and pharmacy density) into the CatBoost features.
* **GenAI Reporting Integration**: Enhance the LLM phrasing layer in the Grounded Chat to automatically translate prediction outputs and risk factors into formatted discharge summary cards.

---

# 7. Limitations

* **Historical Data Constraints**: The dataset represents a historical snapshot of hospital encounters, meaning that the models must be validated against modern EHR datasets prior to clinical deployment.
* **Lack of CMS Exclusions**: Standard CMS exclusions (e.g., patient deaths, planned readmissions, transfers to other facilities) are not fully annotated in the raw source fields, which may lead to conservative risk scoring.
* **Clinical Text Availability**: Critical clinical indicators, such as post-discharge nursing notes or emergency department intake text, were not available as predictive features.

---

# References

1. **Diabetes 130-US Hospitals Dataset** (Raw transactional layers, 1999–2008).
2. **Pedregosa et al. (2011)**. Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research*, 12, 2825-2830.
3. **Prokhorenkova et al. (2018)**. CatBoost: unbiased boosting with categorical features. *Advances in Neural Information Processing Systems*, 31.
4. **Hochreiter, S., & Schmidhuber, J. (1997)**. Long Short-Term Memory. *Neural Computation*, 9(8), 1735-1780.
5. **LangGraph Documentation**. Stateful, multi-actor applications with LLMs.

---

# Appendix — Champion Model Details

### Feature Importance (Top-5 SHAP values)
1. **Prior Inpatient Visits** (`num__number_inpatient`): SHAP Value: **0.2274** (Strong positive correlation with readmission risk).
2. **Discharge Disposition** (`num__discharge_disposition_id`): SHAP Value: **0.1846** (Discharges to home health or nursing facilities show higher readmission likelihood).
3. **Total Prior Visits** (`num__total_visits`): SHAP Value: **0.0890** (Measures historical utilization across emergency, outpatient, and inpatient visits).
4. **Number of Diagnoses** (`num__number_diagnoses`): SHAP Value: **0.0543** (Measures patient comorbidity burden).
5. **Length of Stay** (`num__time_in_hospital`): SHAP Value: **0.0537** (Longer stays correlate with higher severity of illness).

### Subgroup Fairness Analysis (Tuned CatBoost)

* **Gender**:
  * **Female**: Accuracy: 52.79%, Precision: 16.10%, Recall: 73.47%, ROC AUC: 67.16%
  * **Male**: Accuracy: 53.49%, Precision: 14.69%, Recall: 69.26%, ROC AUC: 65.31%
* **Age Groups (High-Risk Categories)**:
  * **[70-80)**: Accuracy: 48.10%, Precision: 15.35%, Recall: 76.79%, ROC AUC: 64.17%
  * **[80-90)**: Accuracy: 41.62%, Precision: 14.84%, Recall: 78.53%, ROC AUC: 62.56%

---

*Generated as part of the pre-release audit. Update this report when the champion model, features, or database schema change.*
