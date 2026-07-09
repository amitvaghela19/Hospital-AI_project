from __future__ import annotations

import json

from mcp.common import CHROMA_COLLECTION, PATHS
from chatbot.intent import format_rag_answer, has_project_context, is_patient_lookup_request


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
