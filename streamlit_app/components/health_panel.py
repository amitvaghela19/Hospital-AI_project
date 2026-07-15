from __future__ import annotations

import streamlit as st

from mcp.client.pool import pool
from streamlit_app import ROOT
from streamlit_app.chat_artifacts import artifact_status
from streamlit_app.rbac_auth import validate_role
from streamlit_app.theme import status_badge


def render_health_panel(*, show_bootstrap: bool = True, role: str | None = None) -> None:
    role = validate_role(role)
    hide_model_details = role == "viewer"
    st.subheader("System health summary")
    health = pool.health_summary()
    chat_artifacts = artifact_status()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Runtime services**")
        redis_ok = bool(health.get("redis"))
        status_badge(redis_ok, "Redis cache", "Connected" if redis_ok else "Optional — caching disabled")

        ollama = health.get("ollama", {})
        ollama_ok = ollama.get("status") == "ok"
        if hide_model_details:
            ollama_detail = "Connected" if ollama_ok else ollama.get("error", ollama.get("status", "unreachable"))
        else:
            ollama_detail = (
                f"Models: {', '.join(ollama.get('models', [])[:3]) or 'none'}"
                if ollama_ok
                else ollama.get("error", ollama.get("status", "unreachable"))
            )
        status_badge(ollama_ok, "Ollama LLM", str(ollama_detail))

        vectordb_ok = bool(health.get("vectordb"))
        status_badge(vectordb_ok, "Vector DB directory", "Present" if vectordb_ok else "Missing")

        wh_ok = bool(health.get("warehouse"))
        status_badge(wh_ok, "SQLite warehouse", "Present" if wh_ok else "Missing")

    with col2:
        st.markdown("**ML chat_artifacts**")
        for key, info in chat_artifacts.items():
            label = key.replace("_", " ").title()
            detail = info["detail"]
            if hide_model_details and key in ("champion_register", "register_serve_alignment", "shadow_tri_ensemble"):
                detail = "Hidden in Viewer mode — unlock Clinician or Analyst."
            status_badge(info["ok"], label, detail)

    st.divider()
    if show_bootstrap:
        st.markdown("**Bootstrap actions**")
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("Index Chroma neighbors", use_container_width=True):
                with st.spinner("Indexing encounters..."):
                    result = pool.index_encounter_neighbors()
                from streamlit_app.data_loaders import load_master_csv

                load_master_csv.clear()
                if result.get("status") == "ok":
                    n = result.get("indexed", 0)
                    coll = result.get("collection", "encounter_neighbors")
                    st.success(f"Indexed {n:,} encounters into `{coll}`")
                else:
                    st.error(f"Indexing failed: {result.get('error', 'unknown error')}")
        with b2:
            st.markdown("Run `notebooks/phase3_ml_experiments.ipynb` for champion training.")
        with b3:
            st.code("python scripts/train_advanced_chat_artifacts.py", language="bash")


        st.divider()
        st.markdown("**Chat knowledge & feedback**")
        stats = pool.feedback_stats() if hasattr(pool, "feedback_stats") else {"positive": 0, "negative": 0, "pending_promotion": 0}
        st.caption(
            f"Feedback: {stats.get('positive', 0)} thumbs-up, {stats.get('negative', 0)} thumbs-down, "
            f"{stats.get('pending_promotion', 0)} pending promotion"
        )
        c4, c5, c6 = st.columns(3)
        with c4:
            if st.button("Index project knowledge", use_container_width=True):
                with st.spinner("Indexing project knowledge..."):
                    result = pool.index_project_knowledge()
                if result.get("status") == "ok":
                    st.success(f"Indexed {result.get('indexed', 0)} docs into `{result.get('collection')}`")
                else:
                    st.error(result.get("error", "index failed"))
        with c5:
            if st.button("Promote thumbs-up", use_container_width=True):
                with st.spinner("Promoting feedback..."):
                    out = pool.promote_feedback(limit=50)
                st.success(f"Promoted {out.get('promoted', 0)} (skipped {out.get('skipped', 0)})")
        with c6:
            st.caption("Run scripts/promote_chat_feedback.py for CLI promotion.")

        if st.button("Run MCP healthcheck script"):
            import subprocess
            import sys

            script = ROOT / "scripts" / "mcp_healthcheck.py"
            if script.exists():
                proc = subprocess.run(
                    [sys.executable, str(script)],
                    capture_output=True,
                    text=True,
                    cwd=str(ROOT),
                )
                st.text(proc.stdout or proc.stderr)
            else:
                st.warning("mcp_healthcheck.py not found")


def rag_mode_label() -> str:
    """Whether Chroma RAG is live or keyword fallback."""
    from mcp.common import CHROMA_COLLECTION, PATHS

    try:
        import chromadb

        if not PATHS["vectordb"].exists():
            return "keyword_fallback"
        client = chromadb.PersistentClient(path=str(PATHS["vectordb"]))
        col = client.get_or_create_collection(CHROMA_COLLECTION)
        if col.count() == 0:
            return "keyword_fallback"
        return "chroma"
    except Exception:
        return "keyword_fallback"
