"""Chat feedback (thumbs up/down) storage and promotion helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from mcp.common import PATHS

CERTIFIED_ROUTES = frozenset(
    {
        "semantic_metric_mcp",
        "dimensional_metric_mcp",
        "script_qa",
        "vector_rag_mcp",
        "promoted_qa_qa",
    }
)


def _feedback_path():
    return PATHS.get("chat_feedback", PATHS["audit"].parent / "chat_feedback.json")


def _promoted_qa_path():
    return PATHS.get("promoted_qa_answers", PATHS["audit"].parent / "promoted_qa_answers.json")


def record_feedback(
    *,
    turn_id: str,
    rating: int,
    role: str,
    route: str,
    question: str,
    answer: str,
) -> dict[str, Any]:
    path = _feedback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    entry = {
        "turn_id": turn_id,
        "rating": int(rating),
        "role": role,
        "route": route,
        "question": question,
        "answer": answer,
        "ts": datetime.now(timezone.utc).isoformat(),
        "promoted": False,
    }
    rows.append(entry)
    path.write_text(json.dumps(rows[-5000:], indent=2), encoding="utf-8")
    return entry


def feedback_stats() -> dict[str, int]:
    path = _feedback_path()
    if not path.exists():
        return {"positive": 0, "negative": 0, "pending_promotion": 0}
    rows = json.loads(path.read_text(encoding="utf-8"))
    positive = sum(1 for r in rows if r.get("rating") == 1)
    negative = sum(1 for r in rows if r.get("rating") == 0)
    pending = sum(
        1
        for r in rows
        if r.get("rating") == 1 and not r.get("promoted") and r.get("route") in CERTIFIED_ROUTES
    )
    return {"positive": positive, "negative": negative, "pending_promotion": pending}


def _question_patterns(question: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 2]
    patterns = []
    if words:
        patterns.append(" ".join(words[:6]))
    if len(words) >= 2:
        patterns.append(" ".join(words[:3]))
    patterns.append(question.lower().strip()[:80])
    seen: set[str] = set()
    out: list[str] = []
    for p in patterns:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def promote_feedback(limit: int = 50) -> dict[str, Any]:
    fb_path = _feedback_path()
    promoted_qa_path = _promoted_qa_path()
    if not fb_path.exists():
        return {"promoted": 0, "skipped": 0}

    rows = json.loads(fb_path.read_text(encoding="utf-8"))
    promoted_qa = json.loads(promoted_qa_path.read_text(encoding="utf-8")) if promoted_qa_path.exists() else []

    promoted = 0
    skipped = 0
    next_id = len(promoted_qa) + 1

    for row in rows:
        if promoted >= limit:
            break
        if row.get("promoted"):
            continue
        if row.get("rating") != 1:
            continue
        if row.get("route") not in CERTIFIED_ROUTES:
            skipped += 1
            continue

        question = str(row.get("question", "")).strip()
        answer = str(row.get("answer", "")).strip()
        if not question or not answer:
            skipped += 1
            continue

        promoted_qa.append(
            {
                "id": f"learn_{next_id:04d}",
                "patterns": _question_patterns(question),
                "answer": answer,
                "source_turn_id": row.get("turn_id"),
                "route": row.get("route"),
                "confidence": 1,
            }
        )
        row["promoted"] = True
        promoted += 1
        next_id += 1

    promoted_qa_path.parent.mkdir(parents=True, exist_ok=True)
    promoted_qa_path.write_text(json.dumps(promoted_qa, indent=2), encoding="utf-8")
    fb_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return {"promoted": promoted, "skipped": skipped, "total_promoted_qa": len(promoted_qa)}
