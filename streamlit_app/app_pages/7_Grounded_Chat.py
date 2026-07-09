import sys

from streamlit_app import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from streamlit_app.components.chat_panel import render_chat_panel
from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.rbac import get_role_config, require_page_access
from streamlit_app.page_registry import page_header_from_script
from streamlit_app.theme import inject_theme

inject_theme()
role, _ = render_sidebar()
page_header_from_script(__file__)

if not require_page_access(role, "grounded_chat"):
    st.stop()

cfg = get_role_config(role)
st.caption(
    f"Role: **{cfg.get('label', role)}** — "
    f"IDs: {'masked' if cfg.get('ids') == 'limited' else ('allowed' if cfg.get('ids') else 'hidden')} · "
    f"SQL: {'yes' if cfg.get('can_sql') else 'no'} · "
    f"Encounter lookup: {'yes' if cfg.get('chat_encounter_detail') else 'no'} · "
    f"**Data changes: never** (read-only in all modes for security)"
)

render_chat_panel(role)
