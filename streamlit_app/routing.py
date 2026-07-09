from __future__ import annotations

import re
import json
from collections.abc import Callable
from pathlib import Path

import streamlit as st

from chatbot.intent import (
    extract_patient_nbr,
    is_off_topic,
    is_patient_lookup_request,
    off_topic_reply,
    wants_dimensional_metric,
    wants_metric,
)
from chatbot.learned import match_learned
from chatbot import refusal_templates as refuse_tpl
from inference.tribunal import route_message_tribunal
from mcp.client.pool import pool
from streamlit_app import ROOT
from streamlit_app.components.chat_progress import map_tribunal_stage, progress_emit
from streamlit_app.components.health_panel import rag_mode_label
from streamlit_app.rbac import can_fred, can_sql, get_role_config, ids_policy
from streamlit_app.rbac_auth import validate_role
from streamlit_app.security import is_data_mutation_request, refuse_data_mutation

SCRIPTS: list[dict] = []
for p in (ROOT / "chatbot" / "scripts").glob("*.json"):
    SCRIPTS.extend(json.loads(p.read_text(encoding="utf-8")))


def match_script(message: str) -> dict | None:
    msg = message.lower()
    best, hits_best = None, 0
    for item in SCRIPTS:
        hits = sum(1 for pat in item.get("patterns", []) if pat.lower() in msg)
        if hits > hits_best:
            best, hits_best = item, hits
    return best if hits_best else None


def _role_can_sql(role: str) -> bool:
    return can_sql(role)


def _role_can_fred(role: str) -> bool:
    return can_fred(role)


def suggested_prompts(role: str | None = None) -> list[str]:
    role = validate_role(role)
    cfg = get_role_config(role)
    prompts = [
        "What is the 30-day readmission rate?",
        "What is the average length of stay?",
        "How do I run the pipeline?",
        "Who are you?",
    ]
    if cfg.get("chat_high_risk_list"):
        prompts.append("Top 10 high risk encounters")
    if cfg.get("chat_encounter_detail"):
        prompts.append("Tell me about this encounter_id 203143410")
    if cfg.get("can_sql"):
        prompts.append("SELECT age, COUNT(*) FROM encounters LIMIT 5")
    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for p in prompts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:8]


