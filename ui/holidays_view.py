"""
ui/holidays_view.py — Taiwan holiday windows page.

Shows the best travel windows from taiwan_holidays.get_holiday_windows(); each
row has a "以此日期搜尋" button that prefills the search page via session_state.
"""
from __future__ import annotations

import streamlit as st

from config import INTER_TRIP_MAX_DAYS, INTER_TRIP_MIN_DAYS
from taiwan_holidays import get_holiday_windows


def render() -> None:
    st.header("📅 台灣假期窗口")
    st.caption("以「最少請假、最多出遊」原則列出最佳時間窗口。")

    col1, col2, col3 = st.columns(3)
    with col1:
        intercontinental = st.checkbox(
            "跨洲旅行 (8–18 天)",
            value=False,
            help=f"打勾則使用 {INTER_TRIP_MIN_DAYS}–{INTER_TRIP_MAX_DAYS} 天區間",
        )
    with col2:
        lookahead = st.slider(
            "未來多少天", min_value=60, max_value=540, value=365, step=30
        )
    with col3:
        top_n = st.number_input(
            "顯示筆數", min_value=5, max_value=50, value=20, step=5
        )

    if intercontinental:
        min_days, max_days = INTER_TRIP_MIN_DAYS, INTER_TRIP_MAX_DAYS
    else:
        min_days, max_days = 3, 14

    try:
        windows = get_holiday_windows(
            lookahead_days=int(lookahead),
            min_trip_days=min_days,
            max_trip_days=max_days,
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"計算假期失敗：{exc}")
        return

    if not windows:
        st.info("未找到符合條件的窗口，可調整天數或延長未來天數。")
        return

    st.subheader(f"找到 {len(windows)} 個窗口（顯示前 {min(int(top_n), len(windows))}）")

    for i, w in enumerate(windows[: int(top_n)], 1):
        holiday_tag = ", ".join(w.holidays_included[:2]) or "—"
        if len(w.holidays_included) > 2:
            holiday_tag += f" +{len(w.holidays_included) - 2}"
        with st.container(border=True):
            cols = st.columns([3, 1, 1, 1, 2, 2])
            cols[0].markdown(
                f"**#{i}**  {w.start_date.strftime('%Y-%m-%d (%a)')} "
                f"→ {w.end_date.strftime('%Y-%m-%d (%a)')}"
            )
            cols[1].metric("天數", w.total_days, label_visibility="visible")
            cols[2].metric("請假", w.leave_days)
            cols[3].metric("效率", w.efficiency)
            cols[4].caption(f"假日：{holiday_tag}")
            if cols[5].button("以此日期搜尋", key=f"pick_window_{i}"):
                st.session_state["search_prefill_dates"] = (w.start_date, w.end_date)
                st.success("已套用日期，請切換到「🔍 搜尋機票」頁。")
