from __future__ import annotations
from langchain_core.messages import HumanMessage
from chatbot.graph.workflow import app
from streamlit_app.rbac import get_role_config
from streamlit_app.rbac_auth import validate_role
from typing import Callable
from mcp.client.pool import pool
from streamlit_app.components.chat_progress import progress_emit

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
    
    seen = set()
    out = []
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
    
    role = validate_role(role)
    
    # Initialize state
    initial_state = {
        "messages": [HumanMessage(content=message)],
        "role": role,
        "last_scored_row": last_scored_row,
        "route": "",
        "stages": [],
        "rag_mode": "n/a",
        "sql_query": None,
        "sql_result": None,
        "sql_retries": 0,
        "raw_context": None,
        "llm_facts": None,
        "final_answer": None
    }
    
    # Run the graph and stream events for progress updates
    final_state = initial_state
    
    try:
        # stream_mode="values" yields the FULL state after each node execution
        for state in app.stream(initial_state, stream_mode="values"):
            final_state = state
            # We don't have the exact node name here, but we can emit a progress pulse
            progress_emit(on_progress, "processing")
    except Exception as e:
        return f"Graph execution error: {e}", "error", None, "n/a"
        
    if final_state is None:
        return "Internal Graph Error", "error", None, "n/a"
        
    final_answer = final_state.get("final_answer", "No response generated.")
    route = final_state.get("route", "unknown")
    stages = final_state.get("stages", [])
    rag_mode = final_state.get("rag_mode", "n/a")
    
    return final_answer, route, stages, rag_mode
