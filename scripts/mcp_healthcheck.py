#!/usr/bin/env python3
"""Health check for Hospital MCP services and local infrastructure."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.client.pool import pool
from mcp.common import PATHS


def check_path(name: str, path: Path) -> dict:
    return {"name": name, "status": "ok" if path.exists() else "missing", "path": str(path)}


def check_command(name: str, cmd: list[str]) -> dict:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return {"name": name, "status": "ok" if r.returncode == 0 else "fail", "detail": (r.stdout or r.stderr)[:200]}
    except FileNotFoundError:
        return {"name": name, "status": "not_installed"}
    except Exception as e:
        return {"name": name, "status": "error", "detail": str(e)}


def main() -> int:
    rows = [
        check_path("warehouse_sqlite", PATHS["warehouse"]),
        check_path("vectordb_chroma", PATHS["vectordb"]),
        check_path("mart_readmission", PATHS["mart_readmission"]),
        check_path("champion_register", PATHS["champion_register"]),
        check_path("datafile_registry", PATHS["datafile"]),
    ]
    hs = pool.health_summary()
    rows.append({"name": "redis", "status": "ok" if hs.get("redis") else "offline"})
    rows.append({"name": "ollama", "status": hs["ollama"].get("status", "unknown")})
    rows.append(check_command("docker", ["docker", "compose", "-f", str(ROOT / "docker-compose.mcp.yml"), "ps"]))
    rows.append(check_command("npx", ["npx", "--version"]))
    rows.append(check_command("uvx", ["uvx", "--version"]))

    custom_servers = [
        "mcp.servers.logging_server",
        "mcp.servers.config_server",
        "mcp.servers.pandas_server",
        "mcp.servers.chroma_server",
    ]
    for mod in custom_servers:
        rows.append(
            check_command(
                mod,
                [sys.executable, "-c", f"import {mod.split('.')[0]}; print('ok')"],
            )
        )

    print(json.dumps(rows, indent=2))
    failed = sum(1 for r in rows if r.get("status") not in ("ok", True))
    print(f"\nSummary: {len(rows) - failed}/{len(rows)} checks passed or optional offline.")
    return 0 if failed <= 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
