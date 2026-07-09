from __future__ import annotations

import os
from typing import Callable, TypedDict

from chatbot.intent import is_off_topic, off_topic_reply, wants_dimensional_metric, wants_metric
from chatbot.learned import match_learned
from mcp.client.pool import pool


class TribunalState(TypedDict):
    message: str
    role: str
    route: str
    answer: str
    stages: list[str]
    fairness_warning: str


def _gender_recall_gap() -> float:
    reg = pool.champion()
    fairness = reg.get("fairness", [])
    recalls = [f["recall"] for f in fairness if f.get("group_type") == "gender"]
    if len(recalls) < 2:
        return 0.0
    return float(max(recalls) - min(recalls))


def clinical_guard(state: TribunalState) -> TribunalState:
    msg = state["message"].lower()
    stages = state.get("stages", [])
    from streamlit_app.security import is_data_mutation_request, refuse_data_mutation

    if is_data_mutation_request(state["message"]):
        return {
            **state,
            "route": "refuse",
            "answer": refuse_data_mutation(state.get("role", "viewer")),
            "stages": stages + ["clinical_guard:data_mutation_refuse"],
        }
    if any(x in msg for x in ["prescribe", "diagnose me", "what drug should"]):
        return {
            **state,
            "route": "refuse",
            "answer": "I cannot provide medical diagnosis or prescribing advice.",
            "stages": stages + ["clinical_guard:refuse"],
        }
    return {**state, "stages": stages + ["clinical_guard:pass"]}


def config_gate(state: TribunalState) -> TribunalState:
    stages = state.get("stages", [])
    try:
        reg = pool.champion()
        registry = pool.config_registry()
        if not reg or not registry:
            raise ValueError("config unavailable")
        return {**state, "stages": stages + ["config_gate:pass"]}
    except Exception as e:
        return {
            **state,
            "route": "refuse",
            "answer": f"Configuration gate failed: {e}",
            "stages": stages + ["config_gate:fail"],
        }


def tool_router(
    state: TribunalState,
    match_script: Callable[[str], dict | None],
) -> TribunalState:
    if state.get("route") == "refuse":
        return state
    msg = state["message"]
    lowered = msg.lower()
    stages = state.get("stages", [])

    if "similar" in lowered or "like this patient" in lowered:
        return {**state, "route": "similarity_mcp", "answer": "Use the prediction tab for encounter similarity.", "stages": stages + ["tool_router:similarity"]}
    if "fred" in lowered or "unemployment" in lowered or "cpi" in lowered:
        sid = "UNRATE" if "unemployment" in lowered else "CPIAUCSL"
        return {**state, "route": "fred_mcp", "answer": str(pool.fred_series(sid)), "stages": stages + ["tool_router:fred"]}
    if is_off_topic(msg):
        return {
            **state,
            "route": "refuse",
            "answer": off_topic_reply(),
            "stages": stages + ["tool_router:off_topic"],
        }
    dim = pool.dimensional_metric(msg)
    if dim:
        return {
            **state,
            "route": "dimensional_metric_mcp",
            "answer": dim,
            "stages": stages + ["tool_router:dimensional"],
        }
    learned = match_learned(msg)
    if learned:
        return {
            **state,
            "route": "learned_qa",
            "answer": learned["answer"],
            "stages": stages + ["tool_router:learned"],
        }
    allow_script = not wants_metric(lowered) or wants_dimensional_metric(msg)
    if wants_metric(lowered):
        sem = pool.semantic_metric(msg)
        if sem:
            route = "dimensional_metric_mcp" if wants_dimensional_metric(msg) else "semantic_metric_mcp"
            return {**state, "route": route, "answer": sem, "stages": stages + ["tool_router:metrics"]}
    hit = match_script(msg)
    if hit and allow_script:
        return {**state, "route": "script_qa", "answer": hit["answer"], "stages": stages + ["tool_router:script"]}
    sem = pool.semantic_metric(msg)
    if sem:
        route = "dimensional_metric_mcp" if wants_dimensional_metric(msg) else "semantic_metric_mcp"
        return {**state, "route": route, "answer": sem, "stages": stages + ["tool_router:metrics"]}
    if "select" in lowered and "from" in lowered:
        return {**state, "route": "sqlite_mcp", "answer": pool.sqlite_query(msg), "stages": stages + ["tool_router:sqlite"]}
    rag = pool.rag_answer(msg)
    if rag:
        return {**state, "route": "vector_rag_mcp", "answer": rag, "stages": stages + ["tool_router:rag"]}
    return {
        **state,
        "route": "refuse",
        "answer": "I can only answer from project knowledge, scripts, or certified metrics.",
        "stages": stages + ["tool_router:refuse"],
    }


def fairness_gate(state: TribunalState) -> TribunalState:
    if state.get("route") == "refuse":
        return state
    gap = _gender_recall_gap()
    warn_tol = float(os.environ.get("FAIRNESS_RECALL_GAP_WARN", "0.05"))
    warning = ""
    if gap > warn_tol:
        warning = f"Fairness note: gender recall gap={gap:.3f} exceeds warn threshold {warn_tol}."
    stages = state.get("stages", [])
    return {**state, "fairness_warning": warning, "stages": stages + ["fairness_gate:pass"]}


def audit_node(state: TribunalState) -> TribunalState:
    pool.audit(state["role"], state.get("route", "tribunal"), {
        "stages": state.get("stages", []),
        "fairness_warning": state.get("fairness_warning", ""),
    })
    answer = state.get("answer", "")
    if state.get("fairness_warning"):
        answer = f"{answer}\n\n{state['fairness_warning']}"
    return {**state, "answer": answer, "stages": state.get("stages", []) + ["audit:logged"]}


def route_message_tribunal(message: str, role: str, match_script: Callable[[str], dict | None]) -> dict:
    state: TribunalState = {
        "message": message,
        "role": role,
        "route": "",
        "answer": "",
        "stages": [],
        "fairness_warning": "",
    }
    state = clinical_guard(state)
    state = config_gate(state)
    state = tool_router(state, match_script)
    state = fairness_gate(state)
    state = audit_node(state)
    return {
        "route": state["route"],
        "answer": state["answer"],
        "stages": state["stages"],
    }
