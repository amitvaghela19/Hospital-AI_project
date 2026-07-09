from __future__ import annotations

import html

import streamlit as st

from streamlit_app.predict_pipeline import PipelineStep, PipelineResult
from streamlit_app.theme import COLORS


_STATUS_ICON = {
    "pending": "○",
    "running": "◉",
    "done": "✓",
    "skipped": "⊘",
    "failed": "✗",
}

_STATUS_CLASS = {
    "pending": "step-pending",
    "running": "step-running",
    "done": "step-done",
    "skipped": "step-skipped",
    "failed": "step-failed",
}


def render_encounter_summary(row: dict, encounter_id: str | int | None) -> None:
    eid = encounter_id or row.get("encounter_id", "—")
    gender = row.get("gender", "—")
    age = row.get("age", "—")
    los = row.get("time_in_hospital", "—")
    visits = row.get("total_visits", "—")
    meds = row.get("num_medications", row.get("active_med_count", "—"))
    st.markdown(
        f"""
        <div class="encounter-card">
            <div class="encounter-card-title">Selected encounter</div>
            <div class="encounter-grid">
                <div><span class="enc-label">ID</span><span class="enc-value">{html.escape(str(eid))}</span></div>
                <div><span class="enc-label">Gender</span><span class="enc-value">{html.escape(str(gender))}</span></div>
                <div><span class="enc-label">Age</span><span class="enc-value">{html.escape(str(age))}</span></div>
                <div><span class="enc-label">LOS</span><span class="enc-value">{html.escape(str(los))} days</span></div>
                <div><span class="enc-label">Visits</span><span class="enc-value">{html.escape(str(visits))}</span></div>
                <div><span class="enc-label">Meds</span><span class="enc-value">{html.escape(str(meds))}</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pipeline_stepper(steps: list[PipelineStep], active_only: bool = False) -> None:
    """Horizontal circular stepper with connector lines."""
    nodes = []
    for i, step in enumerate(steps):
        if active_only and step.status == "pending":
            continue
        cls = _STATUS_CLASS.get(step.status, "step-pending")
        icon = _STATUS_ICON.get(step.status, "○")
        short = step.label.split("·", 1)[-1].strip() if "·" in step.label else step.label
        nodes.append(
            f'<div class="pipeline-node {cls}">'
            f'<div class="pipeline-circle">{icon}</div>'
            f'<div class="pipeline-label">{html.escape(short)}</div>'
            f"</div>"
        )
        if i < len(steps) - 1:
            line_cls = "pipeline-line-done" if step.status == "done" else "pipeline-line"
            nodes.append(f'<div class="{line_cls}"></div>')
    st.markdown(f'<div class="pipeline-track">{"".join(nodes)}</div>', unsafe_allow_html=True)


def render_pipeline_log(steps: list[PipelineStep], expanded: bool = True) -> None:
    """Detailed step log table."""
    with st.expander("Pipeline activity log", expanded=expanded):
        for step in steps:
            icon = _STATUS_ICON.get(step.status, "○")
            color = {
                "done": COLORS["success"],
                "running": COLORS["border"],
                "failed": COLORS["danger"],
                "skipped": COLORS["muted"],
                "pending": COLORS["muted"],
            }.get(step.status, COLORS["muted"])
            dur = f" · {step.duration_ms}ms" if step.duration_ms else ""
            detail = f" — {step.detail}" if step.detail else ""
            st.markdown(
                f'<div class="log-row" style="border-left-color:{color}">'
                f"<strong>{icon} {html.escape(step.label)}</strong>"
                f'<span class="log-meta">{step.status.upper()}{dur}{html.escape(detail)}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )


def render_progress_summary(result: PipelineResult) -> None:
    done = sum(1 for s in result.steps if s.status == "done")
    skipped = sum(1 for s in result.steps if s.status == "skipped")
    failed = sum(1 for s in result.steps if s.status == "failed")
    total = len(result.steps)
    pct = int(100 * (done + skipped) / total) if total else 0
    st.progress(pct / 100.0, text=f"Pipeline {pct}% complete · {done} done · {skipped} skipped · {failed} failed")
