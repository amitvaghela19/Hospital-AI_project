"""Centralized Plotly chart styling: palette, glass layout, multicolor depth, zero-rate bars."""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go

from streamlit_app.theme import COLORS

CHART_PALETTE = [
    COLORS["border"],
    COLORS["accent"],
    COLORS["tab_active"],
    COLORS["bar"],
    "#A78BFA",
    COLORS["warning"],
    COLORS["success"],
    "#F472B6",
    "#38BDF8",
    "#FB923C",
    "#4ADE80",
    "#E879F9",
]

MIN_BAR_DISPLAY_PCT = 0.25

# Minimum plot margins — top reserves space for title + Plotly modebar (reset axes).
MIN_CHART_MARGIN = dict(l=72, r=72, t=112, b=72)
DEFAULT_CHART_MARGIN = dict(MIN_CHART_MARGIN)

DONUT_LAYOUT_META = "donut_right_legend"
DONUT_RIGHT_MARGIN_R = 300

PLOTLY_CHART_CONFIG = dict(
    displayModeBar=True,
    responsive=True,
    displaylogo=False,
)

_RATE_HOVER_H = (
    "<b>%{y}</b><br>Rate: %{customdata[1]:.1f}%<br>n=%{customdata[0]:,}<extra></extra>"
)
_RATE_HOVER_V = (
    "<b>%{x}</b><br>Rate: %{customdata[1]:.1f}%<br>n=%{customdata[0]:,}<extra></extra>"
)


def palette_for(n: int) -> list[str]:
    if n <= 0:
        return list(CHART_PALETTE)
    return [CHART_PALETTE[i % len(CHART_PALETTE)] for i in range(n)]


def apply_single_trace_bar_colors(fig, n: int) -> None:
    """Multicolor bars on one trace (avoids px.bar color= trace splitting)."""
    if not fig.data or not isinstance(fig.data[0], go.Bar):
        return
    fig.data[0].marker.color = palette_for(n)


def assign_bar_customdata(fig, rows: list) -> None:
    """Assign one customdata row per bar; safe for single-trace figures."""
    if not fig.data or not rows:
        return
    if len(fig.data) == 1 and isinstance(fig.data[0], go.Bar):
        fig.data[0].customdata = rows
        return
    for i, trace in enumerate(fig.data):
        if isinstance(trace, go.Bar) and i < len(rows):
            trace.customdata = [rows[i]]


def assign_multitrace_bar_customdata(
    fig,
    plot_df: pd.DataFrame,
    *,
    x_col: str,
    value_cols: list[str],
) -> None:
    """Per-point customdata for px.bar figures split by color= (one row per bar)."""
    for trace in fig.data:
        if not isinstance(trace, go.Bar):
            continue
        xs = list(trace.x) if trace.x is not None else []
        rows = []
        for xval in xs:
            match = plot_df[plot_df[x_col].astype(str) == str(xval)]
            if match.empty:
                rows.append([None] * len(value_cols))
            else:
                rows.append([match.iloc[0][c] for c in value_cols])
        trace.customdata = rows


def apply_min_bar_display(
    df: pd.DataFrame,
    rate_col: str,
    count_col: str,
    *,
    min_pct: float = MIN_BAR_DISPLAY_PCT,
) -> pd.DataFrame:
    """Ensure count>0 / rate=0 groups have a visible bar for hover and click."""
    out = df.copy()
    rates = pd.to_numeric(out[rate_col], errors="coerce").fillna(0.0)
    counts = pd.to_numeric(out[count_col], errors="coerce").fillna(0).astype(int)
    out["display_rate"] = rates
    zero_with_count = (counts > 0) & (rates == 0)
    out.loc[zero_with_count, "display_rate"] = float(min_pct)
    out["true_rate"] = rates
    out["bar_count"] = counts
    return out


def _truncate_two_decimals(value: float) -> float:
    return math.floor(value * 100) / 100


def format_count_compact(value) -> str:
    """Bar label: 55828 -> 55.82K (truncate to two decimals, no space before suffix)."""
    try:
        n = float(value if value is not None else 0)
    except (TypeError, ValueError):
        return "0"
    sign = "-" if n < 0 else ""
    abs_n = abs(n)
    if abs_n >= 1_000_000:
        scaled = _truncate_two_decimals(abs_n / 1_000_000)
        return f"{sign}{scaled:.2f}M"
    if abs_n >= 1_000:
        scaled = _truncate_two_decimals(abs_n / 1_000)
        return f"{sign}{scaled:.2f}K"
    if abs_n == int(abs_n):
        return f"{sign}{int(abs_n)}"
    return f"{sign}{abs_n:.2f}"


