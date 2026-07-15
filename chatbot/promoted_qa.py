"""Promoted Q&A pairs from chat feedback."""
from __future__ import annotations
import json
from streamlit_app import ROOT
promoted_qa_PATH = ROOT / "data" / "nosql" / "promoted_qa_answers.json"
promoted_qa: list[dict] = []

def reload_promoted_qa() -> None:
    global promoted_qa
    promoted_qa = json.loads(promoted_qa_PATH.read_text(encoding="utf-8")) if promoted_qa_PATH.exists() else []

reload_promoted_qa()

def match_promoted_qa(message: str) -> dict | None:
    msg = message.lower()
    best, hits_best = None, 0
    for item in promoted_qa:
        hits = sum(1 for pat in item.get("patterns", []) if pat.lower() in msg)
        if hits > hits_best:
            best, hits_best = item, hits
    return best if hits_best else None
