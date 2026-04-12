"""
main.py — 台北機票比價系統 主程式
=====================================
使用方式：
  python main.py search                          # 互動式搜尋（含來回、彈性日期）
  python main.py search --dest NRT --outbound 2026-05-01 --return 2026-05-06
  python main.py search --dest ALL --use-holidays --flex 2
  python main.py schedule --time 07:00
  python main.py holidays
  python main.py vacation --mode short
  python main.py history --from TPE --to NRT
  python main.py debug-api --dest NRT
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from typing import List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("flight_tracker.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm, IntPrompt
    from rich.table import Table
    from rich import box
    console = Console()
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False
    console   = None

try:
    from fast_flights import get_flights as _ff_check  # noqa: F401
    _HAS_FAST_FLIGHTS = True
except ImportError:
    _HAS_FAST_FLIGHTS = False


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def print_banner() -> None:
    if _HAS_RICH:
        console.print(Panel.fit(
            "[bold cyan]✈  台北機票比價系統  ✈[/bold cyan]\n"
            "[dim]TPE/TSA → 全球 | 直達/轉機分區 | 來回票比價[/dim]",
            border_style="cyan",
        ))
    else:
        print("=" * 55)
        print("  ✈  台北機票比價系統  ✈")
        print("=" * 55)


def _print(msg: str) -> None:
    if _HAS_RICH:
        console.print(msg)
    else:
        print(msg)


def _ask(prompt: str, default: str = "") -> str:
    if _HAS_RICH:
        return Prompt.ask(f"  {prompt}", default=default)
    print(f"  {prompt} [{default}]: ", end="")
    v = input().strip()
    return v if v else default


def _confirm(prompt: str, default: bool = True) -> bool:
    if _HAS_RICH:
        return Confirm.ask(f"  {prompt}", default=default)
    print(f"  {prompt} ({'Y/n' if default else 'y/N'}): ", end="")
    v = input().strip().lower()
    return default if not v else v == "y"


def _int_ask(prompt: str, default: int) -> int:
    if _HAS_RICH:
        return IntPrompt.ask(f"  {prompt}", default=default)
    print(f"  {prompt} [{default}]: ", end="")
    v = input().strip()
    try:
        return int(v) if v else default
    except ValueError:
        return default


def _ask_export_csv() -> bool:
    return _confirm("要匯出 CSV 嗎？", default=False)


# ── 彈性日期展開 ───────────────────────────────────────────────────────────────
def expand_flex_dates(base_dates: List[date], flex_days: int) -> List[date]:
    """
    以每個 base_date 為中心，展開 ±flex_days 天（去重、排序）。
    flex_days=0 → 回傳原始日期
    """
    if flex_days <= 0:
        return sorted(set(base_dates))
    expanded: set[date] = set()
    for d in base_dates:
        for delta in range(-flex_days, flex_days + 1):
            expanded.add(d + timedelta(days=delta))
    return sorted(expanded)


# ── 預設旅行天數（依地區）──────────────────────────────────────────────────────
def default_trip_days_for(destinations: List[str]) -> int:
    from config import is_intercontinental, ASIA_DEFAULT_TRIP_DAYS, INTER_DEFAULT_TRIP_DAYS
    if any(is_intercontinental(d) for d in destinations):
        return INTER_DEFAULT_TRIP_DAYS
    return ASIA_DEFAULT_TRIP_DAYS


# ── 週末完整覆蓋天數計算 ───────────────────────────────────────────────────────
def suggest_trip_days_with_weekends(start: date, min_days: int, max_days: int) -> int:
    for days in range(min_days, max_days + 1):
        end = start + timedelta(days=days - 1)
        if end.weekday() >= 5:  # 週六或週日
            return days
    return max_days


# ══════════════════════════════════════════════════════════════════════════════
#  互動式日期 & 行程設定
# ══════════════════════════════════════════════════════════════════════════════

def ask_trip_dates(
    destinations: List[str],
    use_holidays: bool = False,
    outbound_arg: Optional[str] = None,
    return_arg:   Optional[str] = None,
    flex_arg:     Optional[int] = None,
) -> Tuple[List[date], List[date], int]:
    """
    互動式詢問出發日期、回程日期與彈性天數。
    回傳 (outbound_dates, return_dates, flex_days)
    """
    from config import (
        ASIA_DEFAULT_TRIP_DAYS, INTER_DEFAULT_TRIP_DAYS,
        INTER_TRIP_MIN_DAYS, INTER_TRIP_MAX_DAYS,
    )
    from taiwan_holidays import get_holiday_windows, print_holiday_windows

    default_days = default_trip_days_for(destinations)
    is_inter     = any(__import__("config").is_intercontinental(d) for d in destinations)

    # ── 出發日期 ──────────────────────────────────────────────────────────────
    outbound_dates: List[date] = []
    # Initialised before `if use_holidays` to avoid NameError in return-date section
    return_dates_holidays: List[date] = []

    if use_holidays:
        min_d   = INTER_TRIP_MIN_DAYS if is_inter else ASIA_DEFAULT_TRIP_DAYS
        max_d   = INTER_TRIP_MAX_DAYS if is_inter else ASIA_DEFAULT_TRIP_DAYS + 2
        windows = get_holiday_windows(lookahead_days=180, min_trip_days=min_d, max_trip_days=max_d)
        print_holiday_windows(windows, top_n=10)

        if _HAS_RICH:
            for i, w in enumerate(windows[:10], 1):
                _print(f"  [cyan]{i:>2}[/cyan]. {w.label}")
            raw = _ask("選擇假期窗口編號（逗號分隔，全部按 Enter）", "all")
        else:
            print("選擇窗口編號（逗號，全部留空）：", end="")
            raw = input().strip() or "all"

        if raw.strip().lower() in ("", "all"):
            outbound_dates        = [w.start_date for w in windows[:10]]
            return_dates_holidays = [w.end_date   for w in windows[:10]]
        else:
            idxs                  = [int(x) - 1 for x in raw.split(",") if x.strip().isdigit()]
            outbound_dates        = [windows[i].start_date for i in idxs if i < len(windows)]
            return_dates_holidays = [windows[i].end_date   for i in idxs if i < len(windows)]

    elif outbound_arg:
        outbound_dates = [date.fromisoformat(d.strip()) for d in outbound_arg.split(",")]

    else:
        _print("\n[bold]📅 出發日期設定[/bold]" if _HAS_RICH else "\n📅 出發日期設定")
        raw = _ask("出發日期（YYYY-MM-DD，多個用逗號，留空=未來常用節點）", "")
        if not raw:
            today          = date.today()
            outbound_dates = [today + timedelta(days=d) for d in [14, 30, 60, 90]]
        else:
            outbound_dates = [date.fromisoformat(d.strip()) for d in raw.split(",")]

    # ── 回程日期 ──────────────────────────────────────────────────────────────
    return_dates: List[date] = []

    if return_arg:
        return_dates = [date.fromisoformat(d.strip()) for d in return_arg.split(",")]

    elif use_holidays and return_dates_holidays:
        return_dates = return_dates_holidays

    else:
        _print("\n[bold]🔙 回程日期設定[/bold]" if _HAS_RICH else "\n🔙 回程日期設定")
        if is_inter:
            if outbound_dates:
                sug = suggest_trip_days_with_weekends(
                    outbound_dates[0], INTER_TRIP_MIN_DAYS, INTER_TRIP_MAX_DAYS
                )
            else:
                sug = INTER_DEFAULT_TRIP_DAYS
            _print(
                f"  [dim]跨洲旅行建議 {INTER_TRIP_MIN_DAYS}–{INTER_TRIP_MAX_DAYS} 天"
                f"（含完整週末），建議 {sug} 天[/dim]"
                if _HAS_RICH else
                f"  跨洲旅行建議 {INTER_TRIP_MIN_DAYS}–{INTER_TRIP_MAX_DAYS} 天，建議 {sug} 天"
            )
        else:
            sug = ASIA_DEFAULT_TRIP_DAYS
            _print(
                f"  [dim]亞洲旅行預設 {sug} 天[/dim]"
                if _HAS_RICH else f"  亞洲旅行預設 {sug} 天"
            )

        raw_ret = _ask(
            "回程日期（YYYY-MM-DD，多個用逗號；或輸入旅行天數如 '5'）",
            str(sug),
        )

        if raw_ret.strip().isdigit():
            trip_days    = int(raw_ret.strip())
            return_dates = [d + timedelta(days=trip_days - 1) for d in outbound_dates]
        else:
            parts = [p.strip() for p in raw_ret.split(",") if p.strip()]
            if parts:
                try:
                    return_dates = [date.fromisoformat(p) for p in parts]
                except ValueError:
                    return_dates = [d + timedelta(days=default_days - 1) for d in outbound_dates]

    # 回程日期與出發日期對齊
    if len(return_dates) == 1 and len(outbound_dates) > 1:
        return_dates = return_dates * len(outbound_dates)
    elif not return_dates:
        return_dates = [d + timedelta(days=default_days - 1) for d in outbound_dates]

    # ── 彈性天數 ──────────────────────────────────────────────────────────────
    if flex_arg is not None:
        flex_days = flex_arg
    else:
        _print("\n[bold]📐 彈性出發日期[/bold]" if _HAS_RICH else "\n📐 彈性出發日期")
        _print(
            "  [dim]設定後會在出發/回程日期前後各加幾天一起搜尋[/dim]"
            if _HAS_RICH else "  設定後會在出發/回程日期前後各加幾天一起搜尋"
        )
        flex_days = _int_ask("彈性天數（0=不彈性，1=±1天，2=±2天）", 0)

    return outbound_dates, return_dates, flex_days


# ══════════════════════════════════════════════════════════════════════════════
#  子命令：search
# ══════════════════════════════════════════════════════════════════════════════

def cmd_search(args: argparse.Namespace) -> None:
    from config import (
        DEFAULT_DEPARTURE, ALL_DESTINATIONS, WORLD_DESTINATIONS,
        MAX_STOPS, MAX_DURATION_HOURS, get_max_stops_for,
    )
    from flight_scraper import FlightScraper
    from database import Database
    from reporter import print_results, export_csv

    # ── 出發機場 ──────────────────────────────────────────────────────────────
    from_airport = (getattr(args, "from_airport", None) or DEFAULT_DEPARTURE).upper()
    if _HAS_RICH and not getattr(args, "from_airport", None):
        from_airport = Prompt.ask(
            "  出發機場代碼", default=DEFAULT_DEPARTURE,
            choices=["TPE", "TSA"], show_choices=True,
        ).upper()

    # ── 目的地 ────────────────────────────────────────────────────────────────
    _DEST_ALIASES: dict[str, list[str]] = {
        "japan":       ["NRT", "HND", "KIX", "NGO", "CTS", "FUK"],
        "korea":       ["ICN", "GMP", "PUS"],
        "hongkong":    ["HKG", "MFM"],
        "thailand":    ["BKK", "DMK"],
        "singapore":   ["SIN"],
        "malaysia":    ["KUL"],
        "philippines": ["MNL"],
        "indonesia":   ["CGK", "DPS"],
        "vietnam":     ["HAN", "SGN"],
        "cambodia":    ["REP", "PNH"],
        "myanmar":     ["RGN", "MDL"],
        "laos":        ["VTE"],
        "india":       ["DEL", "BOM", "MAA", "BLR"],
        "srilanka":    ["CMB"],
        "nepal":       ["KTM"],
        "bangladesh":  ["DAC"],
        "uk":          ["LHR"],
        "france":      ["CDG"],
        "germany":     ["FRA"],
        "netherlands": ["AMS"],
        "spain":       ["MAD", "BCN"],
        "italy":       ["FCO"],
        "austria":     ["VIE"],
        "switzerland": ["ZRH"],
        "turkey":      ["IST"],
        "czechia":     ["PRG"],
        "poland":      ["WAW"],
        "sweden":      ["ARN"],
        "denmark":     ["CPH"],
        "finland":     ["HEL"],
        "greece":      ["ATH"],
        "portugal":    ["LIS"],
        "ireland":     ["DUB"],
        "australia":   ["SYD", "MEL", "BNE", "PER"],
        "newzealand":  ["AKL"],
        "neasia":      ["NRT", "HND", "KIX", "NGO", "CTS", "FUK", "ICN", "GMP", "PUS", "HKG", "MFM"],
        "seasia":      ["BKK", "DMK", "SIN", "KUL", "MNL", "CGK", "DPS", "HAN", "SGN"],
        "europe":      list(WORLD_DESTINATIONS.get("歐洲 Europe", [])),
        "oceania":     list(WORLD_DESTINATIONS.get("大洋洲 Oceania", [])),
    }

    destinations: List[str] = []
    dest_arg = getattr(args, "dest", None)
    if dest_arg:
        dest_up  = dest_arg.upper()
        dest_key = dest_arg.lower().replace(" ", "").replace("-", "")

        if dest_up == "ALL":
            destinations = ALL_DESTINATIONS
        elif dest_up in ("MY", "MINE"):
            from config import MY_DESTINATIONS
            destinations = MY_DESTINATIONS
        elif dest_arg in WORLD_DESTINATIONS:
            destinations = WORLD_DESTINATIONS[dest_arg]
        elif dest_key in _DEST_ALIASES:
            destinations = _DEST_ALIASES[dest_key]
        else:
            region_match = next(
                (v for k, v in WORLD_DESTINATIONS.items() if dest_arg.lower() in k.lower()),
                None,
            )
            if region_match:
                destinations = region_match
            else:
                from config import FAVOURITE_GROUPS
                fav_match = next(
                    (v for k, v in FAVOURITE_GROUPS.items() if dest_arg in k), None
                )
                if fav_match:
                    destinations = fav_match
                else:
                    raw_codes = [c.strip().upper() for c in dest_arg.split(",")]
                    invalid   = [c for c in raw_codes if not (len(c) == 3 and c.isalpha())]
                    if invalid:
                        _print(
                            f"[yellow]⚠️ 無法識別的目的地：{', '.join(invalid)}。"
                            f"請使用 IATA 代碼（如 NRT）、國家名（如 Japan）"
                            f"或地區名（如 歐洲 Europe）。[/yellow]"
                            if _HAS_RICH else
                            f"⚠️ 無法識別的目的地：{', '.join(invalid)}。"
                        )
                        return
                    destinations = raw_codes

    # ── 行程類型提示 ──────────────────────────────────────────────────────────
    nonstop_dests  = [d for d in destinations if get_max_stops_for(d, MAX_STOPS) == 0]
    transfer_dests = [d for d in destinations if get_max_stops_for(d, MAX_STOPS) > 0]
    if nonstop_dests and _HAS_RICH:
        console.print(
            f"\n  [yellow]⚡ {len(nonstop_dests)} 個目的地（東北亞/東南亞）僅搜尋直達班次[/yellow]"
        )
    if transfer_dests and _HAS_RICH:
        console.print(
            f"  [dim]✈  {len(transfer_dests)} 個目的地維持最多 {MAX_STOPS} 次轉機[/dim]"
        )

    # ── 日期 & 彈性設定 ───────────────────────────────────────────────────────
    outbound_dates, return_dates, flex_days = ask_trip_dates(
        destinations=destinations,
        use_holidays=getattr(args, "use_holidays", False),
        outbound_arg=getattr(args, "outbound", None),
        return_arg=getattr(args, "ret", None),
        flex_arg=getattr(args, "flex", None),
    )

    out_flex = expand_flex_dates(outbound_dates, flex_days)
    ret_flex = expand_flex_dates(return_dates,   flex_days)

    # ── 確認摘要 ──────────────────────────────────────────────────────────────
    max_stops    = getattr(args, "max_stops",    None) or MAX_STOPS
    max_duration = getattr(args, "max_duration", None) or MAX_DURATION_HOURS

    if _HAS_RICH:
        t = Table(title="搜尋設定摘要", box=box.SIMPLE)
        t.add_column("項目", style="dim")
        t.add_column("設定", style="cyan")
        t.add_row("出發機場",     from_airport)
        t.add_row("目的地數量",   f"{len(destinations)} 個")
        t.add_row("出發日期",     ", ".join(str(d) for d in out_flex))
        t.add_row("回程日期",     ", ".join(str(d) for d in ret_flex))
        t.add_row("彈性天數",     f"±{flex_days} 天")
        t.add_row("東北亞/東南亞", "僅直達 (0 stops)")
        t.add_row("其他地區",     f"最多 {max_stops} 次轉機")
        t.add_row("最長飛行",     f"{max_duration} 小時")
        console.print(t)
        if not Confirm.ask("  確認開始搜尋？", default=True):
            return
    else:
        print(f"\n出發機場: {from_airport} | 目的地: {len(destinations)} 個")
        print(f"出發: {out_flex} | 回程: {ret_flex} | 彈性: ±{flex_days}天")

    # ── 搜尋（來回票）────────────────────────────────────────────────────────
    db = Database()
    scraper = FlightScraper(max_stops=max_stops, max_duration_hours=max_duration)

    _print("\n[bold cyan]── 搜尋來回票 ──[/bold cyan]" if _HAS_RICH else "\n── 搜尋來回票 ──")

    roundtrip_records = scraper.search_roundtrip_many(
        from_airport=from_airport,
        destinations=destinations,
        outbound_dates=out_flex,
        return_dates=ret_flex,
    )

    if roundtrip_records:
        db.bulk_insert_flights(roundtrip_records)
        # Use group_by_date when multiple departure dates were searched
        multi_date = len(out_flex) > 1
        print_results(
            roundtrip_records,
            title=f"{from_airport} ⇄ {', '.join(destinations[:3])}{'...' if len(destinations) > 3 else ''} 來回票",
            top_n=getattr(args, "top_n", 20) or 20,
            split_lcc=True,
            group_by_date=multi_date,
        )
    else:
        _print("⚠️  沒有找到符合條件的來回票。")
        _print(
            "[dim]提示：若廉航不提供來回票，可個別搜尋單程後自行配對。[/dim]"
            if _HAS_RICH else "提示：若廉航不提供來回票，可個別搜尋單程後自行配對。"
        )

    if roundtrip_records and (getattr(args, "export_csv", False) or _ask_export_csv()):
        export_csv(roundtrip_records)


# ══════════════════════════════════════════════════════════════════════════════
#  子命令：schedule
# ══════════════════════════════════════════════════════════════════════════════

def cmd_schedule(args: argparse.Namespace) -> None:
    from config import DEFAULT_DEPARTURE, ALL_DESTINATIONS
    from scheduler import FlightScheduler

    run_time     = getattr(args, "time", None) or "07:00"
    from_airport = (getattr(args, "from_airport", None) or DEFAULT_DEPARTURE).upper()
    dest_raw     = getattr(args, "dest", None)
    dest_list    = (
        [c.strip().upper() for c in dest_raw.split(",")]
        if dest_raw and dest_raw.upper() != "ALL"
        else ALL_DESTINATIONS
    )

    if _HAS_RICH:
        _print("\n[bold]排程設定[/bold]")
        _print(f"  執行時間  : [yellow]{run_time}[/yellow] 台灣時間")
        _print(f"  出發機場  : [cyan]{from_airport}[/cyan]")
        _print(f"  目的地數  : [cyan]{len(dest_list)}[/cyan] 個\n")

    sched = FlightScheduler(
        run_time=run_time,
        from_airport=from_airport,
        destinations=dest_list,
    )
    sched.start(run_immediately=getattr(args, "run_now", False))


# ══════════════════════════════════════════════════════════════════════════════
#  子命令：holidays
# ══════════════════════════════════════════════════════════════════════════════

def cmd_holidays(args: argparse.Namespace) -> None:
    from taiwan_holidays import get_holiday_windows, print_holiday_windows
    from config import INTER_TRIP_MIN_DAYS, INTER_TRIP_MAX_DAYS

    is_inter = getattr(args, "intercontinental", False)
    min_d = INTER_TRIP_MIN_DAYS if is_inter else (getattr(args, "min_days", 3) or 3)
    max_d = INTER_TRIP_MAX_DAYS if is_inter else (getattr(args, "max_days", 14) or 14)

    windows = get_holiday_windows(
        lookahead_days=getattr(args, "days", 365) or 365,
        min_trip_days=min_d,
        max_trip_days=max_d,
    )
    print_holiday_windows(windows, top_n=getattr(args, "top_n", 20) or 20)

    if _HAS_RICH:
        _print(
            "\n[dim]提示：執行 [cyan]python main.py search --use-holidays[/cyan] "
            "可直接以這些日期搜尋機票[/dim]\n"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  子命令：history
# ══════════════════════════════════════════════════════════════════════════════

def cmd_history(args: argparse.Namespace) -> None:
    from database import Database
    from reporter import print_results, dest_label

    db  = Database()
    frm = (getattr(args, "from_airport", None) or "TPE").upper()
    to  = (getattr(args, "to", None) or "").upper()

    if to:
        days_n  = getattr(args, "days", 30) or 30
        history = db.get_price_history(frm, to, days=days_n)
        if _HAS_RICH:
            t = Table(title=f"📈 {frm} → {dest_label(to)} 價格歷史（近 {days_n} 天）")
            t.add_column("日期")
            t.add_column("最低價", justify="right", style="green")
            t.add_column("平均價", justify="right", style="yellow")
            t.add_column("幣別")
            for row in history:
                t.add_row(
                    row["day"],
                    f"{row['min_price']:,.0f}",
                    f"{row['avg_price']:,.0f}",
                    row["currency"],
                )
            console.print(t)
        else:
            for row in history:
                print(f"{row['day']}  最低: {row['min_price']:,.0f}  均價: {row['avg_price']:,.0f}")
    else:
        records = db.get_cheapest_per_destination(from_airport=frm)
        print_results(records, title=f"📊 資料庫中 {frm} 出發各地最低票價")


# ══════════════════════════════════════════════════════════════════════════════
#  子命令：vacation
# ══════════════════════════════════════════════════════════════════════════════

def cmd_vacation(args: argparse.Namespace) -> None:
    """
    Vacation Mode — 三種固定假期模式自動搜尋最便宜旅遊組合。
      short : 5 天  / 1 週末 / 亞洲直達
      long  : 9 天  / 2 週末 / 跨洲含轉機
      happy : 16 天 / 3 週末 / 跨洲含轉機
    加上 --flex 可開啟彈性天數選項。
    """
    from config import (
        DEFAULT_DEPARTURE, VACATION_MODES,
        ASIA_DESTINATIONS, NON_ASIA_DESTINATIONS,
        VACATION_REQUIRE_TW_HOLIDAY,
        VACATION_TOP_WINDOWS, VACATION_TOP_DEST, VACATION_TOP_RESULTS,
    )
    from vacation_windows import find_vacation_windows, print_vacation_windows
    from flight_scraper import FlightScraper
    from database import Database
    from reporter import print_results, print_vacation_summary, export_csv

    # ── 選擇假期模式 ──────────────────────────────────────────────────────────
    mode = getattr(args, "mode", None)
    if not mode:
        if _HAS_RICH:
            _print("\n[bold]🏖️  選擇假期模式：[/bold]")
            for i, (key, cfg) in enumerate(VACATION_MODES.items(), 1):
                label    = cfg["label"]
                days     = cfg["days"]
                weekends = cfg["weekends"]
                dest_str = "亞洲直達" if cfg["destinations"] == "asia" else "跨洲含轉機"
                _print(f"  [cyan]{i}[/cyan]. {label}  [dim]({days} 天 / {weekends} 週末 / {dest_str})[/dim]")
            choice = _int_ask("請選擇（輸入數字）", 1)
            mode   = list(VACATION_MODES.keys())[max(0, min(choice - 1, len(VACATION_MODES) - 1))]
        else:
            print("  1=短途(5天)  2=長途(9天)  3=快樂(16天)  選擇: ", end="")
            raw      = input().strip()
            mode_map = {"1": "short", "2": "long", "3": "happy"}
            mode     = mode_map.get(raw, "short")

    cfg = VACATION_MODES.get(mode)
    if not cfg:
        _print(f"❌ 未知模式: {mode}，使用 short")
        mode, cfg = "short", VACATION_MODES["short"]

    # ── 彈性天數 ──────────────────────────────────────────────────────────────
    flex_days = getattr(args, "flex_days", None)
    if flex_days is None:
        if _HAS_RICH:
            _print(f"\n[bold]📐 彈性天數[/bold]  [dim]（固定天數 = {cfg['days']} 天）[/dim]")
            _print("  開啟後，也會搜尋固定天數前後 ±N 天的窗口。")
            raw = _ask("彈性天數（0=只搜尋固定天數，1=±1天）", "0")
            flex_days = int(raw) if raw.isdigit() else 0
        else:
            flex_days = 0

    horizon         = getattr(args, "horizon", None) or cfg["horizon"]
    require_holiday = getattr(args, "require_holiday", None)
    if require_holiday is None:
        require_holiday = _confirm("必須包含台灣國定假日？", default=VACATION_REQUIRE_TW_HOLIDAY)

    # ── 目的地 ────────────────────────────────────────────────────────────────
    from_airport = (getattr(args, "from_airport", None) or DEFAULT_DEPARTURE).upper()
    dest_arg     = getattr(args, "dest", None)

    if dest_arg:
        from config import WORLD_DESTINATIONS, ALL_DESTINATIONS
        if dest_arg.upper() == "ALL":
            destinations = ALL_DESTINATIONS
        elif dest_arg in WORLD_DESTINATIONS:
            destinations = WORLD_DESTINATIONS[dest_arg]
        else:
            destinations = [c.strip().upper() for c in dest_arg.split(",")]
        dest_label_str = dest_arg
    else:
        if cfg["destinations"] == "asia":
            destinations   = ASIA_DESTINATIONS
            dest_label_str = "亞洲"
        else:
            destinations   = NON_ASIA_DESTINATIONS
            dest_label_str = "亞洲以外"

    max_stops      = cfg["max_stops"] if mode == "short" else (
        getattr(args, "max_stops", None) or cfg["max_stops"]
    )
    max_duration_h = getattr(args, "max_duration", None) or cfg["max_duration"]
    top_windows    = getattr(args, "top_windows",  None) or VACATION_TOP_WINDOWS
    top_dest       = getattr(args, "top_dest",     None) or VACATION_TOP_DEST

    # ── 計算旅遊窗口 ──────────────────────────────────────────────────────────
    _print(
        f"\n[bold cyan]🔍 計算 {cfg['label']} 旅遊窗口...[/bold cyan]"
        if _HAS_RICH else f"\n計算 {cfg['label']} 旅遊窗口..."
    )

    windows = find_vacation_windows(
        mode=mode,
        horizon_days=horizon,
        require_tw_holiday=require_holiday,
        flex_days_override=flex_days,
    )

    if not windows:
        _print("⚠️  找不到符合條件的旅遊窗口。")
        _print(
            "  建議：加上 [cyan]--no-holiday[/cyan] 解除台灣假日限制，"
            "或加上 [cyan]--flex 1[/cyan] 開啟彈性天數。"
            if _HAS_RICH else "  建議：加上 --no-holiday 或 --flex 1"
        )
        return

    print_vacation_windows(windows, mode=mode, top_n=top_windows * 3)

    chosen_windows = windows[:top_windows]
    dest_sample    = destinations[:top_dest]

    if _HAS_RICH:
        t = Table(title=f"{cfg['label']} 搜尋設定", box=box.SIMPLE)
        t.add_column("項目", style="dim")
        t.add_column("設定", style="cyan")
        t.add_row("假期模式",   cfg["label"])
        t.add_row("固定天數",   f"{cfg['days']} 天" + (f"  ±{flex_days} 天彈性" if flex_days else ""))
        t.add_row("目的地",     f"{dest_label_str}（{len(dest_sample)} 個航點）")
        t.add_row("最多轉機",   "直達（強制）" if max_stops == 0 else f"≤{max_stops} 次")
        t.add_row("最長飛行",   f"{max_duration_h} 小時")
        t.add_row("搜尋窗口",   f"{len(chosen_windows)} 個")
        t.add_row("含台灣假日", "✅ 必含" if require_holiday else "不限")
        console.print(t)
        if not _confirm("確認開始搜尋？", default=True):
            return

    db = Database()

    scraper     = FlightScraper(max_stops=max_stops, max_duration_hours=max_duration_h)
    all_results: List = []

    for w_idx, win in enumerate(chosen_windows, 1):
        _print(
            f"\n[bold]窗口 {w_idx}/{len(chosen_windows)}[/bold]  "
            f"[cyan]{win.depart}[/cyan] → [cyan]{win.ret}[/cyan]  "
            f"[dim]({win.trip_days}天 / {win.weekends}週末 / 請{win.leave_days}天假)"
            f"{'  [彈性]' if win.is_flex else ''}[/dim]"
            if _HAS_RICH else
            f"\n窗口 {w_idx}/{len(chosen_windows)}: {win.depart} → {win.ret} ({win.trip_days}天)"
        )

        records = scraper.search_roundtrip_many(
            from_airport=from_airport,
            destinations=dest_sample,
            outbound_dates=[win.depart],
            return_dates=[win.ret],
        )

        if records:
            db.bulk_insert_flights(records)
            all_results.extend(records)
            print_results(
                records,
                title=f"{cfg['label']}  {win.depart}→{win.ret}",
                top_n=VACATION_TOP_RESULTS,
                split_lcc=True,
                group_by_date=False,
            )

    if all_results:
        print_vacation_summary(
            all_results,
            mode_label=cfg["label"],
            top_n=VACATION_TOP_RESULTS,
        )
        if getattr(args, "export_csv", False) or _ask_export_csv():
            export_csv(all_results, filename=f"vacation_{mode}_{date.today()}.csv")
    else:
        _print("⚠️  所有窗口均未找到符合條件的航班。")


# ══════════════════════════════════════════════════════════════════════════════
#  子命令：debug-api
# ══════════════════════════════════════════════════════════════════════════════

def cmd_debug_api(args: argparse.Namespace) -> None:
    if not _HAS_FAST_FLIGHTS:
        print("❌ fast-flights 未安裝，請執行: pip install fast-flights")
        return

    import inspect
    import fast_flights as ff
    from fast_flights import FlightData, Passengers, get_flights

    dep  = (getattr(args, "from_airport", None) or "TPE").upper()
    dest = (getattr(args, "dest",         None) or "NRT").upper()
    dt   = getattr(args, "date",     None) or "2026-05-01"
    ret  = getattr(args, "ret_date", None) or "2026-05-06"

    print(f"\n📦 fast-flights 版本: {getattr(ff, '__version__', 'unknown')}")
    print(f"📦 套件路徑: {ff.__file__}")
    try:
        print(f"📋 get_flights 簽名: {inspect.signature(get_flights)}")
    except Exception as e:
        print(f"⚠️  無法取得簽名: {e}")

    pax = Passengers(adults=1, children=0, infants_in_seat=0)

    def dump_flight(f, label: str) -> None:
        print(f"\n{'─'*60}")
        print(f"  {label}")
        print(f"{'─'*60}")
        for attr in sorted(dir(f)):
            if attr.startswith("_"):
                continue
            try:
                val = getattr(f, attr)
                if not callable(val):
                    print(f"  {attr:30s}: {val!r}")
            except Exception:
                pass

    def do_oneway(frm, to, d, label):
        print(f"\n{'='*60}")
        print(f"  🔍 {label}  {frm} → {to}  {d}")
        print(f"{'='*60}")
        for mode in ("fallback", "force-fallback", "common"):
            try:
                result  = get_flights(
                    flight_data=[FlightData(date=d, from_airport=frm, to_airport=to)],
                    trip="one-way", seat="economy", passengers=pax,
                    fetch_mode=mode,
                )
                flights = []
                for attr in ("flights", "best_flights", "other_flights"):
                    b = getattr(result, attr, None)
                    if b:
                        flights.extend(b)
                if flights:
                    print(f"✅ fetch_mode='{mode}' → {len(flights)} 筆")
                    dump_flight(flights[0], f"第一筆 Flight (fetch_mode={mode})")
                    return flights
                print(f"  fetch_mode='{mode}' → 0 筆")
            except Exception as e:
                print(f"  fetch_mode='{mode}' 失敗: {e}")
        return []

    out_flights = do_oneway(dep, dest, dt,  "去程單程")
    ret_flights = do_oneway(dest, dep, ret, "回程單程")

    print(f"\n{'='*60}")
    print("  🔍 來回票 API 測試（預期失敗）")
    print(f"{'='*60}")
    try:
        get_flights(
            flight_data=[
                FlightData(date=dt,  from_airport=dep,  to_airport=dest),
                FlightData(date=ret, from_airport=dest, to_airport=dep),
            ],
            trip="round-trip", seat="economy", passengers=pax,
        )
        print("✅ 意外成功（API 已修復）")
    except RuntimeError as e:
        print(f"⚠️  確認：round-trip API 目前不可用（{str(e)[:80]}...）")
        print("   → 系統將自動使用「去程+回程分開搜尋再配對」策略")

    if out_flights and ret_flights:
        from flight_scraper import _parse_price_and_currency, _combine_prices
        print(f"\n{'='*60}")
        print("  💡 配對預覽（前3筆）")
        print(f"{'='*60}")
        for out in out_flights[:3]:
            for ret_f in ret_flights[:3]:
                p_out, c_out = _parse_price_and_currency(str(getattr(out, "price", "") or ""))
                p_ret, c_ret = _parse_price_and_currency(str(getattr(ret_f, "price", "") or ""))
                combined, cur = _combine_prices(p_out, c_out, p_ret, c_ret)
                print(
                    f"  去 {getattr(out, 'departure', '?')}→{getattr(out, 'arrival', '?')}"
                    f" ({getattr(out, 'name', '?')})"
                    f" + 回 {getattr(ret_f, 'departure', '?')}→{getattr(ret_f, 'arrival', '?')}"
                    f" ({getattr(ret_f, 'name', '?')})"
                    f" = {cur} {combined:,.0f}"
                )


# ══════════════════════════════════════════════════════════════════════════════
#  CLI 定義
# ══════════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main",
        description="台北機票比價系統 — 來回搜尋 | Vacation Mode | 訂票連結",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python main.py search                                      # 互動式（全功能）
  python main.py search --dest NRT --outbound 2026-05-01 --return 2026-05-06
  python main.py search --dest "東北亞 NE Asia" --use-holidays --flex 1
  python main.py vacation                                    # 互動式假期搜尋
  python main.py vacation --mode short                       # 短途 5 天亞洲直達
  python main.py vacation --mode long --no-holiday           # 長途 9 天不限假日
  python main.py vacation --mode happy --flex 2              # 快樂 16 天±2彈性
  python main.py schedule --time 08:00 --run-now
  python main.py holidays
  python main.py history --to NRT --days 30
  python main.py debug-api --dest NRT
        """,
    )
    sub = parser.add_subparsers(dest="command")

    p_s = sub.add_parser("search", help="搜尋來回機票")
    p_s.add_argument("--from",         dest="from_airport", metavar="IATA")
    p_s.add_argument("--dest",         metavar="CODE|REGION|MY|ALL")
    p_s.add_argument("--outbound",     metavar="YYYY-MM-DD[,...]")
    p_s.add_argument("--return",       dest="ret", metavar="YYYY-MM-DD|N天")
    p_s.add_argument("--use-holidays", action="store_true")
    p_s.add_argument("--flex",         type=int, metavar="N")
    p_s.add_argument("--max-stops",    type=int)
    p_s.add_argument("--max-duration", type=int)
    p_s.add_argument("--top-n",        type=int, default=20)
    p_s.add_argument("--export-csv",   action="store_true")

    p_sc = sub.add_parser("schedule", help="啟動每日自動排程")
    p_sc.add_argument("--time",    default="07:00")
    p_sc.add_argument("--from",    dest="from_airport", metavar="IATA")
    p_sc.add_argument("--dest",    metavar="CODE[,...]")
    p_sc.add_argument("--run-now", action="store_true")

    p_h = sub.add_parser("holidays", help="查看台灣假期最佳出遊窗口")
    p_h.add_argument("--days",             type=int, default=365)
    p_h.add_argument("--min-days",         type=int, default=3)
    p_h.add_argument("--max-days",         type=int, default=18)
    p_h.add_argument("--top-n",            type=int, default=20)
    p_h.add_argument("--intercontinental", action="store_true")

    p_v = sub.add_parser("vacation", help="🏖️  Vacation Mode — 自動找三種假期的最便宜旅遊組合")
    p_v.add_argument("--mode",            choices=["short", "long", "happy"])
    p_v.add_argument("--horizon",         type=int, metavar="DAYS")
    p_v.add_argument("--flex",            type=int, dest="flex_days", metavar="N")
    p_v.add_argument("--require-holiday", dest="require_holiday",
                     action="store_true", default=None)
    p_v.add_argument("--no-holiday",      dest="require_holiday", action="store_false")
    p_v.add_argument("--dest",            metavar="CODE|REGION")
    p_v.add_argument("--from",            dest="from_airport", default="TPE")
    p_v.add_argument("--max-stops",       type=int, dest="max_stops")
    p_v.add_argument("--max-duration",    type=int, dest="max_duration")
    p_v.add_argument("--top-windows",     type=int, dest="top_windows")
    p_v.add_argument("--top-dest",        type=int, dest="top_dest")
    p_v.add_argument("--export-csv",      action="store_true")

    p_hi = sub.add_parser("history", help="查看歷史票價紀錄")
    p_hi.add_argument("--from", dest="from_airport", default="TPE")
    p_hi.add_argument("--to",   metavar="IATA")
    p_hi.add_argument("--days", type=int, default=30)

    p_d = sub.add_parser("debug-api", help="診斷 fast-flights API 原始回應結構")
    p_d.add_argument("--from",     dest="from_airport", default="TPE")
    p_d.add_argument("--dest",     default="NRT")
    p_d.add_argument("--date",     default="2026-05-01")
    p_d.add_argument("--ret-date", dest="ret_date", default="2026-05-06")

    return parser


# ══════════════════════════════════════════════════════════════════════════════
#  入口點
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print_banner()
    parser = build_parser()
    args   = parser.parse_args()

    if not args.command:
        args.command      = "search"
        args.from_airport = None
        args.dest         = None
        args.outbound     = None
        args.ret          = None
        args.use_holidays = False
        args.flex         = None
        args.max_stops    = None
        args.max_duration = None
        args.top_n        = 20
        args.export_csv   = False

    dispatch = {
        "search":    cmd_search,
        "schedule":  cmd_schedule,
        "holidays":  cmd_holidays,
        "vacation":  cmd_vacation,
        "history":   cmd_history,
        "debug-api": cmd_debug_api,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
