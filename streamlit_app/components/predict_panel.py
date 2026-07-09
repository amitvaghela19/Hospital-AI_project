from __future__ import annotations

import streamlit as st

from streamlit_app.artifacts import (
    get_champion_pipeline,
    get_reference_pipeline,
    load_feature_cols,
    load_register,
)
from streamlit_app.components.readonly_table import render_readonly_table
from streamlit_app.components.clinical_report import render_clinical_report
from streamlit_app.components.encounter_select import pick_encounter_row
from streamlit_app.components.pipeline_stepper import (
    render_encounter_summary,
    render_pipeline_log,
    render_pipeline_stepper,
    render_progress_summary,
)
from streamlit_app.data_loaders import load_mart
from streamlit_app.predict_pipeline import run_predict_pipeline
from streamlit_app.rbac import can_predict as rbac_can_predict
from streamlit_app.rbac_auth import validate_role

def risk_band(p: float) -> str:
    if p < 0.33:
        return "Low"
    if p < 0.66:
        return "Medium"
    return "High"


def rule_recommendations(band: str, row: dict) -> list[str]:
    recs = []
    if band == "High":
        recs += ["Follow-up check recommended", "Medication review needed"]
    elif band == "Medium":
        recs += ["Follow-up check recommended"]
    if float(row.get("total_visits", 0) or 0) >= 3:
        recs.append("Review frequent utilization pattern")
    return recs or ["Continue routine monitoring per care pathway"]


def template_explanation(band: str, top_factors: list[str], recs: list[str]) -> str:
    factors = ", ".join(top_factors[:3]) if top_factors else "documented risk factors"
    rec = recs[0] if recs else "Monitoring is recommended"
    return (
        f"This patient has a {band.lower()} risk of readmission due to {factors}. {rec}. "
        "Analytics decision-support only — not a medical device."
    )


