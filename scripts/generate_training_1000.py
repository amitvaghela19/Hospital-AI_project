#!/usr/bin/env python3
"""
Generate `chatbot/scripts/training_1000.json` with exactly 1000 prompt entries.

This is not ML training; it expands the scripted "gold standard" prompt library
used by `streamlit_app/chat_router.match_script()`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "chatbot" / "scripts" / "training_1000.json"

SOURCE_FILES = [
    ROOT / "chatbot" / "scripts" / "general_faq.json",
    ROOT / "chatbot" / "scripts" / "gold_standard.json",
    ROOT / "chatbot" / "scripts" / "model_cards.json",
    ROOT / "chatbot" / "scripts" / "governance_faq.json",
    ROOT / "chatbot" / "scripts" / "clinical_disclaimer.json",
]


def _load_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _index_by_id(entries: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for e in entries:
        if isinstance(e, dict) and e.get("id"):
            out[str(e["id"])] = e
    return out


def generate_entries(target_count: int = 1000) -> list[dict]:
    general = _index_by_id(_load_entries(SOURCE_FILES[0]))
    gold = _index_by_id(_load_entries(SOURCE_FILES[1]))
    model_cards = _index_by_id(_load_entries(SOURCE_FILES[2]))
    gov = _index_by_id(_load_entries(SOURCE_FILES[3]))
    clinical = _index_by_id(_load_entries(SOURCE_FILES[4]))

    # Base mapping: answer id -> extra prompt seeds (keywords/phrases).
    # These seeds are chosen to be "substring-friendly" for match_script (case-insensitive).
    sources: list[tuple[str, list[str]]] = []

    def add_from(answer_id: str, seeds: list[str]) -> None:
        # Try all sources for the answer id.
        for idx in (general, gold, model_cards, gov, clinical):
            if answer_id in idx:
                sources.append((str(idx[answer_id]["answer"]), seeds))
                return
        raise KeyError(f"Answer id not found: {answer_id}")

    # Diabetes dataset / sources (faq1)
    add_from("faq1", ["diabetes 130-us hospitals", "diabetes dataset", "130-us hospitals dataset"])

    # How to run master notebook (faq2)
    add_from(
        "faq2",
        [
            "run master.ipynb",
            "run master notebook",
            "phases 0 through 5",
            "phases 0-5",
            "run phases 0",
            "run phases 1",
            "run phases 2",
            "run phases 3",
            "run phases 4",
            "run phases 5",
            "pipeline fails fast if data-quality gates fail",
            "dq gate",
        ],
    )

    # Power BI (faq3)
    add_from(
        "faq3",
        [
            "power bi dashboard",
            "powerbi dashboard",
            "power bi",
            "powerbi",
            "dashboard pages",
            "connects to certified csv marts",
            "powerbi/BUILD_INSTRUCTIONS.md",
        ],
    )

    # Identity / what it does (faq4)
    add_from(
        "faq4",
        [
            "who are you",
            "what are you",
            "your name",
            "what can you do",
            "what do you do",
            "hospital readmission analytics assistant",
        ],
    )

    # Getting started (faq5)
    add_from(
        "faq5",
        [
            "what should i do",
            "getting started",
            "help me start",
            "now what",
            "start on the home page",
            "index chroma neighbors",
            "explore hospital overview dashboards",
            "risk prediction",
            "grounded chat",
        ],
    )

    # Primary outcome (gs1)
    add_from(
        "gs1",
        [
            "primary outcome",
            "what are we predicting",
            "30-day readmission",
            "readmission within 30 days",
            "label <30",
            "recall is prioritized over accuracy",
        ],
    )

    # Bias / fairness (gs2)
    add_from(
        "gs2",
        [
            "bias",
            "fairness",
            "gender recall",
            "age group recall",
            "gender and age group",
            "subgroup metrics",
        ],
    )

    # Intended use (gs3)
    add_from(
        "gs3",
        [
            "intended use",
            "medical device",
            "clinical decision",
            "analytics decision-support only",
            "not a medical device",
        ],
    )

    # Champion model (mc1)
    add_from(
        "mc1",
        [
            "champion model",
            "best model",
            "which model is primary",
            "champion_register.json",
            "top factors",
            "matrix winner may be an ensemble",
        ],
    )

    # Metrics logging (mc2)
    add_from(
        "mc2",
        [
            "recall",
            "roc",
            "f1",
            "accuracy precision recall f1 roc-auc",
            "operating thresholds are tuned recall-first",
        ],
    )

    # Governance: RBAC (gv1)
    add_from(
        "gv1",
        [
            "rbac",
            "roles",
            "admin analyst clinician viewer",
            "viewers see aggregates only",
            "clinician can score risk with limited identifiers",
            "audit logs",
            "mcp audit",
        ],
    )

    # Governance: Data quality (gv2)
    add_from(
        "gv2",
        [
            "data quality",
            "dq gate",
            "completeness uniqueness validity consistency timeliness",
            "critical failures stop the pipeline",
            "phase 0 runs",
        ],
    )

    # Clinical disclaimer / refusal (cd1)
    add_from(
        "cd1",
        [
            "diagnose",
            "diagnose me",
            "prescribe",
            "what drug should",
            "treatment plan",
            "should i discharge",
        ],
    )

    # Flatten all seeds to (pattern, answer) pairs.
    pattern_answer_pairs: list[tuple[str, str]] = []
    for answer_text, seeds in sources:
        for seed in seeds:
            pattern_answer_pairs.append((seed, answer_text))

    if not pattern_answer_pairs:
        raise RuntimeError("No training patterns generated from source files.")

    # Expand to exactly `target_count` entries by cycling through the base pairs.
    entries: list[dict] = []
    for i in range(target_count):
        pat, ans = pattern_answer_pairs[i % len(pattern_answer_pairs)]
        entries.append(
            {
                "id": f"training_{i+1:04d}",
                "patterns": [pat],
                "answer": ans,
            }
        )

    return entries


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--force", action="store_true", help="Regenerate output even if it exists.")
    args = ap.parse_args()

    if OUT_PATH.exists() and not args.force:
        existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        if isinstance(existing, list) and len(existing) == args.count:
            print(f"{OUT_PATH} already exists with {args.count} entries; skipping.")
            return

    OUT_PATH.write_text(
        json.dumps(generate_entries(target_count=args.count), indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {args.count} entries to {OUT_PATH}")


if __name__ == "__main__":
    main()