def route_chat(
    message: str,
    role: str,
    use_tribunal: bool = False,
    last_scored_row: dict | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[str, str, list[str] | None, str]:
    """
    Returns (answer, route, stages, rag_mode).
    rag_mode: chroma | keyword_fallback | n/a
    """
    role = validate_role(role)
    lowered = message.lower()
    rag_mode = "n/a"
    progress_emit(on_progress, "analyzing")

    def _role_ids_policy(r: str) -> tuple[bool, bool]:
        return ids_policy(r)

    def _finalize(
        deterministic_answer: str,
        route: str,
        stages: list[str] | None,
        rag_mode_value: str,
        *,
        llm_facts: dict | None = None,
        format_with_llm: bool = True,
    ) -> tuple[str, str, list[str] | None, str]:
        """
        Always try to rephrase with Ollama for a professional tone.
        Falls back to deterministic answer if Ollama is unavailable.
        """
        if not format_with_llm:
            return (deterministic_answer, route, stages, rag_mode_value)

        progress_emit(on_progress, "formatting")
        facts = {
            "question": message,
            "route": route,
            "stages": stages,
            "rag_mode": rag_mode_value,
            "deterministic_answer": deterministic_answer,
        }
        if llm_facts is not None:
            facts["payload"] = llm_facts

        formatted, _model_id = pool.ollama_format_chat(facts)
        return (formatted or deterministic_answer, route, stages, rag_mode_value)

    if re.search(r"\b(password|passcode|unlock code|credentials?)\b", lowered) and re.search(
        r"\b(what|tell|give|share|reveal|bypass|jailbreak|ignore)\b", lowered
    ):
        progress_emit(on_progress, "permissions")
        return _finalize(
            "I cannot disclose RBAC passwords or bypass access controls. "
            "Use the sidebar unlock panel with your authorized credential.",
            "refuse",
            None,
            rag_mode,
            format_with_llm=False,
        )

    if is_data_mutation_request(message):
        progress_emit(on_progress, "permissions")
        pool.audit(role, "refuse_data_mutation", {"preview": message[:120]})
        return _finalize(
            refuse_data_mutation(role),
            "refuse",
            None,
            rag_mode,
            format_with_llm=False,
        )

    def _maybe_mask_patient_nbr(records: list[dict], *, mask_patient_nbr: bool) -> list[dict]:
        if not mask_patient_nbr:
            return records
        masked: list[dict] = []
        for r in records:
            r2 = dict(r)
            r2.pop("patient_nbr", None)
            masked.append(r2)
        return masked

    def _parse_top_high_risk_n(msg: str) -> int | None:
        # Examples:
        # - "give me list of top 10 encounters who has high risk"
        # - "top encounters high risk"
        if "high risk" not in msg:
            return None
        if not any(x in msg for x in ["top", "highest", "most"]):
            return None
        if not any(x in msg for x in ["encounter", "patient"]):
            return None
        m = re.search(r"\btop\s*(\d{1,3})\b", msg)
        if m:
            return int(m.group(1))
        return 10

    def _extract_encounter_id(msg: str) -> int | None:
        m = re.search(r"\bencounter[_\s]?id\s*(\d+)\b", msg)
        if m:
            return int(m.group(1))
        return None

    if any(x in lowered for x in ["prescribe", "diagnose me", "what drug should"]):
        progress_emit(on_progress, "permissions")
        ans = "I cannot provide medical diagnosis or prescribing advice."
        return _finalize(ans, "refuse", None, rag_mode)

    if ("similar" in lowered or "like this patient" in lowered) and last_scored_row:
        progress_emit(on_progress, "certified_data")
        sim = pool.similar_cohort(last_scored_row)
        if sim:
            return _finalize(sim, "similarity_mcp", ["context:last_scored_encounter"], rag_mode)
        return _finalize(
            "No similar cohort index. Index neighbors on **System Health Diagnose** first.",
            "similarity_mcp",
            None,
            rag_mode,
        )

    # ---- Certified mart deterministic intents (avoid RAG hijacking) ----
    top_n = _parse_top_high_risk_n(lowered)
    if top_n is not None:
        progress_emit(on_progress, "permissions")
        cfg = get_role_config(role)
        if not cfg.get("chat_high_risk_list"):
            ans = refuse_tpl.refuse_high_risk_list(role)
            return _finalize(ans, "refuse", None, rag_mode, format_with_llm=False)

        can_ids, mask_patient = _role_ids_policy(role)
        if not can_ids:
            ans = refuse_tpl.refuse_no_ids(role)
            return _finalize(ans, "refuse", None, rag_mode, format_with_llm=False)

        progress_emit(on_progress, "certified_data")
        records = pool.top_high_risk_encounters(top_n)
        if not records:
            ans = "No high-risk encounters found in the current certified dataset."
            return _finalize(ans, "high_risk_mart", None, rag_mode)

        records = _maybe_mask_patient_nbr(records, mask_patient_nbr=mask_patient)
        def _fmt_prob(v) -> str:
            try:
                return f"{float(v):.4f}"
            except Exception:
                return str(v)

        lines = []
        for i, r in enumerate(records, start=1):
            enc = r.get("encounter_id")
            pat = r.get("patient_nbr")
            age = r.get("age", "")
            gender = r.get("gender", "")
            y_prob = r.get("y_prob")
            risk_band = r.get("risk_band", "")
            top_factors = r.get("top_factors") or []
            tf = ", ".join(top_factors) if top_factors else "n/a"

            if pat is not None:
                lines.append(
                    f"{i}. encounter_id={enc}, patient_nbr={pat}, age={age}, gender={gender}, risk_band={risk_band}, y_prob={_fmt_prob(y_prob)}, top_factors=[{tf}]"
                )
            else:
                lines.append(
                    f"{i}. encounter_id={enc}, age={age}, gender={gender}, risk_band={risk_band}, y_prob={_fmt_prob(y_prob)}, top_factors=[{tf}]"
                )

        ans = f"Top {top_n} high-risk encounters (sorted by model probability):\n" + "\n".join(lines)

        # Log even when the user enables Tribunal.
        pool.audit(role, "high_risk_mart", {"top_n": top_n, "count": len(records)})

        return _finalize(
            ans,
            "high_risk_mart",
            None,
            rag_mode,
            llm_facts={"high_risk_encounters": records, "top_n": top_n},
        )

    encounter_id = _extract_encounter_id(lowered)
    if encounter_id is None and ("this encounter" in lowered or "that encounter" in lowered):
        if isinstance(last_scored_row, dict) and last_scored_row.get("encounter_id") is not None:
            try:
                encounter_id = int(last_scored_row.get("encounter_id"))
            except Exception:
                encounter_id = None

    if encounter_id is not None:
        progress_emit(on_progress, "permissions")
        cfg = get_role_config(role)
        if not cfg.get("chat_encounter_detail"):
            ans = refuse_tpl.refuse_encounter_detail(role)
            return _finalize(ans, "refuse", None, rag_mode, format_with_llm=False)

        can_ids, mask_patient = _role_ids_policy(role)
        if not can_ids:
            ans = refuse_tpl.refuse_no_ids(role)
            return _finalize(ans, "refuse", None, rag_mode, format_with_llm=False)

        progress_emit(on_progress, "certified_data")
        detail = pool.encounter_detail(encounter_id)
        if not detail:
            ans = f"No encounter found for encounter_id={encounter_id} in the certified dataset."
            return _finalize(ans, "encounter_detail_mart", None, rag_mode)

        if mask_patient:
            detail.pop("patient_nbr", None)

        pool.audit(
            role,
            "encounter_detail_mart",
            {"encounter_id": encounter_id, "masked_patient_nbr": mask_patient},
        )

        tf = detail.get("top_factors") or []
        tf_s = ", ".join(tf) if tf else "n/a"
        ans = (
            f"Encounter details for encounter_id={encounter_id}:\n"
            f"- age: {detail.get('age', '')}\n"
            f"- gender: {detail.get('gender', '')}\n"
            f"- risk_band: {detail.get('risk_band', '')}\n"
            f"- y_prob: {detail.get('y_prob')}\n"
            + (f"- patient_nbr: {detail.get('patient_nbr')}\n" if detail.get("patient_nbr") is not None else "")
            + f"- top_factors: [{tf_s}]"
        )
        return _finalize(
            ans,
            "encounter_detail_mart",
            None,
            rag_mode,
            llm_facts={"encounter_detail": detail, "encounter_id": encounter_id},
        )

    if is_patient_lookup_request(message):
        progress_emit(on_progress, "permissions")
        cfg = get_role_config(role)
        if not cfg.get("chat_encounter_detail"):
            ans = refuse_tpl.refuse_encounter_detail(role)
            return _finalize(ans, "refuse", None, rag_mode, format_with_llm=False)

        can_ids, mask_patient = _role_ids_policy(role)
        if not can_ids:
            ans = refuse_tpl.refuse_no_ids(role)
            return _finalize(ans, "refuse", None, rag_mode, format_with_llm=False)

        patient_nbr = extract_patient_nbr(message)
        if not patient_nbr:
            ans = (
                "Please provide a patient ID to look up, for example: "
                "`check patient 88479036 available` or `patient id 74478915`."
            )
            return _finalize(ans, "patient_lookup_mart", None, rag_mode, format_with_llm=False)

        progress_emit(on_progress, "certified_data")
        result = pool.patient_lookup(patient_nbr)
        pool.audit(
            role,
            "patient_lookup_mart",
            {
                "patient_nbr": patient_nbr,
                "found": result.get("found"),
                "masked_patient_nbr": mask_patient,
            },
        )

        if not result.get("found"):
            ans = (
                f"**No** — patient_nbr **{patient_nbr}** is not in the certified dataset "
                f"(exact match on `mart_clinical_risk`)."
            )
            return _finalize(ans, "patient_lookup_mart", None, rag_mode, format_with_llm=False)

        encounters = result.get("encounters") or []
        enc_ids = [e.get("encounter_id") for e in encounters if e.get("encounter_id") is not None]
        enc_list = ", ".join(f"encounter_id={eid}" for eid in enc_ids)
        count = result.get("encounter_count", len(enc_ids))

        if mask_patient:
            ans = (
                f"**Yes** — {count} encounter(s) on file: {enc_list}. "
                f"(Patient ID masked in Clinician mode.)"
            )
        else:
            ans = (
                f"**Yes** — patient_nbr **{patient_nbr}** has {count} encounter(s) "
                f"on file: {enc_list}."
            )
        return _finalize(
            ans,
            "patient_lookup_mart",
            None,
            rag_mode,
            format_with_llm=False,
            llm_facts={"patient_lookup": result, "patient_nbr": patient_nbr},
        )

    if "fred" in lowered or "unemployment" in lowered or "cpi" in lowered:
        progress_emit(on_progress, "permissions")
        if not _role_can_fred(role):
            return _finalize(
                refuse_tpl.refuse_fred(role),
                "refuse",
                None,
                rag_mode,
                format_with_llm=False,
            )
        progress_emit(on_progress, "macro_data")
        series = "UNRATE" if "unemployment" in lowered else "CPIAUCSL"
        return _finalize(str(pool.fred_series(series)), "fred_mcp", None, rag_mode)

    if "select" in lowered and "from" in lowered:
        progress_emit(on_progress, "permissions")
        if not _role_can_sql(role):
            return _finalize(
                refuse_tpl.refuse_sql(role),
                "refuse",
                None,
                rag_mode,
                format_with_llm=False,
            )
        progress_emit(on_progress, "certified_data")
        try:
            return _finalize(pool.sqlite_query(message), "sqlite_mcp", None, rag_mode)
        except Exception as exc:
            return _finalize(f"SQLite error: {exc}", "sqlite_mcp", None, rag_mode)

    if is_off_topic(message):
        return _finalize(off_topic_reply(), "refuse", None, rag_mode)

    if use_tribunal:
        progress_emit(on_progress, "tribunal")
        if "select" in lowered and "from" in lowered and not _role_can_sql(role):
            return _finalize(
                "Your role cannot run SQL queries.",
                "refuse",
                ["rbac:sql_denied"],
                rag_mode,
            )
        if ("similar" in lowered or "like this patient" in lowered) and last_scored_row:
            sim = pool.similar_cohort(last_scored_row)
            if sim:
                pool.audit(role, "similarity_mcp", {"stages": ["context:last_scored_encounter"]})
                return _finalize(
                    sim,
                    "similarity_mcp",
                    ["tool_router:similarity_context"],
                    rag_mode,
                )
        out = route_message_tribunal(message, role, match_script)
        for stage in out.get("stages") or []:
            if on_progress is not None:
                on_progress(map_tribunal_stage(str(stage)))
        route = out["route"]
        if route == "vector_rag_mcp":
            rag_mode = rag_mode_label()

        # If tribunal couldn't find a deterministic answer, allow the LLM fallback
        # to produce a general (non-clinical) response when appropriate.
        if route == "refuse":
            progress_emit(on_progress, "formatting")
            llm_context = {"last_scored_row": None}
            can_ids, mask_patient = _role_ids_policy(role)
            if can_ids and isinstance(last_scored_row, dict):
                llm_context["last_scored_row"] = dict(last_scored_row)
                if mask_patient:
                    llm_context["last_scored_row"].pop("patient_nbr", None)

            llm_text, _model = pool.ollama_chat_answer(
                question=message,
                role=role,
                context=llm_context,
            )
            if llm_text:
                return (llm_text, "llm_fallback", out.get("stages"), "n/a")

        return _finalize(out["answer"], route, out.get("stages"), rag_mode)

    progress_emit(on_progress, "certified_data")
    dim = pool.dimensional_metric(message)
    if dim:
        return _finalize(dim, "dimensional_metric_mcp", None, rag_mode)

    learned = match_learned(message)
    if learned:
        progress_emit(on_progress, "knowledge")
        return _finalize(learned["answer"], "learned_qa", None, rag_mode)

    allow_script = not wants_metric(lowered) or wants_dimensional_metric(message)
    hit = match_script(message)
    if hit and allow_script:
        progress_emit(on_progress, "knowledge")
        return _finalize(hit["answer"], "script_qa", None, rag_mode)

    progress_emit(on_progress, "knowledge")
    sem = pool.semantic_metric(message)
    if sem:
        route = "dimensional_metric_mcp" if wants_dimensional_metric(message) else "semantic_metric_mcp"
        return _finalize(sem, route, None, rag_mode)

    rag = pool.rag_answer(message)
    rag_mode = rag_mode_label()
    if rag:
        prefix = ""
        if rag_mode == "keyword_fallback":
            prefix = "[Keyword RAG fallback — index Chroma for semantic search]\n\n"
        return _finalize(prefix + rag, "vector_rag_mcp", None, rag_mode)

    ans = (
        "I can only answer from project knowledge, gold-standard scripts, "
        "certified metrics, or a structured risk prediction."
    )

    can_ids, mask_patient = _role_ids_policy(role)
    llm_context = {"last_scored_row": None}
    if can_ids and isinstance(last_scored_row, dict):
        llm_context["last_scored_row"] = dict(last_scored_row)
        if mask_patient:
            llm_context["last_scored_row"].pop("patient_nbr", None)

    progress_emit(on_progress, "formatting")
    llm_text, _model = pool.ollama_chat_answer(
        question=message,
        role=role,
        context=llm_context,
    )
    if llm_text:
        # LLM fallback already returns a final Markdown answer; skip the formatter
        # to avoid double-LLM calls.
        return (llm_text, "llm_fallback", None, "n/a")

    return _finalize(ans, "refuse", None, rag_mode)
