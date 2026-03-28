"""
vacation_windows.py — Vacation Mode 旅遊窗口計算引擎
======================================================
根據指定模式找出最佳出發/回程日期組合：
  - short: 5-6 天，涵蓋 1 個完整週末
  - long:  8-11 天（2 weekends）或 15-18 天（3 weekends）
可選是否必須包含台灣國定假日。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from taiwan_holidays import _get_tw_holidays


# ── 資料結構 ──────────────────────────────────────────────────────────────────

@dataclass
class VacationWindow:
    depart:         date
    ret:            date
    trip_days:      int
    weekends:       int    # full Sat+Sun pairs fully within the window
    tw_holidays:    list[str] = field(default_factory=list)
    leave_days:     int = 0   # estimated weekdays that need annual leave

    @property
    def label(self) -> str:
        hols = f"  [{', '.join(self.tw_holidays[:2])}]" if self.tw_holidays else ""
        return (
            f"{self.depart}→{self.ret}  "
            f"({self.trip_days}天 / {self.weekends}週末 / 請{self.leave_days}天假){hols}"
        )


# ── 核心工具函式 ──────────────────────────────────────────────────────────────

def _count_full_weekends(start: date, end: date) -> int:
    """計算 [start, end] 閉區間內完整的週末數（週六+週日都在範圍內才算一個）。"""
    count = 0
    d = start
    while d <= end:
        if d.weekday() == 5 and (d + timedelta(days=1)) <= end:  # Saturday, Sun also fits
            count += 1
            d += timedelta(days=7)
        else:
            d += timedelta(days=1)
    return count


def _count_leave_days(start: date, end: date, holidays: Dict[date, str]) -> int:
    """計算 [start, end] 範圍內需要請假的工作天數。"""
    return sum(
        1 for i in range((end - start).days + 1)
        if (d := start + timedelta(days=i)).weekday() < 5 and d not in holidays
    )


def _is_off_day(d: date, holidays: Dict[date, str]) -> bool:
    return d.weekday() >= 5 or d in holidays


# ── 主要生成函式 ──────────────────────────────────────────────────────────────

def find_vacation_windows(
    mode: str,                       # "short" | "long"
    horizon_days: int = 180,         # 搜尋未來幾天
    require_tw_holiday: bool = False,
    # ── 可覆蓋的長度範圍 ──────────────────────────────────────────────────
    short_days_range: Tuple[int, int] = (5, 6),
    long_days_range_2w: Tuple[int, int] = (8, 11),
    long_days_range_3w: Tuple[int, int] = (15, 18),
    from_date: Optional[date] = None,
) -> List[VacationWindow]:
    """
    生成符合條件的旅遊窗口清單。

    short mode:
      - 5-6 天，涵蓋 1 個完整週末

    long mode:
      - 8-11 天，涵蓋 2 個完整週末
      - 15-18 天，涵蓋 3 個完整週末

    require_tw_holiday:
      若 True，窗口必須包含至少一個台灣國定假日。

    回傳按出發日期排序、去重後的清單。
    """
    today     = from_date or date.today()
    end_bound = today + timedelta(days=horizon_days)

    # 收集假日
    years = set(range(today.year, end_bound.year + 1))
    all_tw_hols: Dict[date, str] = {}
    for y in years:
        all_tw_hols.update(_get_tw_holidays(y))

    windows: List[VacationWindow] = []
    seen: set[Tuple[date, date]] = set()

    # 決定要搜尋的 (min_days, max_days, required_weekends) 組合
    if mode == "short":
        search_configs = [
            (short_days_range[0], short_days_range[1], 1),
        ]
    else:  # long
        search_configs = [
            (long_days_range_2w[0], long_days_range_2w[1], 2),
            (long_days_range_3w[0], long_days_range_3w[1], 3),
        ]

    for min_d, max_d, req_weekends in search_configs:
        dep = today
        while dep <= end_bound - timedelta(days=min_d):
            for trip_len in range(min_d, max_d + 1):
                ret_date = dep + timedelta(days=trip_len - 1)
                if ret_date > end_bound:
                    break

                key = (dep, ret_date)
                if key in seen:
                    continue

                wknds = _count_full_weekends(dep, ret_date)
                if wknds < req_weekends:
                    continue

                # TW holiday filter
                hols_in = [
                    name for d, name in all_tw_hols.items()
                    if dep <= d <= ret_date
                ]
                if require_tw_holiday and not hols_in:
                    continue

                leave = _count_leave_days(dep, ret_date, all_tw_hols)

                seen.add(key)
                windows.append(VacationWindow(
                    depart=dep,
                    ret=ret_date,
                    trip_days=trip_len,
                    weekends=wknds,
                    tw_holidays=list(set(hols_in)),
                    leave_days=leave,
                ))
            dep += timedelta(days=1)

    # 去重：同一出發週同一 trip 長度只保留請假最少的
    best: Dict[Tuple[int, int, int], VacationWindow] = {}
    for w in windows:
        iso = w.depart.isocalendar()
        # key: (year, week, trip_days)
        k = (iso[0], iso[1], w.trip_days)
        if k not in best or w.leave_days < best[k].leave_days:
            best[k] = w

    result = sorted(best.values(), key=lambda w: (w.leave_days, -w.weekends, w.depart))
    return result


def print_vacation_windows(
    windows: List[VacationWindow],
    mode: str,
    top_n: int = 20,
) -> None:
    """漂亮印出旅遊窗口清單。"""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
        console = Console()
        title = f"🏖️  {'短途假期' if mode == 'short' else '長途假期'} 旅遊窗口"
        t = Table(title=title, box=box.ROUNDED, show_lines=True)
        t.add_column("#",       justify="right", style="dim",    width=3)
        t.add_column("出發日",  style="cyan",    min_width=12)
        t.add_column("回程日",  style="cyan",    min_width=12)
        t.add_column("天數",    justify="right", style="green",  width=5)
        t.add_column("週末數",  justify="right", style="yellow", width=6)
        t.add_column("請假天",  justify="right", style="magenta",width=6)
        t.add_column("包含假日",style="dim",     min_width=20)
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
                hols or "—",
            )
        console.print(t)
    except ImportError:
        print(f"\n{'='*70}")
        for i, w in enumerate(windows[:top_n], 1):
            print(f"  {i:>2}. {w.label}")
        print(f"{'='*70}\n")
