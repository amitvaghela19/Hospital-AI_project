"""Persistent chat turn storage."""
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
