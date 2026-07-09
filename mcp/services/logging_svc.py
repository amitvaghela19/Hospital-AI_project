from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from mcp.common import PATHS


def append_audit(role: str, action: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    path = PATHS["audit"]
    path.parent.mkdir(parents=True, exist_ok=True)
    events = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    entry = {
        "role": role,
        "action": action,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        entry.update(extra)
    events.append(entry)
    path.write_text(json.dumps(events[-500:], indent=2), encoding="utf-8")
    return entry


def read_audit(limit: int = 20) -> list[dict[str, Any]]:
    path = PATHS["audit"]
    if not path.exists():
        return []
    events = json.loads(path.read_text(encoding="utf-8"))
    return events[-limit:]


def append_pipeline_run(run_id: str, phase: str, status: str, detail: str = "") -> dict[str, Any]:
    path = PATHS["pipeline_runs"]
    path.parent.mkdir(parents=True, exist_ok=True)
    runs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    entry = {
        "run_id": run_id,
        "phase": phase,
        "status": status,
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    runs.append(entry)
    path.write_text(json.dumps(runs[-200:], indent=2), encoding="utf-8")
    return entry
