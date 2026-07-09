from __future__ import annotations

from pathlib import Path

import streamlit as st

# Palette aligned with powerbi mockups (scripts/render_powerbi_page_mockups.py)
COLORS = {
    "bg": "#0B1426",
    "panel": "#111827",
    "border": "#00D4FF",
    "text": "#E8F4FD",
    "muted": "#94A3B8",
    "bar": "#0099FF",
    "accent": "#FF007A",
    "tab_active": "#2DD4BF",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#EF4444",
}

_CSS_PATH = Path(__file__).resolve().parent / "theme.css"


def inject_theme() -> None:
    css = _CSS_PATH.read_text(encoding="utf-8") if _CSS_PATH.exists() else ""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def kpi_card(label: str, value: str, accent: str | None = None) -> None:
    border = accent or COLORS["border"]
    st.markdown(
        f"""
        <div class="neon-kpi" style="border-color:{border}">
            <div class="neon-kpi-label">{label}</div>
            <div class="neon-kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(ok: bool, label: str, detail: str = "") -> None:
    cls = "status-ok" if ok else "status-fail"
    icon = "✓" if ok else "✗"
    st.markdown(
        f'<div class="status-row {cls}"><strong>{icon} {label}</strong>'
        f'<span class="status-detail">{detail}</span></div>',
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "", *, icon: str = "") -> None:
    icon_html = f'<span class="page-title-icon" aria-hidden="true">{icon}</span>' if icon else ""
    subtitle_html = f'<p class="page-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="page-header-band">'
        f'<h1 class="page-title">{icon_html}<span class="page-title-text">{title}</span></h1>'
        f"{subtitle_html}"
        f"</div>",
        unsafe_allow_html=True,
    )
