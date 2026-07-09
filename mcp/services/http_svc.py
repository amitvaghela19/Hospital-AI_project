from __future__ import annotations

import json
import os

import requests

from mcp.ollama_config import get_ollama_url


# Gold-standard model names must match `ollama list` output exactly (includes tags like `:latest`).
# Runtime overrides from System Health Diagnose are applied via streamlit_app.runtime_config.
from streamlit_app.runtime_config import get_ollama_fallback, get_ollama_primary


def _primary_model() -> str:
    return get_ollama_primary()


def _fallback_model() -> str:
    return get_ollama_fallback()


def _candidate_models(model: str) -> list[str]:
    model = (model or "").strip()
    if not model:
        return []
    if ":" in model:
        return [model]
    # Try the explicitly provided name, then the common `:latest` tag.
    return [model, f"{model}:latest"]


def ollama_health() -> dict:
    base = get_ollama_url()
    try:
        r = requests.get(f"{base}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m.get("name") for m in r.json().get("models", [])]
            return {"status": "ok", "models": models, "url": base}
        return {"status": "error", "code": r.status_code, "url": base}
    except Exception as e:
        return {"status": "unreachable", "error": str(e), "url": base}


def ollama_generate(
    prompt: str,
    model: str | None = None,
    timeout_s: int = 60,
) -> tuple[str | None, str | None]:
    """Ollama-native generate (used when provider mode is Ollama)."""
    base_models = [model] if model else [_primary_model(), _fallback_model()]
    models: list[str] = []
    for m in base_models:
        models.extend(_candidate_models(m))

    # De-dupe while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for m in models:
        if m not in seen:
            seen.add(m)
            ordered.append(m)

    for m in ordered:
        if not m:
            continue
        try:
            base = get_ollama_url()
            r = requests.post(
                f"{base}/api/generate",
                json={"model": m, "prompt": prompt, "stream": False},
                timeout=timeout_s,
            )
            if r.status_code == 200:
                text = r.json().get("response", "").strip()
                if text:
                    return text, m
        except Exception:
            continue
    return None, None


def llm_generate(
    prompt: str,
    model: str | None = None,
    timeout_s: int = 60,
) -> tuple[str | None, str | None]:
    """Session-aware LLM routing (Ollama or per-user custom API)."""
    from streamlit_app.llm_provider import llm_generate as _route

    return _route(prompt, model=model, timeout_s=timeout_s)


def ollama_phrase_facts(facts: dict) -> tuple[str | None, str | None]:
    prompt = (
        "Use ONLY these facts. Do not add clinical advice beyond recommendations.\nFacts:\n"
        + json.dumps(facts)
        + "\nWrite 1-2 clinician-facing sentences."
    )
    return llm_generate(prompt)


def ollama_format_chat(facts: dict) -> tuple[str | None, str | None]:
    """
    Rephrase/format the final chatbot response professionally using ONLY the provided facts.
    Critical constraint: preserve all numeric values and identifiers exactly; do not recalculate.
    """
    prompt = (
        "You are formatting the final response for a hospital readmission analytics chatbot.\n"
        "Use ONLY the JSON facts provided by the caller.\n\n"
        "Hard rules:\n"
        "- Preserve all numbers (percentages, counts, probabilities) exactly as they appear.\n"
        "- Preserve all identifiers exactly (e.g., encounter_id, patient_nbr). Do not re-derive them.\n"
        "- Do not recalculate percentages or ratios.\n"
        "- Do not add clinical diagnosis/treatment guidance.\n"
        "- If the deterministic_answer is a security refusal or data-mutation refusal, keep it unchanged.\n"
        "- Output ONLY the final answer in Markdown (no JSON, no commentary).\n\n"
        "Facts JSON:\n"
        + json.dumps(facts)
    )
    return llm_generate(prompt, timeout_s=30)


def ollama_chat_answer(
    question: str,
    role: str,
    context: dict | None = None,
) -> tuple[str | None, str | None]:
    """
    Answer a user question when deterministic/project-specific handlers don't match.

    Safety constraints:
    - Refuse medical diagnosis or prescribing/treatment instructions.
    - Do not invent patient identifiers or certified metric values.
    - Keep tone professional and output Markdown only.
    """
    safe_context = context or {}
    prompt = (
        "You are the Hospital Readmission Analytics chatbot for this project.\n"
        "Your job is to help the user with project-related analytics questions, app usage, and governance.\n\n"
        "User role: "
        + str(role)
        + "\n\n"
        "User question:\n"
        + question
        + "\n\n"
        "Context (what you can rely on):\n"
        + json.dumps(safe_context)
        + "\n\n"
        "Hard safety rules:\n"
        "- Never provide medical diagnosis, prescriptions, or treatment instructions.\n"
        "- Never add, edit, delete, falsify, or overwrite patient records, encounter history, "
        "or certified clinical data in any role (Viewer, Clinician, Analyst). "
        "Refuse such requests and cite read-only security policy.\n"
        "- Never invent patient-specific identifiers or patient data (e.g., encounter_id, patient_nbr). "
        "If the user asks for patient-specific details and those values are not present in the context, refuse and redirect to using the Risk Prediction page.\n"
        "- Never invent certified metrics/percentages/counts. "
        "If the question asks for a certified metric value and it is not included in the context, explain that you don't have the certified number and suggest checking the dashboards or running the pipeline.\n"
        "- If the question is outside the hospital analytics scope but harmless, answer generally (briefly) without making clinical claims.\n\n"
        "Output requirements:\n"
        "- Output ONLY the final answer in Markdown.\n"
        "- Do not output JSON.\n"
    )
    return llm_generate(prompt, timeout_s=45)
