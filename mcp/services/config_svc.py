from __future__ import annotations

import json
import os
from typing import Any

from mcp.common import PATHS, REDIS_URL, MQTT_BROKER, MQTT_PORT, FRED_API_KEY, get_ollama_url


def load_datafile_registry() -> list[dict[str, str]]:
    rows = []
    path = PATHS["datafile"]
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        rows.append({
            "role": parts[0].strip(),
            "zone": parts[1].strip(),
            "path": parts[2].strip(),
            "description": parts[3].strip(),
        })
    return rows


def get_rbac() -> dict[str, Any]:
    path = PATHS["rbac"]
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_champion_register() -> dict[str, Any]:
    path = PATHS["champion_register"]
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_env_summary() -> dict[str, str]:
    return {
        "OLLAMA_URL": get_ollama_url(),
        "REDIS_URL": REDIS_URL,
        "MQTT_BROKER": MQTT_BROKER,
        "MQTT_PORT": str(MQTT_PORT),
        "FRED_API_KEY_set": str(bool(FRED_API_KEY)),
        "DATABASE_URL": os.environ.get(
            "DATABASE_URL",
            f"sqlite:///{PATHS['warehouse'].as_posix()}",
        ),
    }
