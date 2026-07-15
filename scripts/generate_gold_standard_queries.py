#!/usr/bin/env python3
"""
Generate a diverse dataset of 10,000 synthetic gold-standard questions
for ingestion into ChromaDB (RAG) to serve as intent routers.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "chatbot" / "training_data"
OUT_PATH = OUT_DIR / "10k_synthetic_queries.json"


def generate_queries(target_count: int = 10000) -> list[dict]:
    # Base templates for generating questions
    sql_templates = [
        "How many {patients} are {gender}, {risk}, and have {los} and {visits}?",
        "Count the number of {patients} where gender is {gender} and risk is {risk}.",
        "What is the average {metric} for {gender} {patients} with {risk}?",
        "Can you show me encounters where patient is {gender} and {risk}?",
        "Find all {patients} who are {risk} and {gender}.",
    ]
    
    rag_templates = [
        "What is the meaning of {concept}?",
        "How do I use the {feature}?",
        "Explain the {concept} pipeline.",
        "Tell me about {concept} and {feature}.",
        "Where can I find information on {concept}?",
    ]
    
    # Vocabulary
    vocab = {
        "patients": ["patients", "encounters", "records", "admissions", "cases"],
        "gender": ["male", "female", "men", "women"],
        "risk": ["high risk", "low risk", "medium risk", "elevated risk"],
        "los": ["length of stay > 5", "stay longer than 3 days", "LOS > 7 days"],
        "visits": ["more than 3 visits", "frequent visitors", "total visits > 2"],
        "metric": ["readmission rate", "length of stay", "age", "number of procedures"],
        "concept": ["data quality gate", "shadow model", "champion register", "RBAC", "ChromaDB", "fairness audit"],
        "feature": ["sidebar unlock", "grounded chat", "risk prediction tab", "model insights"],
    }

    entries = []
    
    for i in range(target_count):
        category = random.choice(["sql", "rag"])
        if category == "sql":
            template = random.choice(sql_templates)
            q = template.format(
                patients=random.choice(vocab["patients"]),
                gender=random.choice(vocab["gender"]),
                risk=random.choice(vocab["risk"]),
                los=random.choice(vocab["los"]),
                visits=random.choice(vocab["visits"]),
                metric=random.choice(vocab["metric"]),
            )
            ans = "This query requires an Analyst role. Please use the sidebar to unlock Analyst access and I will compile the SQL for you."
            route = "sql_intent"
        else:
            template = random.choice(rag_templates)
            q = template.format(
                concept=random.choice(vocab["concept"]),
                feature=random.choice(vocab["feature"]),
            )
            ans = "You can find more information about this in the project documentation and master reports."
            route = "rag_intent"
            
        entries.append({
            "id": f"syn_{i+1:05d}",
            "question": q,
            "answer": ans,
            "category": route
        })

    return entries


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=10000)
    ap.add_argument("--force", action="store_true", help="Regenerate output even if it exists.")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUT_PATH.exists() and not args.force:
        existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        if isinstance(existing, list) and len(existing) == args.count:
            print(f"{OUT_PATH} already exists with {args.count} entries; skipping.")
            return

    entries = generate_queries(target_count=args.count)
    OUT_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print(f"Wrote {args.count} synthetic queries to {OUT_PATH}")


if __name__ == "__main__":
    main()
