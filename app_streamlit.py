"""Hospital readmission analytics — Streamlit entry."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from streamlit_app.theme import inject_theme
from mcp.ollama_config import resolve_ollama_url

st.set_page_config(
    page_title="Readmission Risk Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()
resolve_ollama_url()

from streamlit_app.page_registry import NAV_PAGES

pages = [st.Page(p.path, title=p.title, icon=p.icon, default=p.default) for p in NAV_PAGES]

pg = st.navigation(pages)
pg.run()
