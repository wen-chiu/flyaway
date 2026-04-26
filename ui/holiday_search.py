"""
ui/holiday_search.py — 假期窗口機票搜尋面板

Clean-architecture notes:
  - 此模組只負責「針對一個假期窗口跑機票搜尋」的互動流程。
  - 不包含如何尋找假期窗口（那是 `taiwan_holidays.py` 的職責）。
  - 不包含列表呈現（那是 `ui/holidays_view.py` 的職責）。
  - 真正抓票的實作在 `flight_scraper.FlightScraper`；儲存在 `database.Database`。

對外只暴露：
  - `render_search_panel(window)` — 給 holidays_view 呼叫。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

import streamlit as st

from config import (
    DEFAULT_DEPARTURE,
    DEPARTURE_AIRPORTS,
    MAX_DURATION_HOURS,
    MAX_STOPS,
    WORLD_DESTINATIONS,
)
from database import Database, FlightRecord
from flight_scraper import FlightScraper
from taiwan_holidays import HolidayWindow
from ui.components import ensure_twd, parse_custom_iata, render_results


# ── 區域選項：假期窗口預設只考慮跨洲長途目的地 ──────────────────────────────
@dataclass(frozen=True)
class _RegionOption:
    key:     str   # WORLD_DESTINATIONS 的 region key
    label:   str   # UI 顯示名稱
    default: bool  # 是否預設勾選


_REGION_OPTIONS: tuple[_RegionOption, ...] = (
    _RegionOption("Europe",    "🇪🇺 歐洲",       True),
    _RegionOption("Oceania",   "🇦🇺 大洋洲",     True),
    _RegionOption("N America", "🇺🇸 北美",       False),
    _RegionOption("Japan",     "🇯🇵 日本",       False),
    _RegionOption("Korea",     "🇰🇷 韓國",       False),
    _RegionOption("SE Asia",   "🌴 東南亞",       False),
)


# ── 對外入口 ────────────────────────────────────────────────────────────────
def render_search_panel(window: HolidayWindow) -> None:
    """渲染針對單一假期窗口的機票搜尋區塊（表單 + 結果）。"""
    state = _SearchState.for_window(window)

    st.markdown(f"### ✈ 搜尋此窗口機票：{window.label}")

    # 表單收進 expander：第一次使用展開填參數；有結果後預設收起，焦點留給結果
    has_cached = bool(state.cached()[0])
    with st.expander("🔧 搜尋條件", expanded=not has_cached):
        params = _render_form(window, state)

    if params is None:
        _render_cached_results(state)
        return

    records = _execute_search(params)
    state.store_results(records, params)
    _render_cached_results(state)


# ── 內部：session state 封裝 ────────────────────────────────────────────────
@dataclass
class _SearchState:
    """把 st.session_state 的 key 格式化集中管理，避免散落字串。"""
    window_key: str

    @classmethod
    def for_window(cls, w: HolidayWindow) -> "_SearchState":
        return cls(window_key=f"hw_{w.start_date.isoformat()}_{w.end_date.isoformat()}")

    @property
    def _results_key(self) -> str: return f"{self.window_key}_results"
    @property
    def _meta_key(self)    -> str: return f"{self.window_key}_meta"

    def store_results(self, records: List[FlightRecord], params: "_SearchParams") -> None:
        st.session_state[self._results_key] = records
        st.session_state[self._meta_key]    = params.meta_caption()

    def cached(self) -> tuple[List[FlightRecord], str | None]:
        return (
            st.session_state.get(self._results_key, []),
            st.session_state.get(self._meta_key),
        )


# ── 內部：表單 / 參數收集 ───────────────────────────────────────────────────
@dataclass
class _SearchParams:
    from_airport:  str
    destinations:  List[str]
    outbound:      date
    return_date:   date
    flex_days:     int
    max_stops:     int
    max_duration:  int

    def outbound_dates(self) -> List[date]: return _expand_flex(self.outbound,    self.flex_days)
    def return_dates(self)   -> List[date]: return _expand_flex(self.return_date, self.flex_days)

    def meta_caption(self) -> str:
        return (
            f"{self.from_airport} → {len(self.destinations)} 個目的地  ·  "
            f"{self.outbound} ⇄ {self.return_date}  ·  彈性 ±{self.flex_days} 天"
        )


def _render_form(window: HolidayWindow, state: _SearchState) -> _SearchParams | None:
    """呈現搜尋表單，使用者按下「搜尋」才回傳 _SearchParams；否則回傳 None。"""
    form_id = f"{state.window_key}_form"
    with st.form(form_id, border=True):
        top = st.columns([1, 2, 2, 1])
        with top[0]:
            from_airport = st.radio(
                "出發機場", DEPARTURE_AIRPORTS,
                index=DEPARTURE_AIRPORTS.index(DEFAULT_DEPARTURE),
                horizontal=True, key=f"{form_id}_from",
            )
        with top[1]:
            outbound = st.date_input(
                "出發日（可修改）", value=window.start_date, key=f"{form_id}_out",
            )
        with top[2]:
            return_date = st.date_input(
                "回程日（可修改）", value=window.end_date, key=f"{form_id}_ret",
            )
        with top[3]:
            flex_days = st.slider("彈性 ±N 天", 0, 3, 0, key=f"{form_id}_flex")

        st.caption("目的地區域（預設跨洲長途；可加入其他洲）")
        region_cols = st.columns(len(_REGION_OPTIONS))
        selected_regions: list[str] = []
        for col, opt in zip(region_cols, _REGION_OPTIONS):
            with col:
                if st.checkbox(opt.label, value=opt.default, key=f"{form_id}_rg_{opt.key}"):
                    selected_regions.append(opt.key)

        extra_raw = st.text_input(
            "額外目的地 IATA（逗號分隔，選填）",
            value="", key=f"{form_id}_extra",
        ).upper()

        adv = st.columns(2)
        with adv[0]:
            max_stops = st.number_input(
                "最多轉機次數", 0, 3, MAX_STOPS, key=f"{form_id}_stops",
            )
        with adv[1]:
            max_duration = st.number_input(
                "最長飛行時數", 4, 40, MAX_DURATION_HOURS, key=f"{form_id}_dur",
            )

        submitted = st.form_submit_button("🔍 搜尋此窗口機票", type="primary")

    if not submitted:
        return None

    destinations = _collect_destinations(selected_regions, extra_raw)
    err = _validate(destinations, outbound, return_date)
    if err:
        st.error(err)
        return None

    return _SearchParams(
        from_airport=str(from_airport),
        destinations=destinations,
        outbound=outbound,
        return_date=return_date,
        flex_days=int(flex_days),
        max_stops=int(max_stops),
        max_duration=int(max_duration),
    )


def _collect_destinations(region_keys: list[str], extra_raw: str) -> List[str]:
    codes: list[str] = []
    for rk in region_keys:
        codes.extend(WORLD_DESTINATIONS.get(rk, []))
    extra_valid, extra_invalid = parse_custom_iata(extra_raw)
    if extra_invalid:
        st.warning(f"忽略無效的 IATA 代碼：{', '.join(extra_invalid)}")
    codes.extend(extra_valid)
    return list(dict.fromkeys(codes))


def _validate(destinations: List[str], outbound: date, return_date: date) -> str | None:
    if not destinations:
        return "請至少勾選一個區域或輸入一個目的地代碼。"
    if return_date < outbound:
        return "回程日不可早於出發日。"
    return None


# ── 內部：實際搜尋執行 ──────────────────────────────────────────────────────
def _execute_search(p: _SearchParams) -> List[FlightRecord]:
    out_dates = p.outbound_dates()
    ret_dates = p.return_dates()
    combos = len(out_dates) * len(ret_dates)

    st.info(
        f"將搜尋 {len(p.destinations)} 個目的地 × {combos} 組日期 "
        f"(max_stops={p.max_stops}, max_duration={p.max_duration}h)"
    )

    records: List[FlightRecord] = []
    try:
        with st.status("搜尋中… 這需要一些時間（Google Flights 抓取）", expanded=True) as status:
            scraper = FlightScraper(
                max_stops=p.max_stops,
                max_duration_hours=p.max_duration,
            )
            records = scraper.search_roundtrip_many(
                from_airport=p.from_airport,
                destinations=p.destinations,
                outbound_dates=out_dates,
                return_dates=ret_dates,
            )
            status.update(label=f"完成：{len(records)} 筆", state="complete")
    except Exception as exc:  # noqa: BLE001
        st.error(f"搜尋失敗：{exc}")
        return []

    ensure_twd(records)

    if records:
        try:
            Database().bulk_insert_flights(records)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"結果未存入資料庫：{exc}")
    return records


# ── 內部：結果呈現 ──────────────────────────────────────────────────────────
def _render_cached_results(state: _SearchState) -> None:
    records, meta = state.cached()
    if not records:
        return
    st.markdown("**搜尋結果**")
    if meta:
        st.caption(meta)
    render_results(records, csv_filename_prefix="flyaway_holiday_window")


# ── 小工具 ────────────────────────────────────────────────────────────────
def _expand_flex(d: date, flex: int) -> List[date]:
    if flex <= 0:
        return [d]
    return [d + timedelta(days=delta) for delta in range(-flex, flex + 1)]