def count_bar_text_labels(values) -> list[str]:
    return [format_count_compact(v) for v in values]


def apply_count_bar_trace(fig, sub: pd.DataFrame, value_col: str, *, horizontal: bool) -> None:
    """Compact K/M labels on bars; hover keeps full integer count."""
    labels = count_bar_text_labels(sub[value_col])
    if horizontal:
        hovertemplate = "<b>%{y}</b><br>Encounters: %{x:,}<extra></extra>"
    else:
        hovertemplate = "<b>Active meds: %{x}</b><br>Encounters: %{y:,}<extra></extra>"
    fig.update_traces(text=labels, texttemplate="%{text}", hovertemplate=hovertemplate)


def rate_bar_text_labels(df: pd.DataFrame, true_rate_col: str = "true_rate", count_col: str = "bar_count") -> list[str]:
    labels: list[str] = []
    for _, row in df.iterrows():
        rate = float(row.get(true_rate_col, 0) or 0)
        labels.append(f"{rate:.1f}%")
    return labels


def base_plotly_layout(**kwargs) -> dict:
    base = dict(
        paper_bgcolor="rgba(17, 24, 39, 0)",
        plot_bgcolor="rgba(17, 24, 39, 0.35)",
        font=dict(color=COLORS["text"], family="system-ui, sans-serif"),
        margin=dict(DEFAULT_CHART_MARGIN),
        hoverlabel=dict(
            bgcolor="rgba(17, 24, 39, 0.92)",
            bordercolor=COLORS["border"],
            font=dict(color=COLORS["text"], size=13),
        ),
        xaxis=dict(
            gridcolor="rgba(148, 163, 184, 0.12)",
            zerolinecolor="rgba(148, 163, 184, 0.2)",
            linecolor="rgba(0, 212, 255, 0.25)",
        ),
        yaxis=dict(
            gridcolor="rgba(148, 163, 184, 0.12)",
            zerolinecolor="rgba(148, 163, 184, 0.2)",
            linecolor="rgba(0, 212, 255, 0.25)",
        ),
    )
    base.update(kwargs)
    return base


def _bar_trace_has_labels(trace: go.Bar) -> bool:
    """Safe check when trace.text is a numpy/list array (bool(text) is ambiguous)."""
    if getattr(trace, "texttemplate", None):
        return True
    text = trace.text
    if text is None:
        return False
    if isinstance(text, str):
        return bool(text.strip())
    try:
        return len(text) > 0
    except TypeError:
        return True


def apply_full_width_chart_layout(
    fig,
    *,
    height: int = 480,
    horizontal: bool = False,
    n_categories: int | None = None,
) -> None:
    """Viewer-style full-width dashboard charts: height, margins, and axis room."""
    if horizontal:
        n = max(int(n_categories or 1), 1)
        fig.update_layout(
            height=max(height, 52 * n + 140),
            yaxis=dict(automargin=True),
        )
        _apply_minimum_margins(fig, extra=dict(l=200, r=112, b=88))
    else:
        fig.update_layout(height=height)
        if n_categories and n_categories > 6:
            fig.update_layout(xaxis=dict(tickangle=-28, automargin=True))
        _apply_minimum_margins(fig)


def _bar_point_count(trace: go.Bar) -> int:
    x_len = len(trace.x) if trace.x is not None else 0
    y_len = len(trace.y) if trace.y is not None else 0
    return max(x_len, y_len, 1)


def _enhance_bar_trace(trace: go.Bar, trace_index: int) -> None:
    n = _bar_point_count(trace)
    colors = palette_for(max(n, 1))
    if trace.marker is None:
        trace.marker = dict()
    marker = trace.marker if isinstance(trace.marker, dict) else trace.marker.to_plotly_json()
    color = marker.get("color") if isinstance(marker, dict) else getattr(trace.marker, "color", None)
    if color is None or isinstance(color, str):
        if isinstance(trace.marker, dict):
            trace.marker["color"] = colors
        else:
            trace.marker.color = colors
    line_update = dict(color="rgba(255, 255, 255, 0.28)", width=1.2)
    opacity = 0.92
    if isinstance(trace.marker, dict):
        trace.marker["line"] = line_update
        trace.marker["opacity"] = opacity
    else:
        trace.marker.line = line_update
        trace.marker.opacity = opacity


