"""
ui/search_view.py — Flight search page.

Mirrors CLI `main.py search`: collects sidebar inputs, invokes FlightScraper,
stores results in session_state, and renders the interactive results table.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import List

import streamlit as st

from config import (
    ASIA_DEFAULT_TRIP_DAYS,
    DEFAULT_DEPARTURE,
    DEPARTURE_AIRPORTS,
    INTER_DEFAULT_TRIP_DAYS,
    MAX_DURATION_HOURS,
    MAX_STOPS,
    is_intercontinental,
)
from database import Database, FlightRecord
from flight_scraper import FlightScraper
from taiwan_holidays import compute_leave_summary
from ui.components import (
    DestinationGroup,
    build_destination_groups,
    ensure_twd,
    parse_custom_iata,
    render_results,
    validate_dates,
)

_STATE_RESULTS = "search_results"
_STATE_META = "search_meta"
_STATE_PREFILL = "search_prefill_dates"  # (outbound, return) from holidays view


def _default_trip_days(destinations: List[str]) -> int:
    if any(is_intercontinental(d) for d in destinations):
        return INTER_DEFAULT_TRIP_DAYS
    return ASIA_DEFAULT_TRIP_DAYS


def _expand_flex(base: List[date], flex: int) -> List[date]:
    if flex <= 0:
        return sorted(set(base))
    expanded: set[date] = set()
    for d in base:
        for delta in range(-flex, flex + 1):
            expanded.add(d + timedelta(days=delta))
    return sorted(expanded)


def render() -> None:
    st.header("🔍 搜尋機票")

    groups = build_destination_groups()
    prefill_out, prefill_ret = st.session_state.get(_STATE_PREFILL, (None, None))

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("搜尋條件")

        from_airport = st.radio(
            "出發機場",
            options=DEPARTURE_AIRPORTS,
            index=DEPARTURE_AIRPORTS.index(DEFAULT_DEPARTURE),
            horizontal=True,
        )

        group_labels = [g.label for g in groups]
        default_idx = 0 if groups and "我的最愛" in groups[0].label else 0
        sel_label = st.selectbox("目的地群組", group_labels, index=default_idx)
        sel_group: DestinationGroup = groups[group_labels.index(sel_label)]

        destinations: List[str] = list(sel_group.codes)
        if sel_group.is_custom:
            raw = st.text_input(
                "輸入 IATA 代碼（逗號分隔，例如 NRT,KIX,BKK）",
                value="",
            ).upper()
            destinations, invalid = parse_custom_iata(raw)
            if invalid:
                st.warning(f"忽略無效代碼：{', '.join(invalid)}")
        else:
            st.caption(f"共 {len(destinations)} 個航點")

        st.divider()

        today = date.today()
        outbound = st.date_input(
            "出發日期",
            value=prefill_out or (today + timedelta(days=30)),
            min_value=today,
        )

        ret_mode = st.radio(
            "回程設定",
            options=["指定日期", "旅行天數"],
            horizontal=True,
        )
        return_date: date | None = None
        trip_days: int | None = None
        if ret_mode == "指定日期":
            sug_days = _default_trip_days(destinations) if destinations else ASIA_DEFAULT_TRIP_DAYS
            return_date = st.date_input(
                "回程日期",
                value=prefill_ret or (outbound + timedelta(days=sug_days - 1)),
                min_value=outbound,
            )
        else:
            sug_days = _default_trip_days(destinations) if destinations else ASIA_DEFAULT_TRIP_DAYS
            trip_days = st.number_input(
                "旅行天數", min_value=1, max_value=60, value=sug_days, step=1
            )
            return_date = outbound + timedelta(days=int(trip_days) - 1)
            st.caption(f"自動回程：{return_date}")

        flex_days = st.slider("彈性天數 (±N 天)", min_value=0, max_value=3, value=0)

        show_twd = st.checkbox("以台幣 (TWD) 顯示", value=True)

        st.divider()
        max_stops = st.number_input(
            "最多轉機次數", min_value=0, max_value=3, value=MAX_STOPS, step=1,
            help="東北亞/東南亞會強制 0（直達）",
        )
        max_duration = st.number_input(
            "最長飛行時數", min_value=4, max_value=40,
            value=MAX_DURATION_HOURS, step=1,
        )

        st.divider()
        search_clicked = st.button("🔍 搜尋", type="primary", width="stretch")

    # Clear prefill after it's consumed once.
    if prefill_out or prefill_ret:
        st.session_state[_STATE_PREFILL] = (None, None)

    # ── Main area ─────────────────────────────────────────────────────────────
    if search_clicked:
        if not destinations:
            st.error("請至少選擇一個目的地。")
            return

        err = validate_dates(outbound, return_date)
        if err:
            st.error(err)
            return

        out_dates = _expand_flex([outbound], flex_days)
        ret_dates = _expand_flex([return_date], flex_days) if return_date else []

        summary_cols = st.columns(4)
        summary_cols[0].metric("出發", from_airport)
        summary_cols[1].metric("目的地", f"{len(destinations)} 個")
        summary_cols[2].metric("日期組合", f"{len(out_dates)} × {len(ret_dates)}")
        summary_cols[3].metric("彈性", f"±{flex_days} 天")

        # Leave-summary info (matches CLI behaviour when both dates are given).
        leave = compute_leave_summary(outbound, return_date) if return_date else None
        if leave:
            st.info(
                f"📋 行程 {leave['total_days']} 天，"
                f"需請假 **{leave['leave_days']}** 天；"
                f"免假日 {leave['free_days']} 天。"
            )

        try:
            with st.status("搜尋中… 這需要一些時間（Google Flights 抓取）", expanded=True) as status:
                st.write(f"搜尋 {len(destinations)} 個航點 × {len(out_dates) * len(ret_dates)} 組日期")
                scraper = FlightScraper(
                    max_stops=int(max_stops),
                    max_duration_hours=int(max_duration),
                )
                records = scraper.search_roundtrip_many(
                    from_airport=from_airport,
                    destinations=destinations,
                    outbound_dates=out_dates,
                    return_dates=ret_dates,
                )
                status.update(label=f"完成：{len(records)} 筆", state="complete")
        except Exception as exc:  # noqa: BLE001 - surface any scraper failure to UI
            st.error(f"搜尋失敗：{exc}")
            return

        if show_twd:
            ensure_twd(records)

        if records:
            try:
                Database().bulk_insert_flights(records)
            except Exception as exc:  # noqa: BLE001
                st.warning(f"結果未存入資料庫：{exc}")

        st.session_state[_STATE_RESULTS] = records
        st.session_state[_STATE_META] = {
            "from": from_airport,
            "dests": destinations,
            "outbound": outbound.isoformat(),
            "return": return_date.isoformat() if return_date else "",
        }

    # ── Render cached results (survive tab switches) ─────────────────────────
    records: List[FlightRecord] = st.session_state.get(_STATE_RESULTS, [])
    meta = st.session_state.get(_STATE_META)
    if records:
        st.subheader("搜尋結果")
        if meta:
            dests_preview = ", ".join(meta["dests"][:4])
            if len(meta["dests"]) > 4:
                dests_preview += f" … (共 {len(meta['dests'])} 個)"
            st.caption(
                f"{meta['from']} → {dests_preview}  |  "
                f"{meta['outbound']} ⇄ {meta['return'] or '—'}"
            )
        render_results(records, csv_filename_prefix="flyaway_search")
    elif not search_clicked:
        st.caption("左側設定條件後按「搜尋」。")
