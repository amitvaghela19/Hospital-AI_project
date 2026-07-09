#!/usr/bin/env python3
"""Render 5 dark-neon Power BI reference mockups from master CSV."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EXPORTS = ROOT / "data" / "exports"
OUT_DIR = ROOT / "powerbi" / "assets" / "mockups"

W, H, DPI = 1920, 1080, 100

BG = "#0B1426"
PANEL = "#111827"
BORDER = "#00D4FF"
TEXT = "#E8F4FD"
MUTED = "#94A3B8"
BAR = "#0099FF"
ACCENT = "#FF007A"
TAB_ACTIVE = "#2DD4BF"

TABS = ["Hospital Overview", "Risk Analysis", "Patient Behavior", "Model Insights", "ML Performance"]


def load_data() -> pd.DataFrame:
    path = EXPORTS / "powerbi_dashboard_master.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    return pd.read_csv(path, low_memory=False)


def _f(df: pd.DataFrame, rt: str) -> pd.DataFrame:
    return df[df["record_type"] == rt].copy()


def _ordered_gender_chart(df: pd.DataFrame) -> pd.DataFrame:
    from streamlit_app.gender_labels import GENDER_CHART_ORDER, normalize_gender_display

    gen = _f(df, "CHART_GENDER").copy()
    if gen.empty:
        return gen
    gen["chart_category"] = gen["chart_category"].map(normalize_gender_display)
    gen["chart_rate_pct"] = pd.to_numeric(gen["chart_rate_pct"], errors="coerce")
    gen["chart_count"] = pd.to_numeric(gen.get("chart_count", 1), errors="coerce").fillna(1)
    gen["_weighted"] = gen["chart_rate_pct"] * gen["chart_count"]
    grouped = (
        gen.groupby("chart_category", as_index=False)
        .agg(_weighted=("_weighted", "sum"), chart_count=("chart_count", "sum"))
    )
    grouped["chart_rate_pct"] = grouped["_weighted"] / grouped["chart_count"].replace(0, np.nan)
    order = [c for c in GENDER_CHART_ORDER if c in grouped["chart_category"].astype(str).tolist()]
    grouped["chart_category"] = pd.Categorical(grouped["chart_category"], categories=order, ordered=True)
    return grouped.sort_values("chart_category")


def new_figure(active_tab: int) -> plt.Figure:
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=BG)
    fig.add_axes([0, 0, 1, 1]).axis("off")
    return fig


def draw_bottom_tabs(fig: plt.Figure, active: int) -> None:
    ax = fig.add_axes([0, 0, 1, 0.06])
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    w = 1 / len(TABS)
    for i, name in enumerate(TABS):
        x = i * w
        color = TAB_ACTIVE if i == active else "#64748B"
        weight = "bold" if i == active else "normal"
        ax.text(x + w / 2, 0.55, name, ha="center", va="center", fontsize=8, color=color, fontweight=weight)
        if i == active:
            ax.add_patch(Rectangle((x + 0.02, 0.05), w - 0.04, 0.04, facecolor=TAB_ACTIVE, edgecolor="none"))


def draw_sidebar(fig: plt.Figure, fields: list[tuple[str, list[str]]]) -> None:
    ax = fig.add_axes([0.015, 0.10, 0.13, 0.82])
    ax.set_facecolor(PANEL)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
        spine.set_linewidth(1.5)
    ax.set_title("Filters", fontsize=10, color=TEXT, loc="left", pad=6)
    y = 0.92
    for title, items in fields:
        ax.text(0.06, y, title, fontsize=8, color=BORDER, fontweight="bold", transform=ax.transAxes)
        y -= 0.05
        for item in items[:5]:
            ax.text(0.08, y, f"☐ {item}", fontsize=7, color=TEXT, transform=ax.transAxes)
            y -= 0.045
        y -= 0.03


def panel_ax(fig: plt.Figure, rect: list[float], title: str, hint: str = "") -> plt.Axes:
    ax = fig.add_axes(rect)
    ax.set_facecolor(PANEL)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
        spine.set_linewidth(1.5)
    ax.set_title(title, fontsize=10, color=TEXT, loc="left", pad=6)
    if hint:
        ax.text(0, 1.03, hint, transform=ax.transAxes, fontsize=6.5, color=MUTED)
    return ax


def kpi_card(fig: plt.Figure, rect: list[float], title: str, value: str, accent: bool = False) -> None:
    ax = fig.add_axes(rect)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch(
        (0.03, 0.08), 0.94, 0.84, boxstyle="round,pad=0.02,rounding_size=0.06",
        facecolor=PANEL, edgecolor=BORDER, linewidth=1.8,
    ))
    ax.text(0.5, 0.72, title.upper(), ha="center", fontsize=8, color=MUTED)
    ax.text(0.5, 0.38, value, ha="center", fontsize=18, fontweight="bold", color=ACCENT if accent else BORDER)


def bar_h(ax: plt.Axes, cats: list, vals: list, xlabel: str = "Rate %") -> None:
    y = np.arange(len(cats))
    ax.barh(y, vals, color=BAR, height=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(cats, fontsize=7, color=TEXT)
    ax.set_xlabel(xlabel, fontsize=8, color=MUTED)
    ax.tick_params(axis="x", colors=MUTED, labelsize=7)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.2, color=MUTED)


def bar_v(ax: plt.Axes, cats: list, vals: list, ylabel: str = "") -> None:
    x = np.arange(len(cats))
    ax.bar(x, vals, color=BAR, width=0.65)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, fontsize=7, color=TEXT, rotation=30, ha="right")
    ax.set_ylabel(ylabel, fontsize=8, color=MUTED)
    ax.tick_params(axis="y", colors=MUTED, labelsize=7)
    ax.grid(axis="y", alpha=0.2, color=MUTED)


def save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor=BG, bbox_inches=None, pad_inches=0)
    plt.close(fig)
    print(f"Wrote {path}")


def sidebar_enc(df: pd.DataFrame) -> list[tuple[str, list[str]]]:
    enc = _f(df, "ENCOUNTER")
    return [
        ("Age Band", sorted(enc["enc_age_band"].dropna().unique().astype(str).tolist())[:5]),
        ("Gender", sorted(enc["enc_gender"].dropna().unique().astype(str).tolist())[:3]),
        ("Diagnosis", sorted(enc["enc_diag_1"].dropna().unique().astype(str).tolist())[:5]),
    ]


def sidebar_mtx(df: pd.DataFrame) -> list[tuple[str, list[str]]]:
    mtx = _f(df, "MATRIX")
    return [
        ("Model", sorted(mtx["mtx_model"].dropna().unique().astype(str).tolist())[:6]),
        ("Horizon", sorted(mtx["mtx_horizon"].dropna().unique().astype(str).tolist())),
        ("Split", sorted(mtx["mtx_split"].dropna().unique().astype(str).tolist())[:3]),
        ("Ensemble", sorted(mtx["mtx_ensemble"].dropna().unique().astype(str).tolist())),
    ]


def page1(df: pd.DataFrame, path: Path) -> None:
    fig = new_figure(0)
    fig.text(0.5, 0.96, "Hospital Overview", ha="center", fontsize=20, fontweight="bold", color=TEXT)
    draw_sidebar(fig, sidebar_enc(df))
    enc = _f(df, "ENCOUNTER").iloc[0]
    kpis = [
        ("Total Patients", f"{int(enc['kpi_total_patients']):,}", False),
        ("Readmission Rate", enc["kpi_readmission_rate_pct"], True),
        ("Avg Length of Stay", str(enc["kpi_avg_los"]), False),
    ]
    for i, (t, v, acc) in enumerate(kpis):
        kpi_card(fig, [0.18 + i * 0.27, 0.78, 0.24, 0.14], t, v, acc)
    gender = _ordered_gender_chart(df)
    ax = panel_ax(fig, [0.18, 0.12, 0.78, 0.62], "Readmission Rate by Gender (optional summary)", "record_type = CHART_GENDER")
    bar_h(ax, gender["chart_category"].tolist(), gender["chart_rate_pct"].tolist())
    draw_bottom_tabs(fig, 0)
    save(fig, path)


def page2(df: pd.DataFrame, path: Path) -> None:
    fig = new_figure(1)
    fig.text(0.5, 0.96, "Risk Analysis", ha="center", fontsize=20, fontweight="bold", color=TEXT)
    draw_sidebar(fig, sidebar_enc(df))
    age = _f(df, "CHART_AGE").sort_values("sort_order")
    ax1 = panel_ax(fig, [0.18, 0.48, 0.40, 0.42], "Readmission by Age", "CHART_AGE")
    bar_h(ax1, age["chart_category"].tolist(), age["chart_rate_pct"].tolist())
    gen = _ordered_gender_chart(df)
    ax2 = panel_ax(fig, [0.60, 0.48, 0.38, 0.42], "Readmission by Gender", "CHART_GENDER")
    bar_h(ax2, gen["chart_category"].tolist(), gen["chart_rate_pct"].tolist())
    diag = _f(df, "CHART_DIAG")
    ax3 = panel_ax(fig, [0.18, 0.10, 0.80, 0.34], "Readmission by Diagnosis (Top 10)", "CHART_DIAG")
    bar_h(ax3, diag["chart_category"].tolist(), diag["chart_rate_pct"].tolist())
    draw_bottom_tabs(fig, 1)
    save(fig, path)


def page3(df: pd.DataFrame, path: Path) -> None:
    fig = new_figure(2)
    fig.text(0.5, 0.96, "Patient Behavior", ha="center", fontsize=20, fontweight="bold", color=TEXT)
    draw_sidebar(fig, sidebar_enc(df))
    visit = _f(df, "CHART_VISIT").sort_values("sort_order")
    ax1 = panel_ax(fig, [0.18, 0.22, 0.40, 0.68], "Visit Frequency", "CHART_VISIT")
    bar_h(ax1, visit["chart_category"].tolist(), visit["chart_rate_pct"].tolist())
    med = _f(df, "CHART_MEDICATION").sort_values("sort_order")
    ax2 = panel_ax(fig, [0.60, 0.22, 0.38, 0.68], "Medication Patterns", "CHART_MEDICATION")
    bar_h(ax2, [str(x) for x in med["chart_category"]], med["chart_rate_pct"].tolist(), "Readmit rate %")
    draw_bottom_tabs(fig, 2)
    save(fig, path)


def page4(df: pd.DataFrame, path: Path) -> None:
    fig = new_figure(3)
    fig.text(0.5, 0.96, "Model Insights", ha="center", fontsize=20, fontweight="bold", color=TEXT)
    draw_sidebar(fig, sidebar_enc(df))
    feat = _f(df, "CHART_FEATURE").sort_values("sort_order")
    ax1 = panel_ax(fig, [0.18, 0.22, 0.40, 0.68], "Feature Importance", "CHART_FEATURE (mean |SHAP|)")
    bar_h(ax1, feat["chart_category"].tolist(), feat["chart_value"].tolist(), "Importance")
    pred = _f(df, "CHART_PRED_BUCKET").sort_values("sort_order")
    ax2 = panel_ax(fig, [0.60, 0.22, 0.38, 0.68], "Prediction Distribution", "CHART_PRED_BUCKET (count)")
    bar_v(ax2, pred["chart_category"].tolist(), pred["chart_count"].tolist(), "Encounters")
    draw_bottom_tabs(fig, 3)
    save(fig, path)


def page5(df: pd.DataFrame, path: Path) -> None:
    fig = new_figure(4)
    fig.text(0.5, 0.96, "ML Performance", ha="center", fontsize=20, fontweight="bold", color=TEXT)
    draw_sidebar(fig, sidebar_mtx(df))
    enc = _f(df, "ENCOUNTER").iloc[0]
    kpis = [
        ("Champion Model", str(enc["kpi_champion_model"]), False),
        ("Champion Recall", enc["kpi_champion_recall_pct"], True),
        ("Champion ROC-AUC", enc["kpi_champion_roc_auc_pct"], False),
    ]
    for i, (t, v, acc) in enumerate(kpis):
        kpi_card(fig, [0.18 + i * 0.27, 0.78, 0.24, 0.14], t, v, acc)
    primary = _f(df, "MATRIX")
    primary = primary[primary["mtx_is_primary_protocol"] == 1].sort_values("mtx_recall_pct", ascending=False)
    ax1 = panel_ax(fig, [0.18, 0.48, 0.40, 0.26], "Recall by Model", "MATRIX + mtx_is_primary_protocol = 1")
    bar_v(ax1, primary["mtx_model"].tolist(), primary["mtx_recall_pct"].tolist(), "Recall %")
    avp = _f(df, "ACTUAL_VS_PRED").sort_values("avp_idx").iloc[::max(1, len(_f(df, "ACTUAL_VS_PRED")) // 150)]
    ax2 = panel_ax(fig, [0.60, 0.48, 0.38, 0.26], "Actual vs Predicted", "ACTUAL_VS_PRED")
    ax2.plot(avp["avp_idx"], avp["avp_actual_cum_rate"], color=BAR, linewidth=1.5, label="actual")
    ax2.plot(avp["avp_idx"], avp["avp_predicted_cum_rate"], color=BORDER, linewidth=1.5, label="predicted")
    ax2.legend(fontsize=7, facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT)
    ax2.tick_params(colors=MUTED, labelsize=7)
    ax2.grid(alpha=0.2, color=MUTED)
    exp = _f(df, "MATRIX").head(8)
    ax3 = panel_ax(fig, [0.18, 0.10, 0.80, 0.34], "Experiment Matrix (sample)", "record_type = MATRIX")
    ax3.axis("off")
    cols = ["mtx_model", "mtx_horizon", "mtx_recall_pct", "mtx_roc_auc_pct"]
    tbl = ax3.table(
        cellText=[[str(r[c]) for c in cols] for _, r in exp.iterrows()],
        colLabels=cols, loc="center", cellLoc="left",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7)
    tbl.scale(1, 1.3)
    draw_bottom_tabs(fig, 4)
    save(fig, path)


def main() -> int:
    df = load_data()
    pages = [
        (page1, OUT_DIR / "page_01_hospital_overview.png"),
        (page2, OUT_DIR / "page_02_risk_analysis.png"),
        (page3, OUT_DIR / "page_03_patient_behavior.png"),
        (page4, OUT_DIR / "page_04_model_insights.png"),
        (page5, OUT_DIR / "page_05_ml_performance.png"),
    ]
    for fn, out in pages:
        fn(df, out)
    print(f"Done — {len(pages)} mockups in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