def _render_clinical_result(pred: dict, register: dict) -> None:
    prob = pred["prob"]
    band = pred["band"]
    routed = pred["routed"]
    band_colors = {"High": "#EF4444", "Medium": "#F59E0B", "Low": "#22C55E"}

    st.markdown("### Clinical assessment")
    hero_l, hero_r = st.columns([1, 2])
    with hero_l:
        st.markdown(
            f"""
            <div class="risk-hero" style="border-color:{band_colors[band]}">
                <div class="risk-hero-label">30-day readmission risk</div>
                <div class="risk-hero-band">{band}</div>
                <div class="risk-hero-prob">{prob:.1%}</div>
                <div class="risk-hero-sub">threshold {register.get('threshold', 0.5):.3f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hero_r:
        if pred.get("score_source") == "certified_mart":
            st.caption("Certified score from mart_clinical_risk (aligned with Risk Analysis dashboards).")
            if pred.get("score_divergence"):
                st.warning(
                    f"Live pipeline re-score ({pred.get('live_prob', prob):.1%}) differs from certified "
                    f"mart ({prob:.1%}) — dashboards use the certified export."
                )
        c1, c2, c3 = st.columns(3)
        c1.metric("Primary score", f"{routed['primary_prob']:.3f}")
        c2.metric("Route", routed.get("route", "tri_only"))
        rnn = routed.get("rnn_prob")
        c3.metric("RNN score", f"{rnn:.3f}" if rnn is not None else "—")

        if pred.get("disagree"):
            st.warning("Reference RF disagrees with the served tri_ensemble — review manually.")
        if routed.get("rnn_prob") is not None:
            st.info(
                f"Uncertainty blend: Tri {routed['primary_prob']:.3f} + RNN {routed['rnn_prob']:.3f} "
                f"→ {prob:.3f}"
            )

    tab_factors, tab_recs, tab_explain, tab_advanced = st.tabs(
        ["Risk drivers", "Actions", "Explanation", "Advanced"]
    )
    with tab_factors:
        chips = "".join(f'<span class="factor-chip">{f}</span>' for f in pred["top"][:5])
        st.markdown(chips or "_No factors listed_", unsafe_allow_html=True)

    with tab_recs:
        for r in pred["recs"]:
            st.markdown(f"- {r}")

    with tab_explain:
        st.markdown(pred["text"])
        cap = f"Model: {register.get('champion_model')} · LLM: {pred['model_id']}"
        if pred.get("ollama_status") != "ok":
            cap += f" · Ollama {pred['ollama_status']} (template fallback)"
        st.caption(cap)

    with tab_advanced:
        if pred.get("score_source") == "certified_mart":
            st.markdown(
                f"**Certified mart:** {pred['band']} · {pred['prob']:.1%} "
                f"(live pipeline: {pred.get('live_prob', pred['prob']):.1%})"
            )
        if pred.get("similar_cohort"):
            st.success(pred["similar_cohort"])
        else:
            st.info("Similar cohort unavailable — index neighbors on **System Health Diagnose**.")
        if pred.get("reference_prob") is not None:
            st.write(f"Reference RF: **{pred['reference_prob']:.3f}**")
        dq_mart = load_mart("mart_dq_scorecard")
        if not dq_mart.empty:
            render_readonly_table(dq_mart.head(10), show_caption=False)


def render_predict_panel(role: str, can_predict: bool) -> None:
    role = validate_role(role)
    can_predict = rbac_can_predict(role)
    register = load_register()
    feature_cols = load_feature_cols()
    pipe, pipe_err = get_champion_pipeline()
    reference_pipe, _ = get_reference_pipeline()

    if not can_predict:
        st.error("Your role cannot run predictions.")
        st.info("Unlock **Clinician** or **Analyst** mode in the sidebar with the correct password.")
        return

    if pipe is None:
        st.error(pipe_err or "Champion pipeline unavailable.")
        st.info("Go to **System Health Diagnose** to check prerequisites.")
        return

    left, right = st.columns([1, 1.4], gap="large")

    with left:
        st.markdown("#### 1 · Select encounter")
        row = pick_encounter_row(feature_cols, role=role)
        if row is None:
            return
        st.session_state["predict_row"] = row
        render_encounter_summary(row, st.session_state.get("selected_encounter_id"))

    with right:
        st.markdown("#### 2 · Run inference pipeline")
        st.caption(
            "Eight gated steps: DQ → features → champion → RNN routing → shadow → "
            "cohort → explanation → audit. Displayed risk band uses **certified mart** "
            "when the encounter exists in mart_clinical_risk (same as dashboard pages)."
        )

        score_clicked = st.button(
            "Score risk",
            type="primary",
            use_container_width=True,
        )

        stepper_slot = st.empty()
        progress_slot = st.empty()
        log_slot = st.empty()

        if score_clicked:
            if not rbac_can_predict():
                st.error("Session is locked to Viewer. Unlock Clinician or Analyst mode to score.")
                return
            pipeline_result_holder: dict = {}

            def _on_step(steps):
                with stepper_slot.container():
                    render_pipeline_stepper(steps)
                with progress_slot.container():
                    from streamlit_app.predict_pipeline import PipelineResult

                    render_progress_summary(PipelineResult(success=False, steps=steps))
                with log_slot.container():
                    render_pipeline_log(steps, expanded=True)

            with st.spinner("Running clinical inference pipeline…"):
                pipeline_result = run_predict_pipeline(
                    row,
                    feature_cols,
                    pipe,
                    reference_pipe,
                    register,
                    role,
                    risk_band_fn=risk_band,
                    rule_recommendations_fn=rule_recommendations,
                    template_explanation_fn=template_explanation,
                    on_step_update=_on_step,
                )
            pipeline_result_holder["result"] = pipeline_result

            st.session_state["last_pipeline_steps"] = [
                {"key": s.key, "label": s.label, "status": s.status, "detail": s.detail, "duration_ms": s.duration_ms}
                for s in pipeline_result.steps
            ]

            if not pipeline_result.success:
                st.error(pipeline_result.error or "Pipeline failed.")
            else:
                pred = pipeline_result.prediction
                st.session_state["last_scored_row"] = row
                st.session_state["last_prediction"] = pred
                st.success("Pipeline complete — clinical assessment ready below.")

        elif steps_data := st.session_state.get("last_pipeline_steps"):
            from streamlit_app.predict_pipeline import PipelineStep

            steps = [PipelineStep(**s) for s in steps_data]
            with stepper_slot.container():
                render_pipeline_stepper(steps)
            with log_slot.container():
                render_pipeline_log(steps, expanded=False)

    st.divider()
    if pred := st.session_state.get("last_prediction"):
        row_for_report = st.session_state.get("last_scored_row") or st.session_state.get("predict_row", {})
        _render_clinical_result(pred, register)
        if isinstance(row_for_report, dict) and row_for_report:
            st.divider()
            render_clinical_report(row_for_report, pred, register, role=role)
