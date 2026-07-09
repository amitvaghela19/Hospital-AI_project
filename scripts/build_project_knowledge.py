#!/usr/bin/env python3
"""Build/merge RAG document corpus from dictionaries and RBAC."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def build_docs() -> list[dict]:
    out: list[dict] = []
    existing = {d["id"]: d for d in _load_json(ROOT / "data" / "nosql" / "rag_documents.json", [])}

    feat = _load_json(ROOT / "data" / "nosql" / "feature_dictionary.json", {})
    metrics = _load_json(ROOT / "data" / "nosql" / "metric_dictionary.json", {})
    rbac = _load_json(ROOT / "data" / "nosql" / "rbac_roles.json", {})

    if isinstance(feat, dict) and feat.get("features"):
        lines = ["Certified feature dictionary:"] + [f"- {f}" for f in feat["features"]]
        out.append({"id": "feature_dictionary", "text": "\n".join(lines)})

    if isinstance(metrics, dict) and metrics:
        lines = ["Metric dictionary:"] + [f"- {k}: {v}" for k, v in metrics.items()]
        out.append({"id": "metric_dictionary", "text": "\n".join(lines)})

    if isinstance(rbac, dict) and rbac.get("roles"):
        parts = ["RBAC roles and chat capabilities:"]
        for role, cfg in rbac["roles"].items():
            caps = ", ".join(sorted(k for k, v in cfg.items() if v is True))
            parts.append(f"- {role}: {caps or 'defaults'}")
        out.append({"id": "rbac_roles", "text": "\n".join(parts)})

    out.append(
        {
            "id": "dataset_mart_readmission",
            "text": "mart_readmission certified columns include gender, race, age band, readmit_30d, time_in_hospital, encounter_id. "
            "Dimensional chat answers filter this mart for gender/race/age readmission counts.",
        }
    )

    for doc in out:
        existing[doc["id"]] = doc
    return list(existing.values())


def main() -> int:
    docs = build_docs()
    path = ROOT / "data" / "nosql" / "rag_documents.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(docs, indent=2), encoding="utf-8")
    print(f"Wrote {len(docs)} RAG documents to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

