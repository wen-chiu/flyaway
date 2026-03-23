"""
taiwan_holidays.py — 台灣國定假日解析 & 最少請假出遊規劃
=============================================================
功能：
  1. 抓取台灣國定假日（含農曆動態假日）
  2. 計算「橋接假期」(連假延伸)
  3. 找出最少請假天數換最多出遊天數的最佳時間窗口
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

# ── 嘗試使用 holidays 套件 ────────────────────────────────────────────────────
try:
    import holidays as holidays_pkg
    _HAS_HOLIDAYS_PKG = True
except ImportError:
    _HAS_HOLIDAYS_PKG = False

# ── 硬編碼台灣假日（做為備用 & 補充農曆假日）─────────────────────────────────
_HARDCODED: dict[int, dict[str, str]] = {
    2026: {
        "2026-01-01": "元旦 New Year's Day",
        "2026-02-16": "農曆除夕 Lunar New Year's Eve",
        "2026-02-17": "農曆初一 Lunar New Year (Day 1)",
        "2026-02-18": "農曆初二 Lunar New Year (Day 2)",
        "2026-02-19": "農曆初三 Lunar New Year (Day 3)",
        "2026-02-20": "農曆初四 Lunar New Year (Day 4)",
        "2026-02-28": "和平紀念日 Peace Memorial Day",
        "2026-04-05": "清明節 Tomb Sweeping Day",
        "2026-04-04": "兒童節 Children's Day",
        "2026-05-01": "勞動節 Labor Day",
        "2026-06-19": "端午節 Dragon Boat Festival",
        "2026-09-25": "中秋節 Mid-Autumn Festival",
        "2026-10-10": "國慶日 National Day",
        "2026-10-25": "光復節 ",
        "2026-12-25": "Christmas ",
    },
}


@dataclass
class HolidayWindow:
    """代表一段連假或延伸假期的時間窗口"""
    start_date: date
    end_date: date
    total_days: int
    leave_days: int           # 需要請幾天假
    free_days: int            # 免費放假天數（含例假日 & 國定假日）
    holidays_included: list[str] = field(default_factory=list)
    efficiency: float = 0.0   # total_days / (leave_days + 1)，越高越值錢

    @property
    def label(self) -> str:
        return (f"{self.start_date.strftime('%Y-%m-%d')} ～ "
                f"{self.end_date.strftime('%Y-%m-%d')} "
                f"({self.total_days}天 / 請{self.leave_days}天假)")


def _get_tw_holidays(year: int) -> Dict[date, str]:
    """取得指定年份的台灣國定假日。"""
    result: Dict[date, str] = {}

    # 1. 使用 holidays 套件（如果有安裝）
    if _HAS_HOLIDAYS_PKG:
        try:
            tw = holidays_pkg.Taiwan(years=year)
            for d, name in tw.items():
                result[d] = name
        except Exception:
            pass

    # 2. 補充 / 覆蓋硬編碼的農曆假日
    if year in _HARDCODED:
        for date_str, name in _HARDCODED[year].items():
            d = date.fromisoformat(date_str)
            result[d] = name

    return result


def _is_off_day(d: date, holidays: Dict[date, str]) -> bool:
    """判斷是否為「不需上班」的日子（週六日 or 國定假日）。"""
    return d.weekday() >= 5 or d in holidays


def get_holiday_windows(
    lookahead_days: int = 270,
    min_trip_days:  int = 4,
    max_trip_days:  int = 16,
    from_date: Optional[date] = None,
) -> List[HolidayWindow]:
    """
    分析未來 lookahead_days 天內，
    找出所有「最少請假 / 最多出遊」的黃金時間窗口。

    Returns:
        按出發日期排序的 HolidayWindow 清單
    """
    start = from_date or date.today()
    end   = start + timedelta(days=lookahead_days)

    # 收集所有年份的假日
    years = set(range(start.year, end.year + 1))
    all_holidays: Dict[date, str] = {}
    for y in years:
        all_holidays.update(_get_tw_holidays(y))

    # 找出每個可能的出發日期的「連休塊」
    windows: List[HolidayWindow] = []
    seen_starts: set[date] = set()

    current = start
    while current <= end - timedelta(days=min_trip_days):
        # 找到以 current 為起始點的最大連休塊
        block_start = current
        # 從 block_start 往前找（若前面也是假期，併入）
        s = block_start
        while s > start and _is_off_day(s - timedelta(days=1), all_holidays):
            s -= timedelta(days=1)
        block_start = s

        if block_start in seen_starts:
            current += timedelta(days=1)
            continue

        # 往後延伸，加上請假日
        for leave_budget in range(0, 10):          # 最多允許請 4 天假
            # 先找到現有假期塊結尾
            e = block_start
            while e <= end and _is_off_day(e, all_holidays):
                e += timedelta(days=1)
            block_end_natural = e - timedelta(days=1)

            # 嘗試在末尾加請假
            extra_leave = 0
            e = block_end_natural + timedelta(days=1)
            while extra_leave < leave_budget and e <= end:
                if not _is_off_day(e, all_holidays):
                    extra_leave += 1
                    # 再往後看有沒有接著的假期
                    e += timedelta(days=1)
                    while e <= end and _is_off_day(e, all_holidays):
                        e += timedelta(days=1)
                else:
                    e += timedelta(days=1)

            block_end = e - timedelta(days=1)
            total = (block_end - block_start).days + 1

            # 計算實際請假天數
            actual_leave = sum(
                1 for i in range(total)
                if not _is_off_day(block_start + timedelta(days=i), all_holidays)
            )

            if min_trip_days <= total <= max_trip_days and actual_leave == leave_budget:
                included = [
                    name for d, name in all_holidays.items()
                    if block_start <= d <= block_end
                ]
                eff = total / (actual_leave + 1) if actual_leave >= 0 else total
                windows.append(HolidayWindow(
                    start_date=block_start,
                    end_date=block_end,
                    total_days=total,
                    leave_days=actual_leave,
                    free_days=total - actual_leave,
                    holidays_included=list(set(included)),
                    efficiency=round(eff, 2),
                ))

        seen_starts.add(block_start)
        current = block_start + timedelta(days=1)

    # 去重 & 排序：先按請假天數升序，再按效率降序
    unique: dict[tuple, HolidayWindow] = {}
    for w in windows:
        key = (w.start_date, w.end_date)
        if key not in unique or w.efficiency > unique[key].efficiency:
            unique[key] = w

    result = sorted(unique.values(), key=lambda w: (w.leave_days, -w.efficiency, w.start_date))
    return result


def print_holiday_windows(windows: List[HolidayWindow], top_n: int = 15) -> None:
    """用 Rich 表格漂亮印出假期窗口。"""
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title="🗓️  最佳出遊時間窗口（最少請假原則）", show_lines=True)
        table.add_column("出發日", style="cyan")
        table.add_column("回程日", style="cyan")
        table.add_column("總天數", justify="right", style="green")
        table.add_column("請假天", justify="right", style="yellow")
        table.add_column("效率指數", justify="right", style="magenta")
        table.add_column("包含假日", style="dim")

        for w in windows[:top_n]:
            hols = " / ".join(w.holidays_included[:2])
            if len(w.holidays_included) > 2:
                hols += f" +{len(w.holidays_included)-2}個"
            table.add_row(
                w.start_date.strftime("%Y-%m-%d (%a)"),
                w.end_date.strftime("%Y-%m-%d (%a)"),
                str(w.total_days),
                str(w.leave_days),
                str(w.efficiency),
                hols,
            )
        console.print(table)
    except ImportError:
        # Fallback 純文字
        print(f"\n{'='*70}")
        print(f"{'最佳出遊時間窗口':^60}")
        print(f"{'='*70}")
        for w in windows[:top_n]:
            print(f"  {w.label}  效率={w.efficiency}")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    windows = get_holiday_windows(lookahead_days=365, min_trip_days=3)
    print_holiday_windows(windows, top_n=20)
