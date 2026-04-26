"""
ui/holidays_view.py — Taiwan holiday windows page.

職責：
  - 從 `taiwan_holidays.get_holiday_windows()` 取得推薦窗口並列出
  - 使用者點選某個窗口後，把機票搜尋委派給 `ui.holiday_search`

設計守則：
  - 本檔只做「列表呈現 + 選取」，不碰機票搜尋細節（SRP）
  - 搜尋細節 → `ui/holiday_search.py`
  - 假期計算 → `taiwan_holidays.py`
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from taiwan_holidays import (
    BRIDGE_MAX_DAYS,
    TRIP_DAYS,
    HolidayWindow,
    get_holiday_windows,
    refresh_holiday_cache,
)
from ui.holiday_search import render_search_panel

_SELECTED_KEY = "holiday_selected_window"  # (start_iso, end_iso)


def render() -> None:
    st.header("📅 台灣假期窗口")
    st.caption(
        f"每個國定假日一個 **{TRIP_DAYS} 天**推薦窗口；相鄰假日可橋接成最長 "
        f"**{BRIDGE_MAX_DAYS} 天**長連假。選定窗口後直接在下方搜尋機票，"
        "可再調整出發/回程日期與目的地。"
    )

    windows = _load_windows()
    if windows is None:
        return
    if not windows:
        st.info("未找到符合條件的窗口，可調整選項或延長未來天數。")
        return

    selected_key = st.session_state.get(_SELECTED_KEY)
    selected = _find_selected(windows, selected_key)

    # 頂端固定的「目前選取」摘要 + 快速取消，避免使用者迷路
    if selected is not None:
        _render_selected_banner(selected)

    st.subheader(f"共 {len(windows)} 個窗口")

    for i, w in enumerate(windows, 1):
        is_sel = _is_selected(w, selected_key)
        _render_window_row(i, w, selected=is_sel)
        # 行內展開：搜尋面板直接出現在被選中的窗口下方
        if is_sel:
            with st.container(border=True):
                render_search_panel(w)


# ── 控制列 + 載入 ────────────────────────────────────────────────────────────
def _load_windows() -> list[HolidayWindow] | None:
    """渲染頂端控制列並回傳窗口清單；發生例外時回傳 None。"""
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    with c1:
        lookahead = st.slider("未來多少天", 60, 540, 365, step=30)
    with c2:
        only_bridge = st.checkbox("只看橋接窗口", value=False)
    with c3:
        include_past = st.checkbox("包含已過期", value=False)
    with c4:
        if st.button("🔄 更新假日資料", help="重新抓取政府行事曆"):
            _handle_refresh()

    try:
        windows = get_holiday_windows(
            lookahead_days=int(lookahead),
            include_past=include_past,
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"計算假期失敗：{exc}")
        return None

    if only_bridge:
        windows = [w for w in windows if w.is_bridge]
    return windows


def _handle_refresh() -> None:
    try:
        updated = refresh_holiday_cache()
        if updated:
            years_str = ", ".join(str(y) for y in updated)
            st.success(f"已更新 {years_str} 年行事曆")
        else:
            st.warning("更新失敗，請檢查網路；仍會使用現有資料。")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"更新失敗：{exc}")


# ── 單列呈現 ────────────────────────────────────────────────────────────────
def _render_selected_banner(w: HolidayWindow) -> None:
    """頂端橫幅：顯示目前選取的窗口，提供「取消選取」快速跳出。"""
    with st.container(border=True):
        cols = st.columns([6, 1])
        cols[0].markdown(
            f"✅ **目前選取：** {w.start_date.strftime('%m/%d (%a)')} → "
            f"{w.end_date.strftime('%m/%d (%a)')}　·　共 {w.total_days} 天　·　"
            f"請假 {w.leave_days} 天　·　"
            + ("🌉 橋接長假" if w.is_bridge else f"🗓 標準 {TRIP_DAYS} 天")
        )
        if cols[1].button("✖ 取消選取", key="hw_clear_sel", width="stretch"):
            st.session_state.pop(_SELECTED_KEY, None)
            st.rerun()


def _render_window_row(index: int, w: HolidayWindow, selected: bool) -> None:
    holiday_tag = ", ".join(w.holidays_included[:3]) or "—"
    if len(w.holidays_included) > 3:
        holiday_tag += f" +{len(w.holidays_included) - 3}"

    leave_tag = (
        ", ".join(d.strftime("%m/%d(%a)") for d in w.leave_dates)
        if w.leave_dates else "不需請假"
    )

    countdown = _countdown_label(w.start_date)
    badge     = "🌉 **橋接長假**" if w.is_bridge else f"🗓 標準 {TRIP_DAYS} 天"

    with st.container(border=True):
        head = st.columns([4, 1])
        head[0].markdown(
            f"**#{index}**  {w.start_date.strftime('%Y-%m-%d (%a)')} "
            f"→ {w.end_date.strftime('%Y-%m-%d (%a)')}  {badge}"
            + ("  · ✅ **已選取**" if selected else "")
        )
        head[1].caption(countdown)

        body = st.columns([1, 1, 1, 4, 2])
        body[0].metric("天數", w.total_days)
        body[1].metric("請假", w.leave_days)
        body[2].metric("效率", w.efficiency)
        body[3].markdown(
            f"**包含假日：** {holiday_tag}<br>**需請假：** {leave_tag}",
            unsafe_allow_html=True,
        )
        if body[4].button(
            "選此窗口搜尋機票" if not selected else "重新選擇此窗口",
            key=f"hw_pick_{index}_{w.start_date}",
            width="stretch",
        ):
            st.session_state[_SELECTED_KEY] = _key_of(w)
            st.rerun()


# ── 小工具 ───────────────────────────────────────────────────────────────────
def _key_of(w: HolidayWindow) -> tuple[str, str]:
    return (w.start_date.isoformat(), w.end_date.isoformat())


def _is_selected(w: HolidayWindow, selected_key) -> bool:
    return selected_key is not None and _key_of(w) == tuple(selected_key)


def _find_selected(
    windows: list[HolidayWindow], selected_key,
) -> HolidayWindow | None:
    if selected_key is None:
        return None
    for w in windows:
        if _key_of(w) == tuple(selected_key):
            return w
    return None


def _countdown_label(start: date) -> str:
    days_away = (start - date.today()).days
    if days_away == 0:
        return "今日啟程"
    if days_away < 0:
        return f"已開始 {-days_away} 天"
    return f"還有 {days_away} 天"
