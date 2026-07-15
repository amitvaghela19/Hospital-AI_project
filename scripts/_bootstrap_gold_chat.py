"""Bootstrap: gold-standard chatbot implementation files."""
from pathlib import Path
ROOT = Path(r"e:/Amit/Project/Hospital project")

def w(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print("wrote", rel)

# promoted_qa.py
w("chatbot/promoted_qa.py", '''"""Promoted Q&A pairs from chat feedback."""
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
''')

# chat_store.py
w("mcp/services/chat_store.py", '''"""Persistent chat turn storage."""
from __future__ import annotations
import json, uuid
from datetime import datetime, timezone
from typing import Any
from mcp.common import PATHS

def _path():
    return PATHS.get("chat_sessions", PATHS["audit"].parent / "chat_sessions.json")

def append_turn(*, session_id: str, role: str, question: str, answer: str, route: str,
                rag_mode: str = "n/a", stages: list[str] | None = None, turn_id: str | None = None) -> dict[str, Any]:
    path = _path(); path.parent.mkdir(parents=True, exist_ok=True)
    turns = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    entry = {"turn_id": turn_id or str(uuid.uuid4()), "session_id": session_id, "role": role,
             "question": question, "answer": answer, "route": route, "rag_mode": rag_mode,
             "stages": stages or [], "ts": datetime.now(timezone.utc).isoformat()}
    turns.append(entry)
    path.write_text(json.dumps(turns[-2000:], indent=2), encoding="utf-8")
    return entry
''')

# feedback_svc.py - truncated in bootstrap, full file next
print("bootstrap partial ok")
