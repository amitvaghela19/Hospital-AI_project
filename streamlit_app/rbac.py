"""Shared RBAC helpers for Streamlit pages, chat, and dashboards."""

from __future__ import annotations

from typing import Any

import pandas as pd

from streamlit_app.data_loaders import load_rbac
from streamlit_app.rbac_auth import validate_role


ROLE_ORDER = ["viewer", "clinician", "analyst", "admin"]

# Capability map used to make roles visibly different in the UI.
ROLE_CAPABILITIES: dict[str, dict[str, Any]] = {
    "viewer": {
        "label": "Viewer",
        "summary": "Aggregate dashboards only — no scoring, no patient/encounter IDs.",
        "pages": {
            "hospital_overview": True,
            "risk_analysis": True,
            "patient_behavior": True,
            "model_insights": False,
            "ml_performance": False,
            "risk_prediction": False,
            "grounded_chat": True,
            "system_health_diagnose": True,
        },
        "marts": ["mart_readmission"],
        "can_predict": False,
        "can_sql": False,
        "can_fred": False,
        "can_audit": False,
        "can_diagnose_advanced": False,
        "can_switch_llm": False,
        "can_manage_integrations": False,
        "ids": False,  # False | "limited" | True
        "chat_ids": False,
        "chat_high_risk_list": False,
        "chat_encounter_detail": False,
        "dashboard_ids": False,
    },
    "clinician": {
        "label": "Clinician",
        "summary": "Clinical scoring + limited encounter IDs (patient numbers masked).",
        "pages": {
            "hospital_overview": True,
            "risk_analysis": True,
            "patient_behavior": True,
            "model_insights": True,
            "ml_performance": False,
            "risk_prediction": True,
            "grounded_chat": True,
            "system_health_diagnose": True,
        },
        "marts": ["mart_clinical_risk", "mart_readmission"],
        "can_predict": True,
        "can_sql": False,
        "can_fred": True,
        "can_audit": False,
        "can_diagnose_advanced": True,
        "can_switch_llm": True,
        "can_manage_integrations": True,
        "ids": "limited",
        "chat_ids": True,
        "chat_high_risk_list": True,
        "chat_encounter_detail": True,
        "dashboard_ids": "limited",
    },
    "analyst": {
        "label": "Analyst",
        "summary": "Full dashboards, prediction, SQLite chat, and full identifiers.",
        "pages": {
            "hospital_overview": True,
            "risk_analysis": True,
            "patient_behavior": True,
            "model_insights": True,
            "ml_performance": True,
            "risk_prediction": True,
            "grounded_chat": True,
            "system_health_diagnose": True,
        },
        "marts": "all",
        "can_predict": True,
        "can_sql": True,
        "can_fred": True,
        "can_audit": False,
        "can_diagnose_advanced": True,
        "can_switch_llm": True,
        "can_manage_integrations": True,
        "ids": True,
        "chat_ids": True,
        "chat_high_risk_list": True,
        "chat_encounter_detail": True,
        "dashboard_ids": True,
    },
    "admin": {
        "label": "Admin",
        "summary": "Everything analysts can do, plus audit visibility.",
        "pages": {
            "hospital_overview": True,
            "risk_analysis": True,
            "patient_behavior": True,
            "model_insights": True,
            "ml_performance": True,
            "risk_prediction": True,
            "grounded_chat": True,
            "system_health_diagnose": True,
        },
        "marts": "all",
        "can_predict": True,
        "can_sql": True,
        "can_fred": True,
        "can_audit": True,
        "can_diagnose_advanced": True,
        "can_switch_llm": True,
        "can_manage_integrations": True,
        "ids": True,
        "chat_ids": True,
        "chat_high_risk_list": True,
        "chat_encounter_detail": True,
        "dashboard_ids": True,
    },
}

PAGE_DENY_MESSAGES: dict[str, str] = {
    "model_insights": "Model Insights requires Clinician or Analyst access. Unlock in the sidebar.",
    "ml_performance": "ML Performance requires Analyst access. Unlock in the sidebar.",
    "risk_prediction": "Risk Prediction requires Clinician or Analyst access. Unlock in the sidebar.",
    "grounded_chat": "Grounded Chat is unavailable for this role.",
}


def get_role_config(role: str) -> dict[str, Any]:
    role = (role or "viewer").lower()
    if role not in ROLE_CAPABILITIES:
        role = "viewer"
    # Overlay JSON registry if present (predict / ids / audit / marts).
    cfg = dict(ROLE_CAPABILITIES[role])
    raw = load_rbac().get("roles", {}).get(role, {})
    if "predict" in raw:
        cfg["can_predict"] = bool(raw.get("predict"))
    if "ids" in raw:
        cfg["ids"] = raw.get("ids")
        cfg["dashboard_ids"] = raw.get("ids")
        cfg["chat_ids"] = bool(raw.get("ids"))
    if "audit" in raw:
        cfg["can_audit"] = bool(raw.get("audit"))
    if "marts" in raw:
        cfg["marts"] = raw.get("marts")
    # Keep page gates / SQL / FRED from the gold-standard capability map.
    return cfg


def can_access_page(role: str | None, page_key: str) -> bool:
    role = validate_role(role)
    return bool(get_role_config(role).get("pages", {}).get(page_key, False))


