from __future__ import annotations

import json

from mcp.common import CHROMA_COLLECTION, PATHS
from chatbot.graph.utils import is_patient_lookup_request

def has_project_context(msg: str) -> bool:
    return any(x in msg.lower() for x in ["hospital", "patient", "encounter", "model", "pipeline", "predict", "train"])

def format_rag_answer(message: str, docs: list[str], ids: list[str]) -> str:
    if not docs:
        return ""
    combined = "\n\n".join(docs)
    return f"Based on our project documentation:\n\n{combined}"


def _keyword_rag(message: str) -> str | None:
    if is_patient_lookup_request(message):
        return None
    docs = json.loads(PATHS["rag_docs"].read_text(encoding="utf-8"))
    words = message.lower().split()
    # Sort by score only (avoid comparing dicts when scores tie).
    scored = sorted(
        ((sum(w in d["text"].lower() for w in words), d) for d in docs),
        key=lambda x: x[0],
        reverse=True,
    )
    if scored and scored[0][0] > 0:
        d = scored[0][1]
        if scored[0][0] < 2 and not has_project_context(message):
            return None
        return d["text"]
    return None


def rag_query(message: str, n_results: int = 3) -> str | None:
    if is_patient_lookup_request(message):
        return None
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(PATHS["vectordb"]))
        col = client.get_or_create_collection(CHROMA_COLLECTION)
        if col.count() == 0:
            return _keyword_rag(message)
        res = col.query(query_texts=[message], n_results=min(n_results, col.count()))
        docs = res.get("documents", [[]])[0]
        ids = res.get("ids", [[]])[0]
        if not docs:
            return _keyword_rag(message)
        formatted = format_rag_answer(message, docs, ids)
        if formatted:
            return formatted
        return _keyword_rag(message)
    except Exception:
        return _keyword_rag(message)
