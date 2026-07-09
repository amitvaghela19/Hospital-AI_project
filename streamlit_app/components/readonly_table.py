"""Static read-only tables — no interactive column add/remove/edit UI."""

from __future__ import annotations

import pandas as pd
import streamlit as st

_READONLY_CAPTION = (
    "Read-only certified data — Viewer, Clinician, and Analyst modes cannot "
    "add, update, or delete records in this application."
)


def render_readonly_table(
    data: pd.DataFrame | list | dict,
    *,
    caption: str | None = _READONLY_CAPTION,
    show_caption: bool = True,
) -> None:
    if isinstance(data, pd.DataFrame):
        table = data
    else:
        table = pd.DataFrame(data)
    st.table(table)
    if show_caption and caption:
        st.caption(caption)
