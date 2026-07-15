#!/usr/bin/env python3
"""Index rag_documents.json into Chroma collection project_knowledge."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def index_project_knowledge() -> dict:
    build = ROOT / "scripts" / "build_project_knowledge.py"
    if build.exists():
        subprocess.run([sys.executable, str(build)], check=False, cwd=str(ROOT))

    from mcp.common import CHROMA_COLLECTION, PATHS

    docs = json.loads(PATHS["rag_docs"].read_text(encoding="utf-8"))
    try:
        import chromadb

        PATHS["vectordb"].mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(PATHS["vectordb"]))
        try:
            client.delete_collection(CHROMA_COLLECTION)
        except Exception:
            pass
        col = client.get_or_create_collection(CHROMA_COLLECTION)
        ids = [str(d["id"]) for d in docs]
        texts = [str(d["text"]) for d in docs]
        
        if ids:
            col.add(ids=ids, documents=texts)
        return {"status": "ok", "indexed": len(ids), "collection": CHROMA_COLLECTION}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def main() -> int:
    result = index_project_knowledge()
    print(result)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

