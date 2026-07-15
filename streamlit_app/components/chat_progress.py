"""User-facing progress labels for grounded chat chat_router."""

from __future__ import annotations

from collections.abc import Callable
import html

import streamlit as st

PROGRESS_STEPS: dict[str, str] = {
    "analyzing": "Analyzing your question...",
    "permissions": "Clinical & Security Guard",
    "certified_data": "Intent & Knowledge Routing",
    "macro_data": "Intent & Knowledge Routing",
    "tribunal": "Intent & Knowledge Routing",
    "knowledge": "Intent & Knowledge Routing",
    "formatting": "Formatting response...",
    "complete": "Complete",
    
    # Predefined mapping
    "clinical_guard": "Clinical & Security Guard",
    "config_gate": "Configuration Gate",
    "tool_router": "Intent & Knowledge Routing",
    "fairness_gate": "Fairness Audit",
    "audit": "Governance Logging",
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
    if stage.startswith("clinical_guard"): return PROGRESS_STEPS["clinical_guard"]
    if stage.startswith("config_gate"): return PROGRESS_STEPS["config_gate"]
    if stage.startswith("tool_router"): return PROGRESS_STEPS["tool_router"]
    if stage.startswith("fairness_gate"): return PROGRESS_STEPS["fairness_gate"]
    if stage.startswith("audit"): return PROGRESS_STEPS["audit"]
    return PROGRESS_STEPS["analyzing"]

CHAT_STEPS = [
    "Clinical & Security Guard",
    "Configuration Gate",
    "Intent & Knowledge Routing",
    "Fairness Audit",
    "Governance Logging",
]

def render_chat_stepper(progress_trail: list[str]) -> None:
    """Render a live pipeline stepper for grounded chat based on the progress trail."""
    import streamlit as st
    from streamlit_app.theme import COLORS

    html_lines = []
    is_complete_overall = "Complete" in progress_trail

    for step_label in CHAT_STEPS:
        if step_label in progress_trail:
            # We have hit this step. Is it the last one hit so far?
            # We want to find the index of this step in the trail to see if it's the currently running one.
            # But progress_trail might have multiple of the same. Find last index.
            # Actually, if is_complete_overall, everything is done.
            if is_complete_overall:
                status = "done"
            else:
                # Filter trail to only items in CHAT_STEPS
                filtered_trail = [x for x in progress_trail if x in CHAT_STEPS]
                if filtered_trail and filtered_trail[-1] == step_label:
                    status = "running"
                else:
                    status = "done"
        else:
            # Hasn't hit this step yet. Is it a skipped step?
            # If a later step in CHAT_STEPS has been hit, then this one was skipped!
            # e.g. we hit 'Fairness Audit', but never hit 'Configuration Gate'.
            status = "pending"
            if is_complete_overall:
                status = "skipped"
            else:
                # Find if any step *after* this one in CHAT_STEPS is in the trail
                my_idx = CHAT_STEPS.index(step_label)
                for later_step in CHAT_STEPS[my_idx+1:]:
                    if later_step in progress_trail:
                        status = "skipped"
                        break

        icon = {
            "done": "✓",
            "running": "◉",
            "pending": "○",
            "skipped": "⊘"
        }.get(status, "○")
        
        color = {
            "done": COLORS["success"],
            "running": COLORS["border"],
            "pending": COLORS["muted"],
            "skipped": COLORS["muted"]
        }.get(status, COLORS["muted"])
        
        html_lines.append(
            f'<div class="log-row" style="border-left-color:{color}">'
            f'<strong style="color: {color}">{icon} {html.escape(step_label)}</strong>'
            f'</div>'
        )
        
    st.markdown("".join(html_lines), unsafe_allow_html=True)

