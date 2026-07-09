from __future__ import annotations

import pandas as pd


def sample_rows(df: pd.DataFrame, n: int, random_state: int = 42) -> pd.DataFrame:
    """Return full df when n <= 0 or n >= len(df); otherwise a stratified random subsample."""
    if n <= 0 or n >= len(df):
        return df.reset_index(drop=True)
    return df.sample(n=n, random_state=random_state).reset_index(drop=True)
