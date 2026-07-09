"""Structured system diagnostics with failure breakdown and remediation hints."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import requests

from mcp.client.pool import pool
from mcp.common import PATHS
from mcp.ollama_config import get_ollama_url
from mcp.services import http_svc, redis_svc
from streamlit_app import ROOT
from streamlit_app.artifacts import artifact_status, get_champion_pipeline, load_register
from streamlit_app.components.health_panel import rag_mode_label
from streamlit_app.runtime_config import get_integrations, get_ollama_fallback, get_ollama_primary

DiagStatus = Literal["ok", "warn", "fail", "skip"]


@dataclass
class DiagnosticCheck:
    category: str
    name: str
    status: DiagStatus
    summary: str
    reason: str
    remediation: str
    evidence: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _timed(fn) -> DiagnosticCheck:
    t0 = time.perf_counter()
    result = fn()
    result.duration_ms = int((time.perf_counter() - t0) * 1000)
    return result


def _check_path(category: str, name: str, path: Path, *, required: bool = True) -> DiagnosticCheck:
    if path.exists():
        return DiagnosticCheck(
            category, name, "ok", "Present", "Path exists on disk.", "No action required.", str(path)
        )
    status: DiagStatus = "fail" if required else "warn"
    return DiagnosticCheck(
        category,
        name,
        status,
        "Missing",
        f"Expected path not found: {path}",
        f"Create or regenerate this artifact. Run the pipeline phase that produces `{path.name}`.",
        str(path),
    )


def _run_diagnostic_checks() -> list[DiagnosticCheck]:
    checks: list[DiagnosticCheck] = []

    # --- Runtime ---
    checks.append(_check_path("Runtime", "SQLite warehouse", PATHS["warehouse"]))
    checks.append(_check_path("Runtime", "Vector DB directory", PATHS["vectordb"], required=False))

    redis_ok = redis_svc.is_available()
    checks.append(
        DiagnosticCheck(
            "Runtime",
            "Redis cache",
            "ok" if redis_ok else "warn",
            "Connected" if redis_ok else "Offline",
            "Redis is optional but improves LLM/MCP response caching."
            if not redis_ok
            else "Redis responded to ping.",
            "Start Redis (`docker compose -f docker-compose.mcp.yml up -d`) or continue without cache."
            if not redis_ok
            else "No action required.",
        )
    )

    # --- Ollama / LLM ---
    from streamlit_app.llm_provider import (
        custom_provider_configured,
        get_custom_provider,
        get_provider_mode,
    )

    provider_mode = get_provider_mode()

    if provider_mode == "custom_api" and custom_provider_configured():
        p = get_custom_provider()

        def _custom_llm_check() -> DiagnosticCheck:
            base = (p.get("base_url") or "").strip().rstrip("/")
            model = p.get("model") or ""
            path = p.get("health_path") or "/v1/models"
            headers = {}
            if p.get("api_key"):
                headers["Authorization"] = f"Bearer {p['api_key']}"
            try:
                r = requests.get(f"{base}{path}", headers=headers, timeout=15)
                if r.status_code < 400:
                    return DiagnosticCheck(
                        "LLM",
                        p.get("name") or "Custom API provider",
                        "ok",
                        "Reachable",
                        f"HTTP {r.status_code} · model `{model}`",
                        "No action required.",
                        (r.text or "")[:200],
                    )
                return DiagnosticCheck(
                    "LLM",
                    p.get("name") or "Custom API provider",
                    "fail",
                    f"HTTP {r.status_code}",
                    (r.text or "")[:300],
                    "Verify base URL, API key, and health path in the sidebar LLM panel.",
                )
            except Exception as exc:
                return DiagnosticCheck(
                    "LLM",
                    p.get("name") or "Custom API provider",
                    "fail",
                    "Unreachable",
                    str(exc),
                    "Check custom provider settings in the sidebar (session-only).",
                )

        checks.append(_timed(_custom_llm_check))
    elif provider_mode != "custom_api":
        def _ollama_check() -> DiagnosticCheck:
            health = http_svc.ollama_health()
            models = health.get("models") or []
            primary = get_ollama_primary()
            fallback = get_ollama_fallback()
            if health.get("status") != "ok":
                return DiagnosticCheck(
                    "LLM",
                    "Ollama service",
                    "fail",
                    "Unreachable",
                    health.get("error", health.get("status", "unknown")),
                    f"Start Ollama and verify `{get_ollama_url()}`. Run `ollama serve` and pull required models.",
                )
            missing = [
                m
                for m in (primary, fallback)
                if m and m not in models and f"{m.split(':')[0]}:latest" not in models
            ]
            if missing:
                return DiagnosticCheck(
                    "LLM",
                    "Ollama service",
                    "warn",
                    "Running — selected model(s) not pulled",
                    f"Ollama is up but these selections may be missing: {', '.join(missing)}",
                    f"Run `ollama pull {missing[0].split(':')[0]}` (or pick an installed model).",
                    f"Installed: {', '.join(models[:8])}",
                )
            return DiagnosticCheck(
                "LLM",
                "Ollama service",
                "ok",
                "Running",
                f"Primary `{primary}` and fallback `{fallback}` are available.",
                "No action required.",
                f"Models: {', '.join(models[:10])}",
            )

        checks.append(_timed(_ollama_check))

        def _ollama_probe() -> DiagnosticCheck:
            text, model = http_svc.llm_generate(
                "Reply with exactly: DIAG_OK",
                model=get_ollama_primary(),
                timeout_s=25,
            )
            if text and "DIAG_OK" in text.upper():
                return DiagnosticCheck(
                    "LLM",
                    "Active model probe",
                    "ok",
                    f"Responded via `{model}`",
                    "Primary model generated a valid probe response.",
                    "No action required.",
                    text[:120],
                )
            if text:
                return DiagnosticCheck(
                    "LLM",
                    "Active model probe",
                    "warn",
                    f"Responded via `{model}` (unexpected text)",
                    "Model answered but not with the expected probe token.",
                    "Try another model or increase timeout.",
                    text[:120],
                )
            return DiagnosticCheck(
                "LLM",
                "Active model probe",
                "fail",
                "No response",
                "Primary and fallback models did not return text within the timeout.",
                "Check Ollama logs, pull models, or switch primary model on this page.",
            )

        checks.append(_timed(_ollama_probe))
    else:
        checks.append(
            DiagnosticCheck(
                "LLM",
                "Custom API provider",
                "skip",
                "Not configured",
                "Custom API mode selected but base URL / model not saved.",
                "Configure your provider in the sidebar LLM panel (Clinician/Analyst).",
            )
        )

    # --- ML artifacts ---
    artifacts = artifact_status()
    for key, info in artifacts.items():
        label = key.replace("_", " ").title()
        checks.append(
            DiagnosticCheck(
                "ML artifacts",
                label,
                "ok" if info["ok"] else "fail",
                info["detail"],
                "Artifact check failed." if not info["ok"] else "Artifact available.",
                "Run Phase 3 notebook or `python scripts/train_advanced_artifacts.py`."
                if not info["ok"]
                else "No action required.",
            )
        )

    pipe, pipe_err = get_champion_pipeline()
    checks.append(
        DiagnosticCheck(
            "ML artifacts",
            "Champion inference smoke",
            "ok" if pipe is not None else "fail",
            "Pipeline loads" if pipe is not None else "Load failed",
            pipe_err or "joblib pipeline loaded successfully.",
            "Retrain champion artifacts if the pipeline file is corrupt or missing.",
        )
    )

    reg = load_register()
    checks.append(
        DiagnosticCheck(
            "ML artifacts",
            "Served champion model",
            "ok" if reg.get("champion_model") else "warn",
            reg.get("champion_model", "unknown"),
            f"Threshold={reg.get('threshold', '—')}, reference={reg.get('reference_model', '—')}",
            "Refresh `models/champion_register.json` after retraining.",
        )
    )

    # --- Vector / RAG ---
    rag_mode = rag_mode_label()
    checks.append(
        DiagnosticCheck(
            "Vector / RAG",
            "Knowledge retrieval mode",
            "ok" if rag_mode == "chroma" else "warn",
            rag_mode,
            "Semantic RAG requires a populated Chroma collection."
            if rag_mode != "chroma"
            else "Chroma semantic search is active.",
            "Use **Index Chroma neighbors** on this page if collections are empty.",
        )
    )

    # --- MCP services ---
    for mod in (
        "mcp.servers.pandas_server",
        "mcp.servers.chroma_server",
        "mcp.servers.config_server",
        "mcp.servers.logging_server",
    ):
        try:
            subprocess.run(
                [sys.executable, "-c", f"import {mod.split('.')[0]}; print('ok')"],
                capture_output=True,
                text=True,
                timeout=12,
                cwd=str(ROOT),
            )
            checks.append(
                DiagnosticCheck(
                    "MCP",
                    mod.split(".")[-1],
                    "ok",
                    "Importable",
                    "Python module loads without error.",
                    "No action required.",
                )
            )
        except Exception as exc:
            checks.append(
                DiagnosticCheck(
                    "MCP",
                    mod.split(".")[-1],
                    "fail",
                    "Import failed",
                    str(exc),
                    "Verify virtualenv and `pip install -r requirements.txt`.",
                )
            )

    # --- Integrations ---
    integrations = get_integrations()
    n8n_url = integrations.get("n8n_webhook_url", "").strip()
    if n8n_url:
        def _n8n() -> DiagnosticCheck:
            try:
                r = requests.post(
                    n8n_url,
                    json={"event": "hospital_health_ping", "source": "streamlit_diagnose"},
                    timeout=12,
                )
                if r.status_code < 400:
                    return DiagnosticCheck(
                        "Integrations",
                        "n8n webhook",
                        "ok",
                        f"HTTP {r.status_code}",
                        "Webhook accepted the diagnostic ping.",
                        "No action required.",
                        (r.text or "")[:200],
                    )
                return DiagnosticCheck(
                    "Integrations",
                    "n8n webhook",
                    "fail",
                    f"HTTP {r.status_code}",
                    r.text[:300] or "Webhook returned an error status.",
                    "Verify workflow is active and URL is correct in n8n.",
                )
            except Exception as exc:
                return DiagnosticCheck(
                    "Integrations",
                    "n8n webhook",
                    "fail",
                    "Connection failed",
                    str(exc),
                    "Check n8n URL, network, and that the workflow allows POST.",
                )

        checks.append(_timed(_n8n))
    else:
        checks.append(
            DiagnosticCheck(
                "Integrations",
                "n8n webhook",
                "skip",
                "Not configured",
                "No webhook URL saved for this session.",
                "Unlock Clinician/Analyst mode and add your n8n webhook URL below.",
            )
        )

    crew_base = integrations.get("crewai_base_url", "").strip().rstrip("/")
    crew_key = integrations.get("crewai_api_key", "").strip()
    if crew_base:
        def _crew() -> DiagnosticCheck:
            headers = {"Authorization": f"Bearer {crew_key}"} if crew_key else {}
            for path in ("/health", "/api/health", "/v1/health", ""):
                url = f"{crew_base}{path}" if path else crew_base
                try:
                    r = requests.get(url, headers=headers, timeout=12)
                    if r.status_code < 500:
                        return DiagnosticCheck(
                            "Integrations",
                            "CrewAI endpoint",
                            "ok" if r.status_code < 400 else "warn",
                            f"HTTP {r.status_code} @ {url}",
                            "Endpoint responded to health probe.",
                            "No action required." if r.status_code < 400 else "Check API key or path.",
                            (r.text or "")[:200],
                        )
                except Exception:
                    continue
            return DiagnosticCheck(
                "Integrations",
                "CrewAI endpoint",
                "fail",
                "Unreachable",
                f"Could not reach CrewAI base URL `{crew_base}`.",
                "Verify base URL, API key, and that the CrewAI service is running.",
            )

        checks.append(_timed(_crew))
    else:
        checks.append(
            DiagnosticCheck(
                "Integrations",
                "CrewAI endpoint",
                "skip",
                "Not configured",
                "No CrewAI base URL saved for this session.",
                "Add CrewAI base URL and optional API key in advanced diagnostics.",
            )
        )

    custom = integrations.get("custom_providers") or []
    for i, provider in enumerate(custom):
        name = provider.get("name") or f"Provider {i + 1}"
        base = (provider.get("base_url") or "").strip().rstrip("/")
        api_key = (provider.get("api_key") or "").strip()
        model = (provider.get("model") or "").strip()
        if not base:
            continue

        def _custom(p=provider, n=name) -> DiagnosticCheck:
            headers = {}
            if p.get("api_key"):
                headers["Authorization"] = f"Bearer {p['api_key']}"
            test_path = p.get("health_path") or "/v1/models"
            url = f"{base}{test_path}"
            try:
                r = requests.get(url, headers=headers, timeout=15)
                if r.status_code < 400:
                    return DiagnosticCheck(
                        "Integrations",
                        n,
                        "ok",
                        f"HTTP {r.status_code}",
                        f"Provider reachable. Model selection: `{model or 'default'}`.",
                        "No action required.",
                        (r.text or "")[:200],
                    )
                return DiagnosticCheck(
                    "Integrations",
                    n,
                    "warn",
                    f"HTTP {r.status_code}",
                    r.text[:300] or "Provider returned non-success.",
                    "Verify API key, base URL, and health path.",
                )
            except Exception as exc:
                return DiagnosticCheck(
                    "Integrations",
                    n,
                    "fail",
                    "Unreachable",
                    str(exc),
                    "Check URL, credentials, and firewall rules.",
                )

        checks.append(_timed(_custom))

    return checks


def run_full_diagnostics() -> list[DiagnosticCheck]:
    return _run_diagnostic_checks()


def diagnostics_summary(checks: list[DiagnosticCheck]) -> dict[str, int]:
    out = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
    for c in checks:
        out[c.status] = out.get(c.status, 0) + 1
    return out


def export_diagnostics_json(checks: list[DiagnosticCheck]) -> str:
    return json.dumps([c.to_dict() for c in checks], indent=2)
