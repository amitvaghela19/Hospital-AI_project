import re
from langchain_core.messages import HumanMessage
from chatbot.graph.state import ChatState
from chatbot.graph.utils import match_script, is_patient_lookup_request, extract_patient_nbr
from chatbot.promoted_qa import match_promoted_qa
from chatbot import refusal_templates as refuse_tpl
from streamlit_app.chat_security import is_data_mutation_request, refuse_data_mutation
from streamlit_app.rbac import can_sql, can_fred, get_role_config, ids_policy
from mcp.client.pool import pool

def wants_metric(msg: str) -> bool:
    return any(h in msg.lower() for h in ["rate", "average", "avg", "count", "percent", "%", "length of stay", "los", "kpi"])

def wants_dimensional_metric(msg: str) -> bool:
    has_dim = any(h in msg.lower() for h in ["male", "female", "gender", "race", "age", "[10", "[20"])
    return has_dim and wants_metric(msg)

def is_off_topic(msg: str) -> bool:
    # A simple LLM-like keyword heuristic for out of scope
    off_topic = ["write code", "poem", "weather", "recipe", "diagnose me", "medical advice"]
    return any(x in msg.lower() for x in off_topic)

def off_topic_reply() -> str:
    return "Query blocked: Out of scope."

def _get_last_user_message(state: ChatState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""

def _parse_top_high_risk_n(msg: str) -> int | None:
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

def guardrails_node(state: ChatState) -> dict:
    message = _get_last_user_message(state)
    lowered = message.lower()
    role = state.get("role", "viewer")
    
    if re.search(r"\b(password|passcode|unlock code|credentials?)\b", lowered) and re.search(
        r"\b(what|tell|give|share|reveal|bypass|jailbreak|ignore)\b", lowered
    ):
        return {
            "route": "refuse",
            "final_answer": "I cannot disclose RBAC passwords or bypass access controls. Use the sidebar unlock panel with your authorized credential."
        }

    if is_data_mutation_request(message):
        pool.audit(role, "refuse_data_mutation", {"preview": message[:120]})
        return {
            "route": "refuse",
            "final_answer": refuse_data_mutation(role)
        }

    if any(x in lowered for x in ["prescribe", "diagnose me", "what drug should"]):
        return {
            "route": "refuse",
            "final_answer": "I cannot provide medical diagnosis or prescribing advice."
        }

    return {}

def router_node(state: ChatState) -> dict:
    message = _get_last_user_message(state)
    lowered = message.lower()
    role = state.get("role", "viewer")
    last_scored_row = state.get("last_scored_row")

    if ("similar" in lowered or "like this patient" in lowered) and last_scored_row:
        return {"route": "similarity_mcp", "stages": ["context:last_scored_encounter"]}
        
    top_n = _parse_top_high_risk_n(lowered)
    if top_n is not None:
        return {"route": "high_risk_mart", "llm_facts": {"top_n": top_n}}
        
    encounter_id = _extract_encounter_id(lowered)
    if encounter_id is None and ("this encounter" in lowered or "that encounter" in lowered):
        if isinstance(last_scored_row, dict) and last_scored_row.get("encounter_id") is not None:
            try:
                encounter_id = int(last_scored_row.get("encounter_id"))
            except Exception:
                pass
    if encounter_id is not None:
        return {"route": "encounter_detail_mart", "llm_facts": {"encounter_id": encounter_id}}
        
    if is_patient_lookup_request(message):
        return {"route": "patient_lookup_mart"}
        
    if "fred" in lowered or "unemployment" in lowered or "cpi" in lowered:
        return {"route": "fred_mcp"}
        
    if can_sql(role) and not ("select" in lowered and "from" in lowered):
        data_keywords = [
            "how many", "count", "average", "avg", "mean", "rate", "percent", "percentage",
            "maximum", "max", "minimum", "min", "length of stay", "visit", "high risk", "readmission",
            "low risk", "risk", "meds", "age", "male", "female", "patients", "encounters", "stay"
        ]
        if any(kw in lowered for kw in data_keywords) or wants_metric(message):
            return {"route": "sqlite_mcp_generate", "stages": ["tool_router:sqlite_compiled"]}
            
    if "select" in lowered and "from" in lowered:
        return {"route": "sqlite_mcp_direct"}
        
    allow_script = not wants_metric(lowered) or wants_dimensional_metric(message)
    hit = match_script(message)
    if hit and allow_script:
        return {"route": "script_qa", "raw_context": hit["answer"]}
        
    promoted_qa = match_promoted_qa(message)
    if promoted_qa:
        return {"route": "promoted_qa_qa", "raw_context": promoted_qa["answer"]}
        
    if is_off_topic(message):
        return {"route": "refuse", "final_answer": off_topic_reply()}
        
    dim = pool.dimensional_metric(message)
    if dim:
        return {"route": "dimensional_metric_mcp", "raw_context": dim}
        
    sem = pool.semantic_metric(message)
    if sem:
        route_str = "dimensional_metric_mcp" if wants_dimensional_metric(message) else "semantic_metric_mcp"
        return {"route": route_str, "raw_context": sem}
        
    return {"route": "vector_rag_mcp"}

def faq_node(state: ChatState) -> dict:
    return {"final_answer": state.get("raw_context")}

def lookup_node(state: ChatState) -> dict:
    message = _get_last_user_message(state)
    role = state.get("role", "viewer")
    route = state.get("route")
    cfg = get_role_config(role)
    can_ids, mask_patient = ids_policy(role)
    
    def maybe_mask(records):
        if not mask_patient: return records
        return [{k: v for k, v in r.items() if k != "patient_nbr"} for r in records]
        
    if route == "high_risk_mart":
        if not cfg.get("chat_high_risk_list"):
            return {"route": "refuse", "final_answer": refuse_tpl.refuse_high_risk_list(role)}
        if not can_ids:
            return {"route": "refuse", "final_answer": refuse_tpl.refuse_no_ids(role)}
            
        top_n = state.get("llm_facts", {}).get("top_n", 10)
        records = pool.top_high_risk_encounters(top_n)
        pool.audit(role, "high_risk_mart", {"top_n": top_n, "count": len(records)})
        if not records:
            return {"raw_context": "No high-risk encounters found in the current certified dataset."}
            
        records = maybe_mask(records)
        return {"raw_context": str(records), "llm_facts": {"high_risk_encounters": records}}
        
    if route == "encounter_detail_mart":
        if not cfg.get("chat_encounter_detail"):
            return {"route": "refuse", "final_answer": refuse_tpl.refuse_encounter_detail(role)}
        if not can_ids:
            return {"route": "refuse", "final_answer": refuse_tpl.refuse_no_ids(role)}
            
        enc_id = state.get("llm_facts", {}).get("encounter_id")
        detail = pool.encounter_detail(enc_id)
        pool.audit(role, "encounter_detail_mart", {"encounter_id": enc_id, "masked_patient_nbr": mask_patient})
        if not detail:
            return {"raw_context": f"No encounter found for encounter_id={enc_id} in the certified dataset."}
        if mask_patient:
            detail.pop("patient_nbr", None)
        return {"raw_context": str(detail), "llm_facts": {"encounter_detail": detail}}
        
    if route == "patient_lookup_mart":
        if not cfg.get("chat_encounter_detail"):
            return {"route": "refuse", "final_answer": refuse_tpl.refuse_encounter_detail(role)}
        if not can_ids:
            return {"route": "refuse", "final_answer": refuse_tpl.refuse_no_ids(role)}
            
        patient_nbr = extract_patient_nbr(message)
        if not patient_nbr:
            return {"final_answer": "Please provide a patient ID to look up, for example: `check patient 88479036 available`."}
            
        result = pool.patient_lookup(patient_nbr)
        pool.audit(role, "patient_lookup_mart", {"patient_nbr": patient_nbr, "found": result.get("found"), "masked_patient_nbr": mask_patient})
        if not result.get("found"):
            return {"final_answer": f"**No** — patient_nbr **{patient_nbr}** is not in the certified dataset."}
            
        if mask_patient:
            result.pop("patient_nbr", None)
        return {"raw_context": str(result), "llm_facts": {"patient_lookup": result, "patient_nbr": patient_nbr}}

    if route == "similarity_mcp":
        sim = pool.similar_cohort(state.get("last_scored_row"))
        if sim:
            pool.audit(role, "similarity_mcp", {"stages": ["context:last_scored_encounter"]})
            return {"raw_context": sim}
        return {"final_answer": "No similar cohort index. Index neighbors on **System Health Diagnose** first."}
        
    return {}

def fred_node(state: ChatState) -> dict:
    role = state.get("role", "viewer")
    if not can_fred(role):
        return {"route": "refuse", "final_answer": refuse_tpl.refuse_fred(role)}
    message = _get_last_user_message(state).lower()
    series = "UNRATE" if "unemployment" in message else "CPIAUCSL"
    return {"raw_context": str(pool.fred_series(series))}

def sql_generate_node(state: ChatState) -> dict:
    role = state.get("role", "viewer")
    if not can_sql(role):
        return {"route": "refuse", "final_answer": refuse_tpl.refuse_sql(role)}
        
    message = _get_last_user_message(state)
    # If this is a retry, we inject the previous error into the prompt to self-correct
    err = state.get("sql_result")
    if err and state.get("sql_query"):
        prompt = f"Original question: {message}\nYour previous query: {state['sql_query']}\nFailed with error: {err}\nPlease fix the query."
    else:
        prompt = message
        
    generated_sql = pool.ollama_generate_sql(prompt)
    return {"sql_query": generated_sql}

def sql_execute_node(state: ChatState) -> dict:
    role = state.get("role", "viewer")
    if not can_sql(role):
        return {"route": "refuse", "final_answer": refuse_tpl.refuse_sql(role)}
        
    query = state.get("sql_query")
    if not query:
        # direct sql mode
        query = _get_last_user_message(state)
        
    if not query or not query.strip().lower().startswith("select"):
        return {"sql_result": "Error: Not a valid SELECT query."}
        
    try:
        res = pool.sqlite_query(query)
        return {"sql_result": res}
    except Exception as exc:
        return {"sql_result": f"SQLite error: {exc}"}

def rag_node(state: ChatState) -> dict:
    message = _get_last_user_message(state)
    rag = pool.rag_answer(message)
    return {"raw_context": rag}

def synthesis_node(state: ChatState) -> dict:
    # If final answer is already set (e.g. guardrails/faq), do nothing
    if state.get("final_answer"):
        return {}
        
    message = _get_last_user_message(state)
    route = state.get("route")
    
    # Check if we have SQL results
    if route in ("sqlite_mcp_generate", "sqlite_mcp_direct"):
        res = state.get("sql_result", "")
        # Format explicitly
        if "query" in message.lower() or "sql" in message.lower():
            ans = f"Compiled Query:\n```sql\n{state.get('sql_query')}\n```\n\nResult:\n{res}"
            return {"final_answer": ans, "route": "sqlite_mcp"}
        else:
            short_res = res if len(res) < 800 else res[:800] + "\n...[truncated]"
            formatted, _ = pool.ollama_format_chat({"Question": message, "Query Result": short_res})
            return {"final_answer": formatted if formatted else f"Result:\n{res}", "route": "sqlite_mcp"}

    # Use general ollama synthesis
    raw_ctx = state.get("raw_context")
    if not raw_ctx:
        return {"final_answer": "No information found.", "route": "refuse"}
        
    facts = {
        "question": message,
        "route": route,
        "stages": state.get("stages"),
        "rag_mode": state.get("rag_mode"),
        "deterministic_answer": raw_ctx,
    }
    llm_facts = state.get("llm_facts")
    if llm_facts:
        facts["payload"] = llm_facts
        
    formatted, _ = pool.ollama_format_chat(facts)
    return {"final_answer": formatted or raw_ctx}
