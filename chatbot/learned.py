"""Promoted Q&A pairs from chat feedback."""
from __future__ import annotations
import json
from streamlit_app import ROOT
LEARNED_PATH = ROOT / "data" / "nosql" / "learned_answers.json"
LEARNED: list[dict] = []

def reload_learned() -> None:
    global LEARNED
    LEARNED = json.loads(LEARNED_PATH.read_text(encoding="utf-8")) if LEARNED_PATH.exists() else []

reload_learned()

def match_learned(message: str) -> dict | None:
    msg = message.lower()
    best, hits_best = None, 0
    for item in LEARNED:
        hits = sum(1 for pat in item.get("patterns", []) if pat.lower() in msg)
        if hits > hits_best:
            best, hits_best = item, hits
    return best if hits_best else None
