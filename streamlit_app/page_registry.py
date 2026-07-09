"""Single source of truth for Streamlit navigation and in-page headers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PageDef:
    path: str
    title: str
    icon: str
    subtitle: str
    default: bool = False

    @property
    def filename(self) -> str:
        return Path(self.path).name


APP_PAGES: tuple[PageDef, ...] = (
    PageDef(
        "streamlit_app/app_pages/1_Hospital_Overview.py",
        "Hospital Overview",
        "🏥",
        "Certified KPIs from Phase 4 exports.",
        default=True,
    ),
    PageDef(
        "streamlit_app/app_pages/2_Risk_Analysis.py",
        "Risk Analysis",
        "📊",
        "Readmission patterns by age, gender, and diagnosis.",
    ),
    PageDef(
        "streamlit_app/app_pages/3_Patient_Behavior.py",
        "Patient Behavior",
        "👥",
        "Visit frequency and medication utilization patterns.",
    ),
    PageDef(
        "streamlit_app/app_pages/4_Model_Insights.py",
        "Model Insights",
        "🧠",
        "Feature importance and prediction distribution.",
    ),
    PageDef(
        "streamlit_app/app_pages/5_ML_Performance.py",
        "ML Performance",
        "📈",
        "Champion metrics, experiment matrix, and calibration.",
    ),
    PageDef(
        "streamlit_app/app_pages/6_Risk_Prediction.py",
        "Risk Prediction",
        "⚕️",
        "Select an encounter, run the 8-step inference pipeline, and review the clinical assessment.",
    ),
    PageDef(
        "streamlit_app/app_pages/7_Grounded_Chat.py",
        "Grounded Chat",
        "💬",
        "MCP tribunal, scripts, metrics, RAG, and SQLite (role-gated).",
    ),
    PageDef(
        "streamlit_app/app_pages/8_System_Health_Diagnose.py",
        "System Health Diagnose",
        "🩺",
        "Verify prerequisites, runtime services, and ML artifacts before clinical scoring.",
    ),
)


def page_def_for_script(script_path: str | Path) -> PageDef:
    name = Path(script_path).name
    for page in APP_PAGES:
        if page.filename == name:
            return page
    raise KeyError(f"No page definition for {name}")


def page_header_from_script(script_path: str | Path) -> None:
    from streamlit_app.theme import page_header

    page = page_def_for_script(script_path)
    page_header(page.title, page.subtitle, icon=page.icon)
