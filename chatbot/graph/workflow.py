from langgraph.graph import StateGraph, END
from chatbot.graph.state import ChatState
from chatbot.graph.nodes import (
    guardrails_node,
    router_node,
    faq_node,
    lookup_node,
    fred_node,
    sql_generate_node,
    sql_execute_node,
    rag_node,
    synthesis_node
)

def build_graph():
    builder = StateGraph(ChatState)
    
    # Add nodes
    builder.add_node("guardrails", guardrails_node)
    builder.add_node("router", router_node)
    builder.add_node("faq", faq_node)
    builder.add_node("lookup", lookup_node)
    builder.add_node("fred", fred_node)
    builder.add_node("sql_generator", sql_generate_node)
    builder.add_node("sql_executor", sql_execute_node)
    builder.add_node("rag", rag_node)
    builder.add_node("synthesis", synthesis_node)
    
    # Define edges
    # Start -> Guardrails
    builder.set_entry_point("guardrails")
    
    def check_guardrails(state: ChatState) -> str:
        if state.get("route") == "refuse":
            return "end"
        return "continue"
        
    builder.add_conditional_edges(
        "guardrails",
        check_guardrails,
        {"end": END, "continue": "router"}
    )
    
    def route_decision(state: ChatState) -> str:
        r = state.get("route")
        if r in ("script_qa", "promoted_qa_qa", "dimensional_metric_mcp", "semantic_metric_mcp"):
            return "faq"
        if r in ("high_risk_mart", "encounter_detail_mart", "patient_lookup_mart", "similarity_mcp"):
            return "lookup"
        if r == "fred_mcp":
            return "fred"
        if r == "sqlite_mcp_generate":
            return "sql_generator"
        if r == "sqlite_mcp_direct":
            return "sql_executor"
        if r == "refuse":
            return "end"
        return "rag"
        
    builder.add_conditional_edges(
        "router",
        route_decision,
        {
            "faq": "faq",
            "lookup": "lookup",
            "fred": "fred",
            "sql_generator": "sql_generator",
            "sql_executor": "sql_executor",
            "rag": "rag",
            "end": END
        }
    )
    
    # Path for SQL Generation
    builder.add_edge("sql_generator", "sql_executor")
    
    def check_sql_error(state: ChatState) -> str:
        """Read-only routing — never mutate state here (LangGraph will not persist it)."""
        if state.get("final_answer"):
            return "continue"
        res = str(state.get("sql_result") or "")
        lower = res.lower()
        is_err = (
            "error:" in lower
            or "no such column:" in lower
            or "unrecognized token:" in lower
        )
        retries = int(state.get("sql_retries") or 0)
        # Cap at 2 regenerations after the first failure (sql_retries bumped in sql_generate_node).
        if is_err and retries < 2:
            return "retry"
        return "continue"

    builder.add_conditional_edges(
        "sql_executor",
        check_sql_error,
        {"retry": "sql_generator", "continue": "synthesis"},
    )
    
    # Path for other nodes going directly to synthesis
    builder.add_edge("faq", "synthesis")
    builder.add_edge("lookup", "synthesis")
    builder.add_edge("fred", "synthesis")
    builder.add_edge("rag", "synthesis")
    
    # Synthesis -> END
    builder.add_edge("synthesis", END)
    
    return builder.compile()

app = build_graph()