def _enhance_pie_trace(trace: go.Pie) -> None:
    if trace.marker is None:
        trace.marker = dict()
    labels = trace.labels
    n = len(labels) if labels is not None else 0
    if isinstance(trace.marker, dict):
        if not trace.marker.get("colors"):
            trace.marker["colors"] = palette_for(max(n, 1))
        trace.marker["line"] = dict(color="rgba(11, 20, 38, 0.85)", width=1.5)
    else:
        has_colors = trace.marker.colors is not None
        if not has_colors:
            trace.marker.colors = palette_for(max(n, 1))
        trace.marker.line = dict(color="rgba(11, 20, 38, 0.85)", width=1.5)
    if n:
        trace.pull = [0.02] * n


def _enhance_scatter_trace(trace) -> None:
    color = CHART_PALETTE[0]
    if trace.line is not None:
        trace.line.width = max(getattr(trace.line, "width", 2) or 2, 2.5)
        if not trace.line.color:
            trace.line.color = color
    if trace.marker is not None:
        trace.marker.size = max(getattr(trace.marker, "size", 6) or 6, 7)
        trace.marker.line = dict(color="rgba(255, 255, 255, 0.35)", width=1)


def apply_multitrace_legend_below(fig, *, title: str | None = None) -> None:
    """Legend below the plot area — avoids overlap with bars/modebar in elevated-mode charts."""
    legend = dict(
        orientation="h",
        yanchor="top",
        y=-0.18,
        x=0.5,
        xanchor="center",
        bgcolor="rgba(17, 24, 39, 0.65)",
        bordercolor="rgba(0, 212, 255, 0.25)",
        borderwidth=1,
    )
    if title:
        legend["title"] = title
    fig.update_layout(showlegend=True, legend=legend, margin=dict(b=110))


def apply_column_chart_layout(fig, *, height: int | None = None) -> None:
    """Slightly taller figures for readability when charts share a row in st.columns."""
    if height:
        fig.update_layout(height=height)
    _apply_minimum_margins(fig)


def apply_donut_right_legend_layout(fig, *, height: int = 580) -> None:
    """Large left donut + vertical legend column on the right (gold-standard diagnosis layout)."""
    fig.update_layout(
        height=height,
        showlegend=True,
        margin=dict(l=36, r=DONUT_RIGHT_MARGIN_R, t=108, b=48),
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(size=11),
            tracegroupgap=8,
            bgcolor="rgba(17, 24, 39, 0.65)",
            bordercolor="rgba(0, 212, 255, 0.25)",
            borderwidth=1,
        ),
        meta=dict(chart_theme=DONUT_LAYOUT_META),
    )
    for trace in fig.data:
        if isinstance(trace, go.Pie):
            trace.domain = dict(x=[0.0, 0.58], y=[0.02, 0.98])


def _is_donut_right_legend_layout(fig) -> bool:
    meta = fig.layout.meta
    if isinstance(meta, dict) and meta.get("chart_theme") == DONUT_LAYOUT_META:
        return True
    has_pie = any(isinstance(t, go.Pie) for t in fig.data)
    return has_pie and _margin_dict(fig)["r"] >= 260


def _margin_dict(fig) -> dict[str, int]:
    margin = fig.layout.margin
    if margin is None:
        return {k: 0 for k in ("l", "r", "t", "b")}
    raw = margin.to_plotly_json() if hasattr(margin, "to_plotly_json") else dict(margin)
    return {side: int(raw.get(side) or 0) for side in ("l", "r", "t", "b")}


def _apply_minimum_margins(fig, *, extra: dict[str, int] | None = None) -> None:
    """Pad every side to at least MIN_CHART_MARGIN (+ optional per-chart extras)."""
    mins = dict(MIN_CHART_MARGIN)
    if extra:
        for side, bump in extra.items():
            if side in mins:
                mins[side] = max(mins[side], int(bump))
    current = _margin_dict(fig)
    fig.update_layout(
        margin={side: max(current[side], mins[side]) for side in ("l", "r", "t", "b")}
    )


