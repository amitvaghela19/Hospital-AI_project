from __future__ import annotations

import uuid

import streamlit as st

from mcp.client.pool import pool
from streamlit_app.components.health_panel import rag_mode_label
from streamlit_app.routing import route_chat, suggested_prompts
from streamlit_app.rbac_auth import validate_role


def _process_inflight_chat(
    role: str,
    message: str,
    *,
    use_tribunal: bool,
    show_debug: bool,
) -> None:
    """Run route_chat with live status updates, then persist the assistant reply."""
    last_row = st.session_state.get("last_scored_row")
    progress_trail: list[str] = []

    with st.chat_message("assistant"):
        with st.status("Thinking...", expanded=True) as status:

            def on_progress(label: str) -> None:
                status.update(label=label)
                if label not in progress_trail:
                    progress_trail.append(label)

            turn_id = str(uuid.uuid4())
            ans, route, stages, rag_used = route_chat(
                message,
                role,
                use_tribunal=use_tribunal,
                last_scored_row=last_row if isinstance(last_row, dict) else None,
                on_progress=on_progress,
            )
            status.update(label="Complete", state="complete")

        st.markdown(ans)
        session_id = st.session_state.get("chat_session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            st.session_state.chat_session_id = session_id
        pool.append_turn(
            session_id=session_id,
            role=role,
            question=message,
            answer=ans,
            route=route,
            rag_mode=rag_used,
            stages=stages,
            turn_id=turn_id,
        )
        fb = st.feedback("thumbs", key=f"fb_{turn_id}")
        if fb == 1:
            pool.record_chat_feedback(
                turn_id=turn_id,
                rating=1,
                role=role,
                route=route,
                question=message,
                answer=ans,
            )
        elif fb == 0:
            pool.record_chat_feedback(
                turn_id=turn_id,
                rating=0,
                role=role,
                route=route,
                question=message,
                answer=ans,
            )
        if show_debug:
            cap = f"route={route}"
            if rag_used and rag_used != "n/a":
                cap += f" | rag={rag_used}"
            st.caption(cap)
            if progress_trail:
                with st.expander("Progress steps"):
                    for step in progress_trail:
                        st.markdown(f"- {step}")
            if stages:
                with st.expander("Tribunal stages"):
                    for stage in stages:
                        st.markdown(f'<div class="tribunal-stage">{stage}</div>', unsafe_allow_html=True)

    pool.audit(role, route, {"message_preview": message[:120], "turn_id": turn_id})

    st.session_state.chat_history.append(
        {
            "role": "assistant",
            "content": ans,
            "route": route,
            "stages": stages,
            "rag_mode": rag_used,
            "turn_id": turn_id,
        }
    )
    st.session_state.pop("_chat_inflight", None)
    st.rerun()


def render_chat_panel(role: str) -> None:
    role = validate_role(role)
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    col_a, col_b = st.columns([2, 1])
    with col_a:
        use_tribunal = st.checkbox("MCP Model Tribunal (multi-gate LangGraph)", value=True)
    with col_b:
        show_debug = st.checkbox("Show routing debug", value=False)

    rag_mode = rag_mode_label()
    if rag_mode == "keyword_fallback":
        st.caption("Knowledge search: keyword fallback (run **System Health Diagnose** → Index Chroma for semantic RAG).")
    else:
        st.caption("Knowledge search: semantic RAG active.")

    st.markdown("**Try asking**")
    prompt_cols = st.columns(4)
    for i, prompt in enumerate(suggested_prompts(role)):
        with prompt_cols[i % 4]:
            if st.button(prompt, key=f"suggest_{i}", use_container_width=True):
                st.session_state.pending_chat = prompt

    if st.button("Clear chat", type="secondary"):
        st.session_state.chat_history = []
        st.session_state.pop("_chat_inflight", None)
        st.rerun()

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if show_debug and msg.get("route"):
                cap = f"route={msg['route']}"
                if msg.get("rag_mode") and msg["rag_mode"] != "n/a":
                    cap += f" | rag={msg['rag_mode']}"
                st.caption(cap)
            if show_debug and msg.get("stages"):
                with st.expander("Tribunal stages"):
                    for stage in msg["stages"]:
                        st.markdown(f'<div class="tribunal-stage">{stage}</div>', unsafe_allow_html=True)

    inflight = st.session_state.get("_chat_inflight")
    if inflight:
        _process_inflight_chat(
            role,
            inflight,
            use_tribunal=use_tribunal,
            show_debug=show_debug,
        )
        return

    pending = st.session_state.pop("pending_chat", None)
    user_input = st.chat_input("Ask about metrics, pipeline, models, or dashboards…")
    message = pending or user_input

    if message:
        st.session_state.chat_history.append({"role": "user", "content": message})
        st.session_state["_chat_inflight"] = message
        st.rerun()
