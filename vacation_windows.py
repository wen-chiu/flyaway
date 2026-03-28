"""
vacation_windows.py — Vacation Mode 旅遊窗口計算引擎
======================================================
三種假期模式（固定天數為預設，可用 --flex 開啟彈性）：
  short : 5 天  / 1 個完整週末 / 亞洲直達
  long  : 9 天  / 2 個完整週末 / 跨洲含轉機
  happy : 16 天 / 3 個完整週末 / 跨洲含轉機
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from taiwan_holidays import _get_tw_holidays


@dataclass
class VacationWindow:
    depart:      date
    ret:         date
    trip_days:   int
    weekends:    int          # full Sat+Sun pairs within window
    tw_holidays: list[str] = field(default_factory=list)
    leave_days:  int = 0      # weekdays needing annual leave
    is_flex:     bool = False  # True if days != default fixed days

    @property
    def label(self) -> str:
        flex_tag = " [彈性]" if self.is_flex else ""
        hols = f"  [{', '.join(self.tw_holidays[:2])}]" if self.tw_holidays else ""
        return (
            f"{self.depart}→{self.ret}  "
            f"({self.trip_days}天 / {self.weekends}週末 / 請{self.leave_days}天假)"
            f"{flex_tag}{hols}"
        )


# ── 工具函式 ──────────────────────────────────────────────────────────────────

def _count_full_weekends(start: date, end: date) -> int:
    """計算 [start, end] 閉區間內完整的週末數（週六+週日都在範圍內才算一個）。"""
    count = 0
    d = start
    while d <= end:
        if d.weekday() == 5 and (d + timedelta(days=1)) <= end:
            count += 1
            d += timedelta(days=7)
        else:
            d += timedelta(days=1)
    return count


def _count_leave_days(start: date, end: date, holidays: Dict[date, str]) -> int:
    return sum(
        1 for i in range((end - start).days + 1)
        if (d := start + timedelta(days=i)).weekday() < 5 and d not in holidays
    )


def _collect_holidays(from_date: date, to_date: date) -> Dict[date, str]:
    years = set(range(from_date.year, to_date.year + 1))
    hols: Dict[date, str] = {}
    for y in years:
        hols.update(_get_tw_holidays(y))
    return hols


# ── 主要生成函式 ──────────────────────────────────────────────────────────────

def find_vacation_windows(
    mode:                 str,
    horizon_days:         int  = 180,
    require_tw_holiday:   bool = False,
    # Override fixed days (normally leave as None to use mode defaults)
    fixed_days_override:  Optional[int] = None,
    # Enable flexible days: search fixed±flex_days as well
    flex_days_override:   Optional[int] = None,
    from_date:            Optional[date] = None,
) -> List[VacationWindow]:
    """
    找出符合條件的旅遊窗口。

    fixed_days_override: 若給定，覆蓋模式預設的固定天數
    flex_days_override:  若給定，覆蓋模式預設的彈性天數
                         設為 0 = 只搜尋固定天數（更聚焦）
                         設為 >0 = 也搜尋 fixed±N 天
    """
    from config import VACATION_MODES

    cfg = VACATION_MODES.get(mode)
    if not cfg:
        raise ValueError(f"未知的假期模式: {mode}. 有效選項: {list(VACATION_MODES)}")

    fixed_days  = fixed_days_override  if fixed_days_override is not None  else cfg["days"]
    flex_days   = flex_days_override   if flex_days_override  is not None  else 0
    req_weekends = cfg["weekends"]

    today     = from_date or date.today()
    end_bound = today + timedelta(days=horizon_days)
    all_hols  = _collect_holidays(today, end_bound)

    # Build the set of trip lengths to search:
    # Primary: fixed_days
    # With flex: fixed_days ± flex_days
    if flex_days > 0:
        trip_lens = list(range(max(1, fixed_days - flex_days), fixed_days + flex_days + 1))
    else:
        trip_lens = [fixed_days]

    windows: List[VacationWindow] = []
    seen: set[Tuple[date, date]] = set()

    dep = today
    while dep <= end_bound - timedelta(days=min(trip_lens)):
        for trip_len in trip_lens:
            ret_date = dep + timedelta(days=trip_len - 1)
            if ret_date > end_bound:
                continue

            key = (dep, ret_date)
            if key in seen:
                continue

            wknds = _count_full_weekends(dep, ret_date)
            if wknds < req_weekends:
                continue

            hols_in = [
                name for d, name in all_hols.items()
                if dep <= d <= ret_date
            ]
            if require_tw_holiday and not hols_in:
                continue

            leave   = _count_leave_days(dep, ret_date, all_hols)
            is_flex = (trip_len != fixed_days)

            seen.add(key)
            windows.append(VacationWindow(
                depart=dep,
                ret=ret_date,
                trip_days=trip_len,
                weekends=wknds,
                tw_holidays=list(set(hols_in)),
                leave_days=leave,
                is_flex=is_flex,
            ))
        dep += timedelta(days=1)

    # De-duplicate: per (ISO week, trip_days) keep lowest leave_days
    best: Dict[Tuple[int, int, int], VacationWindow] = {}
    for w in windows:
        iso = w.depart.isocalendar()
        k   = (iso[0], iso[1], w.trip_days)
        if k not in best or w.leave_days < best[k].leave_days:
            best[k] = w

    # Sort: fixed days first, then by leave_days asc, then by depart date
    result = sorted(
        best.values(),
        key=lambda w: (w.is_flex, w.leave_days, -w.weekends, w.depart),
    )
    return result


def print_vacation_windows(
    windows:  List[VacationWindow],
    mode:     str,
    top_n:    int = 20,
) -> None:
    from config import VACATION_MODES
    mode_label = VACATION_MODES.get(mode, {}).get("label", mode)

    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
        console = Console()
        t = Table(
            title=f"{mode_label}  旅遊窗口",
            box=box.ROUNDED, show_lines=True,
        )
        t.add_column("#",       justify="right", style="dim",     width=3)
        t.add_column("出發日",  style="cyan",    min_width=14)
        t.add_column("回程日",  style="cyan",    min_width=14)
        t.add_column("天數",    justify="right", style="green",   width=5)
        t.add_column("週末",    justify="right", style="yellow",  width=5)
        t.add_column("請假天",  justify="right", style="magenta", width=6)
        t.add_column("類型",    justify="center", style="dim",    width=5)
        t.add_column("包含假日", style="dim",    min_width=16)
        for i, w in enumerate(windows[:top_n], 1):
            hols = " / ".join(w.tw_holidays[:2])
            if len(w.tw_holidays) > 2:
                hols += f" +{len(w.tw_holidays)-2}"
            t.add_row(
                str(i),
                w.depart.strftime("%Y-%m-%d (%a)"),
                w.ret.strftime("%Y-%m-%d (%a)"),
                str(w.trip_days),
                str(w.weekends),
                str(w.leave_days),
                "[dim]彈性[/dim]" if w.is_flex else "[bold]固定[/bold]",
                hols or "—",
            )
        console.print(t)
    except ImportError:
        print(f"\n{'='*65}")
        print(f"  {mode_label} 旅遊窗口")
        print(f"{'='*65}")
        for i, w in enumerate(windows[:top_n], 1):
            tag = " [彈性]" if w.is_flex else ""
            print(f"  {i:>2}. {w.label}{tag}")
        print(f"{'='*65}\n")