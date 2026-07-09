from __future__ import annotations

import os
from typing import Any

from mcp.common import FRED_API_KEY

# Analyst context only — not used in champion model features.
DEFAULT_SERIES = {
    "UNRATE": "US unemployment rate",
    "CPIAUCSL": "US CPI all urban consumers",
}


def fetch_series(series_id: str, limit: int = 12) -> dict[str, Any]:
    api_key = FRED_API_KEY or os.environ.get("FRED_API_KEY", "")
    if not api_key:
        return {
            "series_id": series_id,
            "error": "FRED_API_KEY not set. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html",
            "note": "For analyst socioeconomic context only — not clinical decision input.",
        }
    try:
        import requests

        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        return {
            "series_id": series_id,
            "description": DEFAULT_SERIES.get(series_id, ""),
            "observations": [{"date": o["date"], "value": o["value"]} for o in obs],
            "note": "Analyst context only — not fed into readmission champion model.",
        }
    except Exception as e:
        return {"series_id": series_id, "error": str(e)}


def list_default_series() -> dict[str, str]:
    return dict(DEFAULT_SERIES)
