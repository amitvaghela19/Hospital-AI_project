#!/usr/bin/env python3
"""Index encounter neighbors in Chroma for similarity search."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.services.similarity_svc import index_encounters


def main():
    mart = ROOT / "data" / "exports" / "mart_readmission.csv"
    if not mart.exists():
        feat = ROOT / "data" / "lake" / "gold" / "model_features.parquet"
        df = pd.read_parquet(feat)
    else:
        df = pd.read_csv(mart)
    result = index_encounters(df, sample_n=10000)
    print(result)


if __name__ == "__main__":
    main()
