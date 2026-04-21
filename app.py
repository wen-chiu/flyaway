"""
app.py — Streamlit entry point for flyaway.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from ui import holidays_view, search_view, vacation_view

st.set_page_config(
    page_title="台北機票比價 Flyaway",
    page_icon="✈",
    layout="wide",
)

PAGES = {
    "🔍 搜尋機票": search_view.render,
    "🏖 假期模式": vacation_view.render,
    "📅 台灣假期": holidays_view.render,
}


def main() -> None:
    st.sidebar.title("✈ Flyaway")
    page = st.sidebar.radio("功能", list(PAGES.keys()), label_visibility="collapsed")
    st.sidebar.divider()
    PAGES[page]()
    st.sidebar.divider()
    st.sidebar.caption("Powered by fast-flights · Google Flights")


if __name__ == "__main__":
    main()
