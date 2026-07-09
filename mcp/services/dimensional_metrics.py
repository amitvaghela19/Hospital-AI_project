"""Natural-language dimensional metrics from certified marts (gender, age, race)."""

from __future__ import annotations

import re

import pandas as pd

from mcp.services.pandas_svc import load_mart
from streamlit_app.gender_labels import GENDER_CHART_ORDER, normalize_gender_display


def _gender_mask(series: pd.Series, label: str) -> pd.Series:
    return series.map(normalize_gender_display).astype(str) == label


def _parse_gender_filter(msg: str) -> str | None:
    if re.search(r"\b(male|men|man\b|boys?\b)\b", msg) and not re.search(
        r"\b(female|women|woman\b|girls?\b)\b", msg
    ):
        return "Male"
    if re.search(r"\b(female|women|woman\b|girls?\b)\b", msg) and not re.search(
        r"\b(male|men|man\b|boys?\b)\b", msg
    ):
        return "Female"
    if re.search(r"\b(other|unknown|non-binary|nonbinary)\b", msg):
        return "Other"
    return None


def _parse_race_filter(msg: str, mart: pd.DataFrame) -> str | None:
    if "race" not in mart.columns:
        return None
    races = sorted({str(r).strip() for r in mart["race"].dropna().unique() if str(r).strip()})
    for race in races:
        token = race.lower()
        if len(token) >= 3 and token in msg:
            return race
    return None


def _parse_age_filter(msg: str) -> str | None:
    m = re.search(r"\b(\[\d{2}-\d{2}\)|\[\d{2}-\d{2}\)|\[\d{2}\+?\)|\[\d{2}-\d{2}\))\b", msg)
    if m:
        return m.group(1)
    m = re.search(r"\bage\s*(?:band|group|range)?\s*(\[\d{2}[^\]]*\])", msg)
    if m:
        return m.group(1)
    return None


def _wants_readmit_context(msg: str) -> bool:
    return any(x in msg for x in ("readmit", "readmission", "30-day", "30 day", "30d"))


def _wants_count(msg: str) -> bool:
    return any(x in msg for x in ("how many", "count", "number of", "total"))


def _wants_rate(msg: str) -> bool:
    return any(x in msg for x in ("rate", "percent", "%", "percentage", "proportion"))


def _format_breakdown(df: pd.DataFrame, column: str, label: str) -> str:
    if column not in df.columns or "readmit_30d" not in df.columns:
        return ""
    grouped = (
        df.groupby(column, dropna=False)["readmit_30d"]
        .agg(rate="mean", encounters="count", readmits="sum")
        .reset_index()
    )
    parts: list[str] = []
    for _, row in grouped.iterrows():
        enc = int(row["encounters"])
        readmits = int(row["readmits"])
        rate = float(row["rate"])
        parts.append(f"{row[column]}: {readmits:,} readmits / {enc:,} encounters ({rate:.1%})")
    return f"{label}: " + "; ".join(parts)


def dimensional_metric(message: str) -> str | None:
    msg = message.lower()
    mart = load_mart("mart_readmission")
    if mart.empty or "readmit_30d" not in mart.columns:
        return None

    gender_label = _parse_gender_filter(msg)
    race_value = _parse_race_filter(msg, mart)
    age_band = _parse_age_filter(msg)

    has_dimension = gender_label or race_value or age_band or any(
        x in msg for x in ("by gender", "by race", "by age", "gender", "male", "female", "race")
    )
    if not has_dimension:
        return None
    if not (_wants_readmit_context(msg) or _wants_count(msg) or _wants_rate(msg)):
        return None

    if any(x in msg for x in ("by gender", "readmission by gender", "readmit by gender")) and gender_label is None:
        work = mart.copy()
        if "gender" in work.columns:
            work["_g"] = work["gender"].map(normalize_gender_display)
            order = [g for g in GENDER_CHART_ORDER if g in set(work["_g"])]
            lines: list[str] = []
            for g in order:
                sub = work[work["_g"] == g]
                readmits = int(sub["readmit_30d"].sum())
                enc = len(sub)
                rate = float(sub["readmit_30d"].mean()) if enc else 0.0
                lines.append(f"{g}: {readmits:,} readmits / {enc:,} encounters ({rate:.1%})")
            return "30-day readmission by gender (certified mart): " + "; ".join(lines)

    if any(x in msg for x in ("by race", "readmission by race")) and race_value is None and "race" in mart.columns:
        return _format_breakdown(mart, "race", "30-day readmission by race (certified mart)")

    if any(x in msg for x in ("by age", "readmission by age")) and age_band is None and "age" in mart.columns:
        return _format_breakdown(mart, "age", "30-day readmission by age band (certified mart)")

    sub = mart
    filters: list[str] = []
    if gender_label and "gender" in sub.columns:
        sub = sub[_gender_mask(sub["gender"], gender_label)]
        filters.append(f"gender={gender_label}")
    if race_value and "race" in sub.columns:
        sub = sub[sub["race"].astype(str) == race_value]
        filters.append(f"race={race_value}")
    if age_band and "age" in sub.columns:
        sub = sub[sub["age"].astype(str) == age_band]
        filters.append(f"age={age_band}")

    if not filters:
        return None
    if sub.empty:
        return f"No certified encounters match filter ({', '.join(filters)})."

    readmits = int(sub["readmit_30d"].sum())
    enc = len(sub)
    rate = float(sub["readmit_30d"].mean())
    filter_text = ", ".join(filters)
    return (
        f"Among certified encounters ({filter_text}), {readmits:,} had a 30-day readmission "
        f"out of {enc:,} encounters ({rate:.1%})."
    )