def can_predict(role: str | None = None) -> bool:
    role = validate_role(role)
    return bool(get_role_config(role).get("can_predict"))


def can_sql(role: str | None = None) -> bool:
    role = validate_role(role)
    return bool(get_role_config(role).get("can_sql"))


def can_fred(role: str | None = None) -> bool:
    role = validate_role(role)
    return bool(get_role_config(role).get("can_fred"))


def can_audit(role: str | None = None) -> bool:
    role = validate_role(role)
    return bool(get_role_config(role).get("can_audit"))


def can_diagnose_advanced(role: str | None = None) -> bool:
    role = validate_role(role)
    return bool(get_role_config(role).get("can_diagnose_advanced"))


def can_switch_llm(role: str | None = None) -> bool:
    role = validate_role(role)
    return bool(get_role_config(role).get("can_switch_llm"))


def can_manage_integrations(role: str | None = None) -> bool:
    role = validate_role(role)
    return bool(get_role_config(role).get("can_manage_integrations"))


def ids_policy(role: str | None = None) -> tuple[bool, bool]:
    """
    Returns (can_access_ids, mask_patient_nbr).
    - viewer: (False, False)
    - clinician: (True, True)  # encounter_id only
    - analyst/admin: (True, False)
    """
    role = validate_role(role)
    ids = get_role_config(role).get("ids", False)
    if ids is False or ids is None:
        return False, False
    if ids == "limited":
        return True, True
    return True, False


def require_page_access(role: str | None, page_key: str) -> bool:
    """
    Streamlit gate: returns True if allowed, otherwise shows a deny panel and returns False.
    """
    import streamlit as st

    role = validate_role(role)
    if can_access_page(role, page_key):
        return True

    cfg = get_role_config(role)
    st.error(PAGE_DENY_MESSAGES.get(page_key, "Your role cannot access this page."))
    st.info(
        f"**Current access:** {cfg.get('label', role)} (locked)\n\n"
        f"{cfg.get('summary', '')}\n\n"
        "Use **Unlock Clinical or Analyst mode** in the sidebar and enter the correct password."
    )
    with st.expander("What each access level can do"):
        for r in ("viewer", "clinician", "analyst"):
            c = ROLE_CAPABILITIES[r]
            st.markdown(f"**{c['label']}** — {c['summary']}")
    return False


def enforce_mart_access(role: str | None, mart_name: str) -> bool:
    role = validate_role(role)
    marts = get_role_config(role).get("marts", [])
    if marts == "all":
        return True
    if isinstance(marts, list):
        # Viewer/clinician may still need mart_readmission for aggregate dashboards.
        if mart_name in marts:
            return True
        if mart_name == "mart_readmission" and can_access_page(role, "hospital_overview"):
            return True
    return False


_ID_COLS = (
    "encounter_id",
    "patient_nbr",
    "enc_encounter_id",
    "enc_patient_nbr",
)


def mask_dataframe_ids(df: pd.DataFrame, role: str | None = None) -> pd.DataFrame:
    """Drop/mask identifier columns according to role policy."""
    role = validate_role(role)
    if df is None or getattr(df, "empty", True):
        return df
    can_ids, mask_patient = ids_policy(role)
    out = df.copy()
    if not can_ids:
        drop_cols = [c for c in _ID_COLS if c in out.columns]
        if drop_cols:
            out = out.drop(columns=drop_cols)
        return out
    if mask_patient:
        for c in ("patient_nbr", "enc_patient_nbr"):
            if c in out.columns:
                out = out.drop(columns=[c])
    return out


def mask_record_ids(record: dict | None, role: str | None = None) -> dict | None:
    if not isinstance(record, dict):
        return record
    role = validate_role(role)
    can_ids, mask_patient = ids_policy(role)
    out = dict(record)
    if not can_ids:
        for c in _ID_COLS:
            out.pop(c, None)
        return out
    if mask_patient:
        out.pop("patient_nbr", None)
        out.pop("enc_patient_nbr", None)
    return out


def capability_rows(role: str | None = None) -> list[tuple[str, str]]:
    """Human-readable permission rows for the sidebar."""
    role = validate_role(role)
    cfg = get_role_config(role)
    pages = cfg.get("pages", {})
    yes = "allowed"
    no = "blocked"
    lim = "limited (encounter_id only)"
    ids = cfg.get("ids", False)
    if ids is False:
        ids_label = no
    elif ids == "limited":
        ids_label = lim
    else:
        ids_label = yes
    return [
        ("Risk Prediction", yes if pages.get("risk_prediction") else no),
        ("Model Insights", yes if pages.get("model_insights") else no),
        ("ML Performance", yes if pages.get("ml_performance") else no),
        ("Aggregate dashboards", yes if pages.get("hospital_overview") else no),
        ("Encounter / patient IDs", ids_label),
        ("SQL in chat", yes if cfg.get("can_sql") else no),
        ("FRED macro chat", yes if cfg.get("can_fred") else no),
        ("Audit log access", yes if cfg.get("can_audit") else no),
        ("Advanced system diagnose", yes if cfg.get("can_diagnose_advanced") else no),
        ("LLM model switching", yes if cfg.get("can_switch_llm") else no),
        ("n8n / CrewAI / API hooks", yes if cfg.get("can_manage_integrations") else no),
    ]
