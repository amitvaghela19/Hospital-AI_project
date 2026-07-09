"""User-facing progress labels for grounded chat routing."""

from __future__ import annotations

from collections.abc import Callable

PROGRESS_STEPS: dict[str, str] = {
    "analyzing": "Analyzing your question...",
    "permissions": "Checking permissions...",
    "certified_data": "Querying certified data...",
    "macro_data": "Fetching macro data...",
    "tribunal": "Running MCP tribunal...",
    "knowledge": "Searching knowledge base...",
    "formatting": "Formatting response...",
    "complete": "Complete",
}


def progress_emit(on_progress: Callable[[str], None] | None, step_key: str) -> None:
    """Emit a friendly progress label if a callback is registered."""
    if on_progress is None:
        return
    label = PROGRESS_STEPS.get(step_key, step_key)
    on_progress(label)


def map_tribunal_stage(stage: str) -> str:
    """Map internal tribunal stage ids to user-facing progress text."""
    stage = str(stage or "").strip().lower()
    if stage.startswith("clinical_guard") or stage.startswith("config_gate"):
        return PROGRESS_STEPS["permissions"]
    if stage.startswith("tool_router:rag"):
        return PROGRESS_STEPS["knowledge"]
    if stage.startswith("tool_router:metrics") or stage.startswith("tool_router:script"):
        return PROGRESS_STEPS["knowledge"]
    if stage.startswith("tool_router:sqlite"):
        return PROGRESS_STEPS["certified_data"]
    if stage.startswith("tool_router:fred"):
        return PROGRESS_STEPS["macro_data"]
    if stage.startswith("tool_router:similarity"):
        return PROGRESS_STEPS["certified_data"]
    if stage.startswith("fairness_gate") or stage.startswith("audit"):
        return PROGRESS_STEPS["formatting"]
    if stage.startswith("tool_router"):
        return PROGRESS_STEPS["tribunal"]
    return PROGRESS_STEPS["tribunal"]
