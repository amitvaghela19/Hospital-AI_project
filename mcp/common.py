"""Shared paths and helpers for Hospital MCP services and servers."""
from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


ROOT = project_root()

PATHS = {
    "datafile": ROOT / "datafile.txt",
    "warehouse": ROOT / "data" / "warehouse" / "hospital.db",
    "vectordb": ROOT / "data" / "vectordb",
    "mart_readmission": ROOT / "data" / "exports" / "mart_readmission.csv",
    "gold_features": ROOT / "data" / "lake" / "gold" / "model_features.parquet",
    "audit": ROOT / "data" / "nosql" / "audit_events.json",
    "pipeline_runs": ROOT / "data" / "nosql" / "pipeline_runs.json",
    "rbac": ROOT / "data" / "nosql" / "rbac_roles.json",
    "rag_docs": ROOT / "data" / "nosql" / "rag_documents.json",
    "chat_sessions": ROOT / "data" / "nosql" / "chat_sessions.json",
    "chat_feedback": ROOT / "data" / "nosql" / "chat_feedback.json",
    "learned_answers": ROOT / "data" / "nosql" / "learned_answers.json",
    "champion_register": ROOT / "models" / "champion_register.json",
    "notifications_log": ROOT / "data" / "nosql" / "mcp_notifications.json",
    "scheduler_jobs": ROOT / "data" / "nosql" / "mcp_scheduler_jobs.json",
}

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")


def get_ollama_url() -> str:
    """Dynamic Ollama base URL (secrets, env, auto-probe)."""
    from mcp.ollama_config import get_ollama_url as _resolved

    return _resolved()
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "project_knowledge")
