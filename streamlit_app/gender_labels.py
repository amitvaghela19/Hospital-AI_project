"""Shared gender display labels for charts, filters, and Power BI exports."""

from __future__ import annotations

import pandas as pd

GENDER_CHART_ORDER = ["Male", "Female", "Other"]
# Plotly horizontal bars: first categoryarray entry is at the bottom of the y-axis.
GENDER_CHART_Y_ORDER = ["Other", "Female", "Male"]


def normalize_gender_display(value) -> str:
    """Map raw gender values to Male, Female, or Other for charts and filters."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Other"
    text = str(value).strip()
    if not text:
        return "Other"
    lower = text.casefold()
    if lower == "male":
        return "Male"
    if lower == "female":
        return "Female"
    return "Other"


def prepare_gender_readmit_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate readmission rate by display gender in Male, Female, Other order."""
    if df.empty or "gender" not in df.columns or "readmit_30d" not in df.columns:
        return pd.DataFrame(columns=["gender", "readmit_30d", "rate"])

    work = df.copy()
    work["_gender_display"] = work["gender"].map(normalize_gender_display)
    sub = (
        work.groupby("_gender_display", as_index=False)
        .agg(readmit_30d=("readmit_30d", "mean"), count=("readmit_30d", "count"))
        .rename(columns={"_gender_display": "gender"})
    )
    sub["rate"] = sub["readmit_30d"] * 100
    present = [g for g in GENDER_CHART_ORDER if g in sub["gender"].astype(str).tolist()]
    sub["gender"] = pd.Categorical(sub["gender"], categories=present, ordered=True)
    return sub.sort_values("gender").reset_index(drop=True)


def gender_filter_options(raw_series) -> list[str]:
    """Sidebar/chart filter options in Male, Female, Other order."""
    if raw_series is None or len(raw_series) == 0:
        return []
    present = {normalize_gender_display(v) for v in raw_series.dropna().unique()}
    return [g for g in GENDER_CHART_ORDER if g in present]


def expand_gender_filter(selected: list[str], raw_series) -> list[str]:
    """Map display labels (e.g. Other) back to underlying raw gender values for filtering."""
    if not selected:
        return []
    selected_display = {normalize_gender_display(v) for v in selected}
    if raw_series is None or len(raw_series) == 0:
        return list(selected_display)
    raw_values: list[str] = []
    for raw in raw_series.dropna().unique():
        if normalize_gender_display(raw) in selected_display:
            raw_values.append(str(raw))
    return raw_values