def _fix_outside_legend(fig) -> None:
    """Right-side legends anchored outside the plot (x >= 1) get clipped in Streamlit."""
    if _is_donut_right_legend_layout(fig):
        return
    if not fig.layout.showlegend:
        return
    leg = fig.layout.legend
    if leg is None:
        return
    x = float(leg.x if leg.x is not None else 1.02)
    xanchor = str(leg.xanchor or "left")
    if x >= 1.0 and xanchor == "left":
        fig.update_layout(
            legend=dict(
                bgcolor="rgba(17, 24, 39, 0.65)",
                bordercolor="rgba(0, 212, 255, 0.25)",
                borderwidth=1,
                x=0.98,
                xanchor="right",
                y=0.98,
                yanchor="top",
                orientation=str(leg.orientation or "v"),
            )
        )


def _suppress_redundant_legend(fig) -> None:
    """Single-trace bar charts do not need a legend (labels + tooltips are enough)."""
    if _is_donut_right_legend_layout(fig):
        return
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar)]
    if len(fig.data) == 1 and len(bar_traces) == 1 and fig.layout.showlegend is not True:
        fig.update_layout(showlegend=False)


def _position_multitrace_legend(fig) -> None:
    """Multi-trace line charts: keep legend below the plot (matches viewer-style clarity)."""
    if _is_donut_right_legend_layout(fig):
        return
    if len(fig.data) <= 1 or not fig.layout.showlegend:
        return
    leg = fig.layout.legend
    if leg is not None and leg.y is not None and float(leg.y) < 0:
        return
    has_scatter = any(t.__class__.__name__ in ("Scatter", "Scattergl") for t in fig.data)
    has_bar = any(isinstance(t, go.Bar) for t in fig.data)
    if has_scatter and not has_bar:
        apply_multitrace_legend_below(fig)


def _pad_bar_label_margins(fig) -> None:
    """Horizontal bars with end labels need extra right margin; vertical bars need top."""
    extra: dict[str, int] = {}
    for trace in fig.data:
        if not isinstance(trace, go.Bar):
            continue
        has_text = _bar_trace_has_labels(trace)
        if str(getattr(trace, "orientation", "")).lower() == "h":
            extra["r"] = max(extra.get("r", 0), 112 if has_text else 48)
            extra["l"] = max(extra.get("l", 0), 56)
        elif has_text:
            extra["t"] = max(extra.get("t", 0), 32)
    if extra:
        _apply_minimum_margins(fig, extra=extra)


def enhance_figure(fig) -> object:
    """Apply multicolor depth styling; safe to call on every figure before render."""
    layout_updates = base_plotly_layout()
    for key in ("xaxis", "yaxis"):
        if key in fig.layout and fig.layout[key]:
            existing = fig.layout[key].to_plotly_json() if hasattr(fig.layout[key], "to_plotly_json") else {}
            merged = dict(layout_updates.get(key, {}))
            merged.update({k: v for k, v in existing.items() if v is not None})
            layout_updates[key] = merged
    for k, v in layout_updates.items():
        if k not in ("xaxis", "yaxis", "legend") and getattr(fig.layout, k, None) is None:
            fig.update_layout(**{k: v})
    if fig.layout.paper_bgcolor is None or fig.layout.paper_bgcolor == COLORS["panel"]:
        fig.update_layout(
            paper_bgcolor=layout_updates["paper_bgcolor"],
            plot_bgcolor=layout_updates["plot_bgcolor"],
            hoverlabel=layout_updates["hoverlabel"],
        )

    for i, trace in enumerate(fig.data):
        if isinstance(trace, go.Bar):
            _enhance_bar_trace(trace, i)
        elif isinstance(trace, go.Pie):
            _enhance_pie_trace(trace)
        elif trace.__class__.__name__ in ("Scatter", "Scattergl"):
            _enhance_scatter_trace(trace)

    _suppress_redundant_legend(fig)
    _fix_outside_legend(fig)
    _position_multitrace_legend(fig)
    _pad_bar_label_margins(fig)
    _apply_minimum_margins(fig)
    return fig


def render_plotly_chart(fig, **kwargs):
    """Styled Plotly render — applies enhance_figure then st.plotly_chart."""
    import streamlit as st

    enhance_figure(fig)
    config = kwargs.pop("config", None) or dict(PLOTLY_CHART_CONFIG)
    return st.plotly_chart(fig, use_container_width=True, config=config, **kwargs)
