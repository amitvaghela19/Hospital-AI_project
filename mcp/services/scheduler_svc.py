from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.common import PATHS, ROOT

_jobs_path = PATHS["scheduler_jobs"]


def _load_jobs() -> list[dict[str, Any]]:
    if not _jobs_path.exists():
        return []
    return json.loads(_jobs_path.read_text(encoding="utf-8"))


def _save_jobs(jobs: list[dict[str, Any]]) -> None:
    _jobs_path.parent.mkdir(parents=True, exist_ok=True)
    _jobs_path.write_text(json.dumps(jobs[-50:], indent=2), encoding="utf-8")


def register_job(name: str, command: str, cron_hint: str = "manual") -> dict[str, Any]:
    jobs = _load_jobs()
    entry = {
        "name": name,
        "command": command,
        "cron_hint": cron_hint,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "last_run": None,
        "last_status": None,
    }
    jobs.append(entry)
    _save_jobs(jobs)
    return entry


def run_master_pipeline() -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-c",
        (
            "import nbformat; from nbclient import NotebookClient; "
            "nb=nbformat.read('master.ipynb', as_version=4); "
            "NotebookClient(nb, timeout=6000, kernel_name='hospital-dotvenv', "
            "resources={'metadata':{'path':'.'}}).execute()"
        ),
    ]
    return run_registered_command("master_pipeline", cmd)


def run_registered_command(name: str, command: list[str] | None = None) -> dict[str, Any]:
    jobs = _load_jobs()
    job = next((j for j in jobs if j["name"] == name), None)
    cmd = command or (job["command"].split() if job and isinstance(job["command"], str) else None)
    if not cmd:
        cmd = ["echo", "no command"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=7200,
            shell=isinstance(cmd, str),
        )
        status = "ok" if result.returncode == 0 else "failed"
        out = {
            "name": name,
            "status": status,
            "returncode": result.returncode,
            "stdout_tail": (result.stdout or "")[-2000:],
            "stderr_tail": (result.stderr or "")[-2000:],
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        out = {"name": name, "status": "error", "error": str(e)}
    if job:
        job["last_run"] = out.get("ts")
        job["last_status"] = out.get("status")
        _save_jobs(jobs)
    return out


def list_jobs() -> list[dict[str, Any]]:
    return _load_jobs()
