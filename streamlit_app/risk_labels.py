"""Shared risk-band display labels for filters, charts, and drill-down."""

from __future__ import annotations

RISK_BAND_ORDER = ["Low", "Medium", "High"]


def normalize_risk_band_display(value) -> str:
    """Map raw risk_band values to Low, Medium, or High."""
    if value is None:
        return "Low"
    text = str(value).strip()
    if not text:
        return "Low"
    lower = text.casefold()
    if lower == "low":
        return "Low"
    if lower == "medium":
        return "Medium"
    if lower == "high":
        return "High"
    return text.title()


def risk_band_filter_options(raw_series) -> list[str]:
    """Sidebar/chart filter options in Low, Medium, High order."""
    if raw_series is None or len(raw_series) == 0:
        return list(RISK_BAND_ORDER)
    present = {normalize_risk_band_display(v) for v in raw_series.dropna().unique()}
    return [b for b in RISK_BAND_ORDER if b in present]


def expand_risk_band_filter(selected: list[str]) -> list[str]:
    """Map display labels to lowercase wire values used in mart_clinical_risk."""
    if not selected:
        return []
    return [normalize_risk_band_display(v).casefold() for v in selected]
