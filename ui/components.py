"""
ui/components.py — Shared UI helpers for the Streamlit app.

Pure presentation: converts FlightRecord objects into DataFrames, builds
the destination-group menu from config, and validates raw user input.
No business logic lives here.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Tuple

import pandas as pd
import streamlit as st

from airline_classifier import classify_airline
from booking_links import BookingLinkFactory
from config import (
    ALL_DESTINATIONS,
    COMPOSITE_ALIASES,
    COMPOSITE_REGIONS,
    FAVOURITE_GROUPS,
    MY_DESTINATIONS,
    NONSTOP_ONLY_REGIONS,
    REGION_ALIASES,
    TWD_FALLBACK_RATES,
    WORLD_DESTINATIONS,
)
from database import FlightRecord
from reporter import dest_label


_IATA_RE = re.compile(r"^[A-Z]{3}$")


# ── Destination menu ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DestinationGroup:
    label: str
    codes: Tuple[str, ...]
    is_custom: bool = False


def build_destination_groups() -> List[DestinationGroup]:
    """
    Build the same group menu that the CLI offers in cmd_search, reading purely
    from config.py (so we don't import main.py).
    """
    # Chinese label lookup (canonical region key → shortest Chinese alias)
    cn_labels: dict[str, str] = {}
    for alias, canon in REGION_ALIASES.items():
        if all("\u4e00" <= c <= "\u9fff" for c in alias):
            if canon not in cn_labels or len(alias) < len(cn_labels[canon]):
                cn_labels[canon] = alias

    groups: List[DestinationGroup] = []

    if MY_DESTINATIONS:
        groups.append(DestinationGroup("⭐ 我的最愛", tuple(MY_DESTINATIONS)))

    for grp_name, grp_codes in FAVOURITE_GROUPS.items():
        if grp_codes:
            groups.append(DestinationGroup(grp_name, tuple(grp_codes)))

    for region_name, region_codes in WORLD_DESTINATIONS.items():
        cn = cn_labels.get(region_name, "")
        display = f"{cn} {region_name}" if cn else region_name
        nonstop_tag = "（僅直達）" if region_name in NONSTOP_ONLY_REGIONS else ""
        groups.append(DestinationGroup(f"{display}{nonstop_tag}", tuple(region_codes)))

    # Composite regions (e.g. 東北亞 = Japan + Korea)
    comp_cn: dict[str, str] = {}
    for alias, ckey in COMPOSITE_ALIASES.items():
        if all("\u4e00" <= ch <= "\u9fff" for ch in alias):
            comp_cn.setdefault(ckey, alias)
    for comp_name, comp_keys in COMPOSITE_REGIONS.items():
        cn = comp_cn.get(comp_name, "")
        display = f"{cn} {comp_name}" if cn else comp_name
        codes: list[str] = []
        for rk in comp_keys:
            codes.extend(WORLD_DESTINATIONS.get(rk, []))
        codes = list(dict.fromkeys(codes))
        groups.append(DestinationGroup(f"{display}（組合）", tuple(codes)))

    groups.append(DestinationGroup("全部 ALL", tuple(ALL_DESTINATIONS)))
    groups.append(DestinationGroup("✏️ 自訂代碼", tuple(), is_custom=True))
    return groups


def parse_custom_iata(raw: str) -> Tuple[List[str], List[str]]:
    """
    Split a comma-separated string into (valid_codes, invalid_tokens).
    Each code must match IATA 3-letter uppercase after trimming.
    """
    valid: List[str] = []
    invalid: List[str] = []
    for tok in raw.split(","):
        code = tok.strip().upper()
        if not code:
            continue
        if _IATA_RE.match(code):
            valid.append(code)
        else:
            invalid.append(tok.strip())
    # De-duplicate while preserving order.
    seen: set[str] = set()
    deduped = [c for c in valid if not (c in seen or seen.add(c))]
    return deduped, invalid


# ── Price normalisation ───────────────────────────────────────────────────────

def ensure_twd(records: Iterable[FlightRecord]) -> None:
    """
    Safety pass: convert any non-TWD FlightRecord to TWD using fallback rates.
    Modifies records in-place (same approach as main.cmd_search).
    """
    for r in records:
        if r.currency and r.currency.upper() != "TWD":
            rate = TWD_FALLBACK_RATES.get(r.currency.upper(), 1.0)
            r.price = round(r.price * rate, 0)
            r.currency = "TWD"


# ── DataFrame conversion ──────────────────────────────────────────────────────

def records_to_dataframe(records: List[FlightRecord]) -> pd.DataFrame:
    """Convert FlightRecord list to a display-oriented DataFrame."""
    rows: list[dict] = []
    for r in records:
        link_set = BookingLinkFactory.from_record(r)
        primary = link_set.primary
        google = link_set.google_link

        rows.append({
            "目的地": dest_label(r.arrival_airport),
            "去程日": r.departure_date,
            "去程時間": _fmt_times(r.departure_time, r.arrival_time),
            "去程時長": r.duration_str,
            "回程日": r.return_date or "—",
            "回程時間": _fmt_times(r.return_dep_time, r.return_arr_time),
            "回程時長": _fmt_duration(r.return_duration),
            "轉機": r.stops_str,
            "航空公司": r.airline or "—",
            "類型": classify_airline(r.airline) if r.airline else "unknown",
            "價格 (TWD)": int(round(r.price, 0)),
            "訂票": primary.url if primary else "",
            "Google Flights": google.url if google else "",
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("價格 (TWD)", ascending=True, kind="stable").reset_index(drop=True)
    return df


def _fmt_times(dep: str, arr: str) -> str:
    """Show only HH:MM part; drop any leading date prefix returned by API."""
    dep = _time_only(dep)
    arr = _time_only(arr)
    if dep == "—" and arr == "—":
        return "—"
    return f"{dep} → {arr}"


def _time_only(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "—"
    # API may prepend a date ("2026-04-30 2:05 PM" or "2026-04-30 14:05").
    # Strip a leading YYYY-MM-DD token; preserve the rest (handles "2:05 PM").
    parts = s.split(maxsplit=1)
    if len(parts) == 2 and len(parts[0]) == 10 and parts[0].count("-") == 2:
        return parts[1]
    return s


def _fmt_duration(minutes: int) -> str:
    if not minutes or minutes <= 0:
        return "—"
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m:02d}m"


def dataframe_column_config() -> dict:
    """Column config for st.dataframe to render clickable booking links."""
    return {
        "價格 (TWD)": st.column_config.NumberColumn(format="NT$ %d"),
        "訂票": st.column_config.LinkColumn("訂票", display_text="🎫 訂票"),
        "Google Flights": st.column_config.LinkColumn(
            "Google Flights", display_text="🔍 查看"
        ),
    }


# Columns shown in the UI (order matches the CLI terminal table).
# "類型" stays in the DataFrame for tab filtering but is hidden from view.
_DISPLAY_COLUMNS = (
    "目的地", "去程日", "去程時間", "去程時長",
    "回程日", "回程時間", "回程時長",
    "轉機", "航空公司", "價格 (TWD)", "訂票", "Google Flights",
)


# ── Result rendering ──────────────────────────────────────────────────────────

def render_results(
    records: List[FlightRecord],
    csv_filename_prefix: str = "flyaway",
) -> None:
    """Render metrics, tabs (all/nonstop/transfer/LCC) and a download button."""
    if not records:
        st.info("⚠️ 沒有找到符合條件的機票。")
        return

    df = records_to_dataframe(records)

    col1, col2, col3 = st.columns(3)
    col1.metric("最低價", f"NT$ {int(df['價格 (TWD)'].min()):,}")
    col2.metric("平均價", f"NT$ {int(df['價格 (TWD)'].mean()):,}")
    col3.metric("結果數", f"{len(df)} 筆")

    nonstop = df[df["轉機"].isin(["直達", "直達*"])]
    transfer = df[~df["轉機"].isin(["直達", "直達*"])]
    traditional = df[df["類型"] == "traditional"]
    lcc = df[df["類型"] == "LCC"]

    tabs = st.tabs([
        f"全部 ({len(df)})",
        f"直達 ({len(nonstop)})",
        f"轉機 ({len(transfer)})",
        f"傳統航空 ({len(traditional)})",
        f"LCC ({len(lcc)})",
    ])
    with tabs[0]:
        _render_table(df)
    with tabs[1]:
        _render_table(nonstop)
    with tabs[2]:
        _render_table(transfer)
    with tabs[3]:
        _render_table(traditional)
    with tabs[4]:
        _render_table(lcc)

    # CSV download — bytes in memory, no temp file.
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    today = date.today().isoformat()
    st.download_button(
        label="⬇ 下載 CSV",
        data=buf.getvalue().encode("utf-8-sig"),
        file_name=f"{csv_filename_prefix}_{today}.csv",
        mime="text/csv",
    )


def _render_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.caption("（此分類沒有結果）")
        return
    st.dataframe(
        df,
        column_config=dataframe_column_config(),
        column_order=_DISPLAY_COLUMNS,
        hide_index=True,
        width="stretch",
    )


# ── Input validation ──────────────────────────────────────────────────────────

def validate_dates(outbound: date, ret: date | None) -> str | None:
    """Return None if valid, else an error message."""
    today = date.today()
    if outbound < today:
        return "出發日期不可早於今天。"
    if ret is not None:
        if ret < outbound:
            return "回程日期不可早於出發日期。"
        if (ret - outbound).days > 365:
            return "行程長度不可超過 365 天。"
    return None
