"""
Runtime MCP client pool — uses shared service layer (same logic as FastMCP servers).

IDE agents connect via stdio MCP servers; Streamlit imports this pool directly
for low latency with graceful degradation when Redis/Chroma/MQTT are offline.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.services import (
    chroma_svc,
    config_svc,
    llm_svc,
    logging_svc,
    numpy_svc,
    pandas_svc,
    redis_svc,
    sqlite_svc,
    fred_svc,
    mqtt_svc,
    notifications_svc,
    similarity_svc,
)


class MCPPool:
  """Unified tool surface for Phase 5 / Streamlit runtime."""

  def audit(self, role: str, action: str, extra: dict | None = None) -> dict:
    return logging_svc.append_audit(role, action, extra)

  def top_high_risk_encounters(self, n: int = 10) -> list[dict]:
    return pandas_svc.top_high_risk_encounters(n=n)

  def encounter_detail(self, encounter_id: int, mask_patient_nbr: bool = False) -> dict | None:
    return pandas_svc.encounter_detail(encounter_id=encounter_id, mask_patient_nbr=mask_patient_nbr)

  def patient_lookup(self, patient_nbr: str) -> dict:
    return pandas_svc.patient_lookup(patient_nbr)

  def semantic_metric(self, message: str) -> str | None:
    return pandas_svc.semantic_metric(message)

  def dimensional_metric(self, message: str) -> str | None:
    from mcp.services.dimensional_metrics import dimensional_metric

    return dimensional_metric(message)

  def append_turn(self, **kwargs) -> dict:
    from mcp.services import chat_store

    return chat_store.append_turn(**kwargs)

  def record_chat_feedback(self, **kwargs) -> dict:
    from mcp.services import feedback_svc

    return feedback_svc.record_feedback(**kwargs)

  def promote_feedback(self, limit: int = 50) -> dict:
    from mcp.services import feedback_svc

    out = feedback_svc.promote_feedback(limit=limit)
    from chatbot import promoted_qa as promoted_qa_mod

    promoted_qa_mod.reload_promoted_qa()
    return out

  def feedback_stats(self) -> dict:
    from mcp.services import feedback_svc

    return feedback_svc.feedback_stats()

  def index_project_knowledge(self) -> dict:
    from scripts.index_project_knowledge import index_project_knowledge

    return index_project_knowledge()

  def rag_answer(self, message: str) -> str | None:
    return chroma_svc.rag_query(message)

  def ollama_phrase(self, facts: dict) -> tuple[str | None, str | None]:
    return llm_svc.ollama_phrase_facts(facts)

  def ollama_format_chat(self, facts: dict) -> tuple[str | None, str | None]:
    """
    Format the final chat response using Ollama.
    """
    return llm_svc.ollama_format_chat(facts)

  def ollama_chat_answer(self, question: str, role: str, context: dict | None = None) -> tuple[str | None, str | None]:
    """
    Final fallback for unknown questions (after scripts/metrics/RAG fail).
    """
    safe_context = context or {}
    return llm_svc.ollama_chat_answer(question=question, role=role, context=safe_context)

  def ollama_generate_sql(self, question: str) -> str | None:
    return llm_svc.ollama_generate_sql(question)

  def sqlite_query(self, sql: str) -> str:
    return sqlite_svc.run_query(sql)

  def sqlite_tables(self) -> list[str]:
    return sqlite_svc.list_tables()

  def config_registry(self) -> list[dict]:
    return config_svc.load_datafile_registry()

  def champion(self) -> dict:
    return config_svc.get_champion_register()

  def feature_stats(self, columns: list[str] | None = None) -> dict:
    return numpy_svc.feature_array_stats(columns)

  def fred_series(self, series_id: str) -> dict:
    return fred_svc.fetch_series(series_id)

  def mqtt_publish(self, patient_id: str, hr: int, spo2: float) -> dict:
    return mqtt_svc.publish_vitals(patient_id, hr, spo2)

  def notify(self, title: str, message: str, level: str = "info") -> dict:
    return notifications_svc.notify(title, message, level)

  def ollama_health(self) -> dict:
    return llm_svc.ollama_health()

  def redis_available(self) -> bool:
    return redis_svc.is_available()

  def similar_cohort(self, row: dict) -> str | None:
    return similarity_svc.format_similar_cohort(row)

  def index_encounter_neighbors(self, sample_n: int = 10000) -> dict:
    import pandas as pd
    from mcp.common import PATHS
    mart = PATHS["mart_readmission"]
    if mart.exists():
      df = pd.read_csv(mart)
    else:
      df = pd.read_parquet(PATHS["gold_features"])
    return similarity_svc.index_encounters(df, sample_n=sample_n)

  def health_summary(self) -> dict[str, Any]:
    from mcp.common import PATHS

    return {
      "redis": redis_svc.is_available(),
      "ollama": llm_svc.ollama_health(),
      "warehouse": PATHS["warehouse"].exists(),
      "vectordb": PATHS["vectordb"].exists(),
      "champion": PATHS["champion_register"].exists(),
    }


pool = MCPPool()
