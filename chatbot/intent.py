from __future__ import annotations

import re

_METRIC_HINTS = (
    "rate",
    "average",
    "avg ",
    "avg.",
    "how many",
    "total patient",
    "total encounter",
    "count",
    "percent",
    "%",
    "length of stay",
    "los",
    "kpi",
)

_PROJECT_TERMS = (
    "readmit",
    "hospital",
    "patient",
    "encounter",
    "model",
    "champion",
    "power bi",
    "powerbi",
    "pipeline",
    "notebook",
    "streamlit",
    "dashboard",
    "risk",
    "dq",
    "data quality",
    "mart",
    "phase",
    "los",
    "diabetes",
    "fairness",
    "bias",
    "shap",
    "experiment",
    "ollama",
    "chroma",
    "mcp",
    "tribunal",
    "shadow",
    "similar",
    "fred",
    "sql",
    "warehouse",
    "ingest",
    "feature",
)

_OFF_TOPIC_MARKERS = (
    # Intentionally narrow: off-topic refusals should not block harmless general Q&A.
    # Clinical diagnosis/prescribing remains blocked by hard guards in routing/tribunal.
)


_GENDER_HINTS = ("male", "female", "gender", "woman", "women", "man", "men")
_RACE_HINTS = ("race", "ethnic")
_AGE_HINTS = ("age band", "by age", "[10", "[20", "[30", "[40", "[50", "[60", "[70", "[80")


def wants_dimensional_metric(message: str) -> bool:
    m = message.lower()
    has_dim = any(h in m for h in _GENDER_HINTS + _RACE_HINTS + _AGE_HINTS)
    has_metric = wants_metric(message)
    return has_dim and has_metric


def wants_metric(message: str) -> bool:
    m = message.lower()
    return any(h in m for h in _METRIC_HINTS)


def has_project_context(message: str) -> bool:
    m = message.lower()
    return any(t in m for t in _PROJECT_TERMS)


def is_off_topic(message: str) -> bool:
    m = message.lower().strip()
    return any(marker in m for marker in _OFF_TOPIC_MARKERS)


def off_topic_reply() -> str:
    return (
        "I can only help with this hospital readmission analytics project — data, models, "
        "dashboards, pipeline, and risk scoring. Try: \"What is the 30-day readmission rate?\" "
        "or \"How do I run the pipeline?\""
    )


_PATIENT_NBR_PATTERNS = (
    re.compile(
        r"\bpatient(?:\s*(?:id|nbr|number|#))?\s*[:=]?\s*(\d+)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:check|find|lookup|look\s+up|is|does|verify|confirm|search)\b"
        r".{0,40}\bpatient\b.{0,40}\b(\d+)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bpatient\b.{0,40}\b(?:available|exists|in\s+(?:the\s+)?(?:dataset|data|system|records?))\b",
        re.IGNORECASE | re.DOTALL,
    ),
)

_LOOKUP_VERBS = re.compile(
    r"\b(check|find|lookup|look\s+up|is|does|verify|confirm|search|available|exists)\b",
    re.IGNORECASE,
)


def extract_patient_nbr(message: str) -> str | None:
    """Extract patient_nbr from a lookup-style message (exact string, no substring match)."""
    if not message or not message.strip():
        return None
    for pat in _PATIENT_NBR_PATTERNS[:2]:
        m = pat.search(message)
        if m:
            return m.group(1).strip()
    return None


def is_patient_lookup_request(message: str) -> bool:
    """True when the user is asking to find or verify a patient in certified data."""
    if not message or not message.strip():
        return False
    if extract_patient_nbr(message):
        return True
    lowered = message.lower()
    if "patient" not in lowered:
        return False
    if _LOOKUP_VERBS.search(message) and re.search(
        r"\b(available|exists|in\s+(?:the\s+)?(?:dataset|data|system|records?)|on\s+file)\b",
        lowered,
    ):
        return True
    if _LOOKUP_VERBS.search(message) and re.search(
        r"\bpatient(?:\s*(?:id|nbr|number))?\b",
        lowered,
    ):
        return True
    return False


def format_rag_answer(message: str, docs: list[str], ids: list[str]) -> str | None:
    if is_patient_lookup_request(message):
        return None
    if not docs:
        return None
    msg_words = {w for w in message.lower().split() if len(w) > 2}
    best_i, best_score = 0, -1
    for i, doc in enumerate(docs):
        doc_l = doc.lower()
        score = sum(1 for w in msg_words if w in doc_l)
        if score > best_score:
            best_score, best_i = score, i
    if best_score == 0 and not has_project_context(message):
        return None
    if ids[best_i] == "metric_readmit" and "rate" in message.lower():
        return None
    if ids[best_i] == "feature_dictionary" and _LOOKUP_VERBS.search(message):
        return None
    return docs[best_i].strip()
