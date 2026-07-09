"""Structured RBAC refusal messages — no LLM rephrasing."""

from __future__ import annotations


def refuse_high_risk_list(role: str) -> str:
    return (
        f"Your current role ({role}) cannot list high-risk encounters with identifiers. "
        "You can still ask aggregate certified questions, for example:\n"
        "- What is the 30-day readmission rate?\n"
        "- How many patients readmitted are male?\n"
        "- Readmission rate by gender\n"
        "Unlock **Clinician** or **Analyst** in the sidebar to access encounter-level lists."
    )


def refuse_encounter_detail(role: str) -> str:
    return (
        f"Your current role ({role}) cannot look up individual patient or encounter details by ID. "
        "Try certified aggregates instead, for example:\n"
        "- What is the 30-day readmission rate?\n"
        "- How many readmissions by gender?\n"
        "Unlock **Clinician** or **Analyst** in the sidebar for patient and encounter lookup."
    )


def refuse_sql(role: str) -> str:
    return (
        f"Your current role ({role}) cannot run SQL against the warehouse. "
        "Ask certified metrics in plain language, for example:\n"
        "- What is the average length of stay?\n"
        "- How many male patients were readmitted?\n"
        "Unlock **Analyst** in the sidebar for SQL chat queries."
    )


def refuse_fred(role: str) -> str:
    return (
        f"Your current role ({role}) cannot access macro (FRED) economic data. "
        "Ask hospital readmission metrics instead, or unlock **Clinician** or **Analyst**."
    )


def refuse_no_ids(role: str) -> str:
    return (
        f"Your current role ({role}) cannot access patient or encounter identifiers. "
        "Aggregate certified metrics are still available."
    )


def refuse_data_mutation(role: str) -> str:
    from streamlit_app.security import refuse_data_mutation as _msg

    return _msg(role)
