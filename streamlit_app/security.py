"""Read-only data policy — applies to Viewer, Clinician, and Analyst modes."""

from __future__ import annotations

import re

_MUTATION_VERBS = re.compile(
    r"\b("
    r"delete|remove|erase|drop|truncate|wipe|clear|purge|destroy|"
    r"update|insert|alter|modify|edit|change|replace|overwrite|"
    r"add|create|register|append|"
    r"falsif\w*|forge|tamper|fabricat\w*|manipulat\w*|"
    r"add\s+column|remove\s+column|rewrite|corrupt|backdate"
    r")\b",
    re.IGNORECASE,
)

_RECORD_TARGETS = re.compile(
    r"\b("
    r"patient\s*(?:id|nbr|number|record|history|data|file|chart|\d+)|"
    r"encounter\s*(?:id|record|history|data|\d+)|"
    r"medical\s+record|health\s+record|clinical\s+record|"
    r"readmission\s+history|diagnosis\s+history|"
    r"mart_|dataset|database|warehouse|csv|export|table|row|record"
    r")\b",
    re.IGNORECASE,
)

_SQL_WRITE = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|create|replace|truncate|"
    r"attach|detach|grant|revoke|merge|upsert"
    r")\b",
    re.IGNORECASE,
)


def refuse_data_mutation(role: str | None = None) -> str:
    """Standard refusal — same policy for Viewer, Clinician, and Analyst."""
    return (
        "**No — for security reasons this cannot be done.** "
        "This platform is **read-only** in all modes (Viewer, Clinician, and Analyst). "
        "I cannot add, update, edit, or delete patient records, encounters, or certified data."
    )


def is_data_mutation_request(message: str) -> bool:
    """Detect requests to modify, delete, or falsify records or datasets."""
    if not message or not message.strip():
        return False
    text = message.strip()
    if _SQL_WRITE.search(text) and re.search(r"\b(from|into|table|set|values)\b", text, re.I):
        return True
    if _MUTATION_VERBS.search(text) and _RECORD_TARGETS.search(text):
        return True
    if re.search(
        r"\b(add|create|register|insert)\b.*\b(new\s+)?(patient|encounter|record)\b",
        text,
        re.I,
    ):
        return True
    if re.search(
        r"\b(delete|remove|edit|change|update|modify|falsif\w*|forge|tamper)\b"
        r".*\b(all|every|any)\b.*\b(patient|encounter|record)",
        text,
        re.I,
    ):
        return True
    if re.search(r"\b(make|mark|set)\b.*\b(patient|encounter).*\b(as|to)\b", text, re.I):
        return True
    return False
