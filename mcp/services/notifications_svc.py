from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from mcp.common import PATHS


def notify(title: str, message: str, level: str = "info") -> dict[str, Any]:
    path = PATHS["notifications_log"]
    path.parent.mkdir(parents=True, exist_ok=True)
    events = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    entry = {
        "title": title,
        "message": message,
        "level": level,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    events.append(entry)
    path.write_text(json.dumps(events[-100:], indent=2), encoding="utf-8")
    # Optional Windows toast (best-effort)
    try:
        from win10toast import ToastNotifier

        ToastNotifier().show_toast(title, message, duration=5, threaded=True)
        entry["toast"] = "sent"
    except Exception:
        entry["toast"] = "log_only"
    return entry


def list_notifications(limit: int = 20) -> list[dict[str, Any]]:
    path = PATHS["notifications_log"]
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))[-limit:]
