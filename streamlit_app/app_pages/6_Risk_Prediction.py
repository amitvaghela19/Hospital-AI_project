import sys

from streamlit_app import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from streamlit_app.components.predict_panel import render_predict_panel
from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.rbac import can_predict, require_page_access
from streamlit_app.page_registry import page_header_from_script
from streamlit_app.theme import inject_theme

inject_theme()
role, _ = render_sidebar()
page_header_from_script(__file__)

if not require_page_access(role, "risk_prediction"):
    st.stop()

render_predict_panel(role, can_predict(role))
