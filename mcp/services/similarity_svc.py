from __future__ import annotations

import os
from typing import Any

import pandas as pd

from mcp.common import PATHS

NEIGHBOR_COLLECTION = os.environ.get("CHROMA_NEIGHBOR_COLLECTION", "encounter_neighbors")
NEIGHBORS_K = int(os.environ.get("CHROMA_NEIGHBORS_K", "5"))


def _encounter_text(row: dict | pd.Series) -> str:
    if isinstance(row, pd.Series):
        row = row.to_dict()
    parts = [
        f"los={row.get('time_in_hospital', row.get('static_los', ''))}",
        f"visits={row.get('total_visits', row.get('static_visits', ''))}",
        f"meds={row.get('num_medications', row.get('active_med_count', row.get('static_meds', '')))}",
        f"gender={row.get('gender', '')}",
        f"age={row.get('age', '')}",
        f"inpatient={row.get('number_inpatient', '')}",
    ]
    return " | ".join(str(p) for p in parts)


def index_encounters(df: pd.DataFrame, sample_n: int = 10000) -> dict[str, Any]:
    try:
        import chromadb

        if len(df) > sample_n:
            df = df.sample(n=sample_n, random_state=42)
        client = chromadb.PersistentClient(path=str(PATHS["vectordb"]))
        try:
            client.delete_collection(NEIGHBOR_COLLECTION)
        except Exception:
            pass
        col = client.create_collection(NEIGHBOR_COLLECTION)
        ids = []
        docs = []
        metas = []
        for i, row in df.iterrows():
            eid = str(row.get("encounter_id", i))
            ids.append(f"enc_{eid}")
            docs.append(_encounter_text(row))
            metas.append({
                "readmit_30d": float(row.get("readmit_30d", 0) or 0),
                "encounter_id": eid,
            })
        batch_size = 500
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            col.add(ids=ids[start:end], documents=docs[start:end], metadatas=metas[start:end])
        return {"status": "ok", "indexed": len(ids), "collection": NEIGHBOR_COLLECTION}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def similar_cohort_stats(row: dict, k: int | None = None) -> dict[str, Any] | None:
    k = k or NEIGHBORS_K
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(PATHS["vectordb"]))
        col = client.get_or_create_collection(NEIGHBOR_COLLECTION)
        if col.count() == 0:
            return None
        query = _encounter_text(row)
        res = col.query(query_texts=[query], n_results=min(k, col.count()))
        metas = res.get("metadatas", [[]])[0]
        if not metas:
            return None
        rates = [float(m.get("readmit_30d", 0)) for m in metas]
        return {
            "neighbor_count": len(rates),
            "readmission_rate": sum(rates) / len(rates),
            "neighbor_ids": [m.get("encounter_id") for m in metas],
        }
    except Exception:
        return None


def format_similar_cohort(row: dict) -> str | None:
    stats = similar_cohort_stats(row)
    if not stats:
        return None
    return (
        f"Similar cohort (n={stats['neighbor_count']}): "
        f"30-day readmission rate = {stats['readmission_rate']:.1%}."
    )
