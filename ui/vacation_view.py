"""
ui/vacation_view.py — Vacation Mode page.

Wraps vacation_windows.find_vacation_windows + FlightScraper.search_roundtrip_many,
mirroring CLI `main.py vacation`.
"""
from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from config import (
    ASIA_DESTINATIONS,
    DEFAULT_DEPARTURE,
    DEPARTURE_AIRPORTS,
    NON_ASIA_DESTINATIONS,
    VACATION_MODES,
    VACATION_TOP_DEST,
    VACATION_TOP_RESULTS,
    VACATION_TOP_WINDOWS,
)
from database import Database, FlightRecord
from flight_scraper import FlightScraper
from vacation_windows import find_vacation_windows
from ui.components import ensure_twd, render_results

_STATE_RESULTS = "vacation_results"
_STATE_META = "vacation_meta"


def render() -> None:
    st.header("🏖 假期模式")
    st.caption("根據預設假期長度搜尋最佳票價（亞洲短途 / 跨洲長假）。")

    mode_keys = list(VACATION_MODES.keys())
    mode_labels = {k: VACATION_MODES[k]["label"] for k in mode_keys}

    with st.sidebar:
        st.subheader("假期模式")
        from_airport = st.radio(
            "出發機場",
            options=DEPARTURE_AIRPORTS,
            index=DEPARTURE_AIRPORTS.index(DEFAULT_DEPARTURE),
            horizontal=True,
        )
        mode = st.radio(
            "模式",
            options=mode_keys,
            format_func=lambda k: mode_labels[k],
        )
        cfg = VACATION_MODES[mode]
        st.caption(
            f"預設 {cfg['days']} 天 · 需 {cfg['weekends']} 個完整週末 · "
            f"最多 {cfg['max_stops']} 轉 · 目的地={cfg['destinations']}"
        )
        flex = st.slider(
            "彈性天數 (覆蓋模式預設)", min_value=0, max_value=3,
            value=int(cfg.get("flex_days", 0)),
        )
        top_n = st.number_input(
            "結果顯示筆數", min_value=5, max_value=50,
            value=VACATION_TOP_RESULTS, step=5,
        )
        search_clicked = st.button("🔍 搜尋假期", type="primary", width="stretch")

    cfg = VACATION_MODES[mode]

    if search_clicked:
        try:
            windows = find_vacation_windows(
                mode=mode,
                horizon_days=cfg["horizon"],
                flex_days_override=flex,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"計算假期窗口失敗：{exc}")
            return

        if not windows:
            st.warning("找不到符合條件的旅遊窗口。")
            return

        top_windows = windows[:VACATION_TOP_WINDOWS]
        window_df = pd.DataFrame([
            {
                "出發": w.depart.isoformat(),
                "回程": w.ret.isoformat(),
                "天數": w.trip_days,
                "週末": w.weekends,
                "請假": w.leave_days,
                "包含假日": ", ".join(w.tw_holidays[:2]) or "—",
                "彈性": "是" if w.is_flex else "否",
            }
            for w in top_windows
        ])
        st.subheader(f"{cfg['label']} · 候選窗口（前 {len(top_windows)}）")
        st.dataframe(window_df, hide_index=True, width="stretch")

        destinations = (
            ASIA_DESTINATIONS[:VACATION_TOP_DEST]
            if cfg["destinations"] == "asia"
            else NON_ASIA_DESTINATIONS[:VACATION_TOP_DEST]
        )
        out_dates = [w.depart for w in top_windows]
        ret_dates = [w.ret for w in top_windows]

        st.info(
            f"將搜尋 {len(destinations)} 個目的地 × {len(top_windows)} 個窗口 "
            f"(max_stops={cfg['max_stops']})。"
        )

        try:
            with st.status("搜尋中…", expanded=True) as status:
                scraper = FlightScraper(
                    max_stops=cfg["max_stops"],
                    max_duration_hours=cfg["max_duration"],
                )
                records = scraper.search_roundtrip_many(
                    from_airport=from_airport,
                    destinations=destinations,
                    outbound_dates=out_dates,
                    return_dates=ret_dates,
                )
                status.update(label=f"完成：{len(records)} 筆", state="complete")
        except Exception as exc:  # noqa: BLE001
            st.error(f"搜尋失敗：{exc}")
            return

        ensure_twd(records)

        if records:
            try:
                Database().bulk_insert_flights(records)
            except Exception as exc:  # noqa: BLE001
                st.warning(f"結果未存入資料庫：{exc}")

        st.session_state[_STATE_RESULTS] = records[: int(top_n) * 5]
        st.session_state[_STATE_META] = {"mode": mode, "label": cfg["label"]}

    records: List[FlightRecord] = st.session_state.get(_STATE_RESULTS, [])
    meta = st.session_state.get(_STATE_META)
    if records:
        st.subheader("機票結果")
        if meta:
            st.caption(meta["label"])
        render_results(records, csv_filename_prefix=f"flyaway_vacation_{meta['mode'] if meta else 'mode'}")
    elif not search_clicked:
        st.caption("左側選擇模式後按「搜尋假期」。")
