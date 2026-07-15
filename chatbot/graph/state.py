from typing import TypedDict, Annotated, Sequence, Any
import operator
from langchain_core.messages import BaseMessage

class ChatState(TypedDict):
    # Core input
    messages: Annotated[Sequence[BaseMessage], operator.add]
    role: str
    last_scored_row: dict | None
    
    # Graph execution state
    route: str
    stages: Annotated[list[str], operator.add]
    rag_mode: str
    
    # Data payloads
    sql_query: str | None
    sql_result: str | None
    sql_retries: int
    raw_context: str | None
    llm_facts: dict | None
    
    # Final output
    final_answer: str | None
