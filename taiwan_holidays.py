"""
taiwan_holidays.py — 台灣國定假日解析 & 最少請假出遊規劃
=============================================================
功能：
  1. 動態抓取台灣官方行事曆（含補假、調整放假、彈性放假）
     - 主要資料源：ruyut/TaiwanCalendar（基於行政院人事行政總處公告）
     - 本地 JSON 快取（./.cache/taiwan_holidays/{year}.json）
     - Fallback：`holidays` 套件 → 最後才用少量硬編碼保底
  2. 計算「橋接假期」(連假延伸、兩個相近假期相連)
  3. 找出最少請假天數換最多出遊天數的最佳時間窗口
  4. 自動過濾已過去的日期，預設依出發日期升冪排列
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 嘗試使用 holidays 套件（備援） ────────────────────────────────────────────
try:
    import holidays as holidays_pkg
    _HAS_HOLIDAYS_PKG = True
except ImportError:
    _HAS_HOLIDAYS_PKG = False

# ── HTTP 資料源（動態抓取） ──────────────────────────────────────────────────
try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# ruyut/TaiwanCalendar — 以政府公告行事曆為來源，每年更新，含補假/彈性放假
_REMOTE_SOURCES: list[str] = [
    "https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/{year}.json",
    "https://raw.githubusercontent.com/ruyut/TaiwanCalendar/main/data/{year}.json",
]

# 本地快取位置（置於專案底下，方便打包時一併帶走）
_CACHE_DIR = Path(__file__).parent / ".cache" / "taiwan_holidays"
_CACHE_TTL_DAYS = 30  # 快取新鮮度；過期會重新抓取，但抓不到仍可用舊檔

# ── 窗口策略常數 ─────────────────────────────────────────────────────────────
# 只推薦固定長度的「標準窗口」(9 天) + 兩個假日相鄰時的「橋接窗口」(<=17 天)。
# 彈性出發請於搜尋頁用 ±flex_days 額外處理，此檔維持收斂的推薦清單。
TRIP_DAYS        = 9    # 標準窗口天數（含兩個完整週末，涵蓋短/中假期需求）
BRIDGE_MAX_DAYS  = 17   # 橋接窗口上限；中秋(9/25)↔國慶(10/10 週六+10/11 週日) ≈ 17 天

# ── 最終 fallback：最少量硬編碼（僅在網路 & holidays 套件皆無法使用時生效）──
_HARDCODED_FALLBACK: dict[int, dict[str, str]] = {
    2026: {
        "2026-01-01": "開國紀念日",
        "2026-02-16": "農曆除夕",
        "2026-02-17": "春節",
        "2026-02-18": "春節",
        "2026-02-19": "春節",
        "2026-02-20": "春節",
        "2026-02-27": "和平紀念日（補假）",
        "2026-02-28": "和平紀念日",
        "2026-04-03": "兒童節（補假）",
        "2026-04-04": "兒童節",
        "2026-04-05": "清明節",
        "2026-04-06": "清明節（補假）",
        "2026-05-01": "勞動節",
        "2026-06-19": "端午節",
        "2026-09-25": "中秋節",
        "2026-10-09": "國慶日（彈性放假）",
        "2026-10-10": "國慶日",
    },
}


@dataclass
class HolidayWindow:
    """代表一段連假或延伸假期的時間窗口。"""
    start_date: date
    end_date:   date
    total_days: int
    leave_days: int
    free_days:  int
    holidays_included: list[str] = field(default_factory=list)
    leave_dates:       list[date] = field(default_factory=list)
    efficiency:        float      = 0.0
    is_bridge:         bool       = False

    @property
    def label(self) -> str:
        tag = " [橋接]" if self.is_bridge else ""
        return (
            f"{self.start_date.strftime('%Y-%m-%d')} ～ "
            f"{self.end_date.strftime('%Y-%m-%d')} "
            f"({self.total_days}天 / 請{self.leave_days}天假){tag}"
        )


# ── 資料來源：動態抓取 + 快取 ────────────────────────────────────────────────
def _cache_path(year: int) -> Path:
    return _CACHE_DIR / f"{year}.json"


def _read_cache(year: int) -> Optional[list[dict]]:
    p = _cache_path(year)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # noqa: BLE001
        logger.warning("讀取台灣行事曆快取失敗 %s: %s", p, exc)
        return None


def _write_cache(year: int, data: list[dict]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with _cache_path(year).open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("寫入台灣行事曆快取失敗: %s", exc)


def _cache_is_fresh(year: int) -> bool:
    p = _cache_path(year)
    if not p.exists():
        return False
    age = datetime.now().timestamp() - p.stat().st_mtime
    return age < _CACHE_TTL_DAYS * 86400


def _fetch_remote(year: int) -> Optional[list[dict]]:
    if not _HAS_REQUESTS:
        return None
    for tmpl in _REMOTE_SOURCES:
        url = tmpl.format(year=year)
        try:
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    return data
        except Exception as exc:  # noqa: BLE001
            logger.debug("抓取 %s 失敗: %s", url, exc)
    return None


def _load_taiwan_calendar(year: int) -> Optional[list[dict]]:
    """優先權：新鮮快取 → 線上抓取 → 舊快取 → None"""
    if _cache_is_fresh(year):
        cached = _read_cache(year)
        if cached:
            return cached
    remote = _fetch_remote(year)
    if remote is not None:
        _write_cache(year, remote)
        return remote
    return _read_cache(year)


def _parse_calendar_entries(entries: list[dict]) -> Dict[date, str]:
    """
    解析 ruyut/TaiwanCalendar 格式：
        {"date":"20260101","week":"四","isHoliday":true,"description":"開國紀念日"}
    僅回傳「被標記為假日」的日期。一般週末且無名稱的不會被列為命名假日，
    但補假、調整放假、彈性放假等會出現在平日，會被保留。
    """
    out: Dict[date, str] = {}
    for e in entries:
        try:
            ds = str(e.get("date", ""))
            if len(ds) != 8:
                continue
            d = date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
            if not bool(e.get("isHoliday", False)):
                continue
            desc = (e.get("description") or "").strip()
            if not desc and d.weekday() >= 5:
                continue  # 一般週末不必命名
            out[d] = desc or "假日"
        except Exception:  # noqa: BLE001
            continue
    return out


def _get_tw_holidays(year: int) -> Dict[date, str]:
    """取得指定年份的台灣國定假日（含補假 / 調整放假 / 彈性放假）。"""
    result: Dict[date, str] = {}

    entries = _load_taiwan_calendar(year)
    if entries:
        result.update(_parse_calendar_entries(entries))

    if _HAS_HOLIDAYS_PKG:
        try:
            tw = holidays_pkg.Taiwan(years=year)
            for d, name in tw.items():
                result.setdefault(d, name)
        except Exception:  # noqa: BLE001
            pass

    if not result and year in _HARDCODED_FALLBACK:
        for date_str, name in _HARDCODED_FALLBACK[year].items():
            result[date.fromisoformat(date_str)] = name

    return result


def refresh_holiday_cache(years: Optional[list[int]] = None) -> dict[int, int]:
    """強制重新抓取並更新指定年份的快取。回傳 {year: 命名假日天數}。"""
    if years is None:
        y = date.today().year
        years = [y, y + 1]
    out: dict[int, int] = {}
    for y in years:
        data = _fetch_remote(y)
        if data is not None:
            _write_cache(y, data)
            out[y] = len(_parse_calendar_entries(data))
    return out


# ── 工具函式 ──────────────────────────────────────────────────────────────────
def _is_off_day(d: date, holidays: Dict[date, str]) -> bool:
    """判斷是否為「不需上班」的日子（週六日 or 國定假日/補假）。"""
    return d.weekday() >= 5 or d in holidays


def get_off_days(start_date: date, end_date: date) -> Dict[date, str]:
    """取得指定區間內「不需上班」的日期 -> 原因說明。"""
    if end_date < start_date:
        return {}
    years = set(range(start_date.year, end_date.year + 1))
    all_holidays: Dict[date, str] = {}
    for y in years:
        all_holidays.update(_get_tw_holidays(y))

    result: Dict[date, str] = {}
    d = start_date
    while d <= end_date:
        if d in all_holidays:
            result[d] = all_holidays[d]
        elif d.weekday() >= 5:
            result[d] = "週末"
        d += timedelta(days=1)
    return result


def compute_leave_summary(start_date: date, end_date: date) -> dict:
    """計算在指定區間內上班族需請假的天數。"""
    if end_date < start_date:
        return {"leave_days": 0, "free_days": 0, "total_days": 0, "leave_dates": []}

    off = get_off_days(start_date, end_date)
    total_days = (end_date - start_date).days + 1

    leave_dates: list[date] = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5 and d not in off:
            leave_dates.append(d)
        d += timedelta(days=1)

    return {
        "leave_days":  len(leave_dates),
        "free_days":   total_days - len(leave_dates),
        "total_days":  total_days,
        "leave_dates": leave_dates,
    }


# ── 主要：尋找最佳假期窗口 ───────────────────────────────────────────────────
def _distinct_holiday_names(names: list[str]) -> list[str]:
    """
    正規化假日名稱 — 把「清明節（補假）」/「清明節」視為同一個節日，
    以便判斷「橋接」時是否連接兩個不同的假日。
    """
    norm: list[str] = []
    for n in names:
        base = n
        for sep in ("（", "("):
            if sep in base:
                base = base.split(sep)[0]
        for suf in ("補假", "補休", "調整放假", "彈性放假", "假期"):
            if base.endswith(suf):
                base = base[: -len(suf)]
        base = base.strip()
        if base and base not in norm:
            norm.append(base)
    return norm


def get_holiday_windows(
    lookahead_days: int = 365,
    from_date:      Optional[date] = None,
    include_past:   bool = False,
    **_legacy,   # 接受舊參數 (min_trip_days / max_trip_days / max_leave_days / sort_by) 以向下相容
) -> List[HolidayWindow]:
    """
    產出「圍繞國定假日」的推薦出遊窗口，只包含兩類：

    1. 標準窗口：每個國定假日一個 ``TRIP_DAYS`` (9) 天窗口，
       以最少請假天數為目標選擇最佳起始日（自動包含 1–2 個完整週末）。
    2. 橋接窗口：相鄰兩個假日 cluster 若總跨度 ≤ ``BRIDGE_MAX_DAYS`` (17)，
       額外產出一個橫跨兩者的長連假窗口（例：中秋↔國慶 約 16–17 天）。

    結果按出發日升冪排序；預設過濾已過期窗口。
    """
    today = date.today()
    scan_start = from_date or today
    scan_end   = scan_start + timedelta(days=lookahead_days)

    years = set(range(scan_start.year, scan_end.year + 1))
    all_holidays: Dict[date, str] = {}
    for y in years:
        all_holidays.update(_get_tw_holidays(y))

    clusters = _build_clusters(all_holidays, scan_start, scan_end)
    if not clusters:
        return []

    windows: List[HolidayWindow] = []

    # 1) 每個 cluster 一個標準 9 天窗口
    for cluster in clusters:
        w = _best_fixed_window(cluster, all_holidays, scan_end, TRIP_DAYS)
        if w:
            windows.append(w)

    # 2) 相鄰 cluster 之間的橋接窗口
    for i in range(len(clusters) - 1):
        c1, c2 = clusters[i], clusters[i + 1]
        span = (c2.off_end - c1.off_start).days + 1
        if TRIP_DAYS < span <= BRIDGE_MAX_DAYS:
            windows.append(_make_window(c1.off_start, c2.off_end, all_holidays, force_bridge=True))

    # 過濾 + 去重 + 依日期排序
    if not include_past:
        windows = [w for w in windows if w.end_date >= today]

    unique: dict[tuple, HolidayWindow] = {}
    for w in windows:
        unique[(w.start_date, w.end_date)] = w
    return sorted(unique.values(), key=lambda w: w.start_date)


# ── 內部輔助：cluster / 窗口建構 ─────────────────────────────────────────────
@dataclass
class _Cluster:
    """圍繞一或多個連續國定假日的 off-day 連休區塊。"""
    holidays: list[date]       # cluster 內的命名假日（依日期排序）
    off_start: date            # 連續 off-day 區塊最早日期（可能是週末）
    off_end:   date            # 連續 off-day 區塊最晚日期


def _build_clusters(
    holidays: Dict[date, str],
    scan_start: date,
    scan_end:   date,
) -> list[_Cluster]:
    """把 scan_start..scan_end 內的命名假日分群；同一 off-day 區塊共用一個 cluster。"""
    named = sorted(d for d in holidays if scan_start <= d <= scan_end)
    clusters: list[_Cluster] = []
    for h in named:
        # 展開 off-day 區塊
        s = h
        while _is_off_day(s - timedelta(days=1), holidays):
            s -= timedelta(days=1)
        e = h
        while _is_off_day(e + timedelta(days=1), holidays):
            e += timedelta(days=1)
        if clusters and clusters[-1].off_start == s:
            clusters[-1].holidays.append(h)
        else:
            clusters.append(_Cluster(holidays=[h], off_start=s, off_end=e))
    return clusters


def _make_window(
    start: date,
    end:   date,
    holidays: Dict[date, str],
    force_bridge: bool = False,
) -> HolidayWindow:
    total = (end - start).days + 1
    leave_dates: list[date] = []
    holiday_names: list[str] = []
    for i in range(total):
        d = start + timedelta(days=i)
        if d in holidays:
            holiday_names.append(holidays[d])
        elif d.weekday() < 5:
            leave_dates.append(d)

    unique_names  = list(dict.fromkeys(holiday_names))
    distinct_base = _distinct_holiday_names(unique_names)
    return HolidayWindow(
        start_date=start,
        end_date=end,
        total_days=total,
        leave_days=len(leave_dates),
        free_days=total - len(leave_dates),
        holidays_included=unique_names,
        leave_dates=leave_dates,
        efficiency=round(total / (len(leave_dates) + 1), 2),
        is_bridge=force_bridge or len(distinct_base) >= 2,
    )


def _best_fixed_window(
    cluster:   _Cluster,
    holidays:  Dict[date, str],
    scan_end:  date,
    trip_days: int,
) -> Optional[HolidayWindow]:
    """
    在 cluster 周圍找一個長度固定為 trip_days 的窗口，使請假天數最少。
    起點候選 = 能讓整個 cluster（的命名假日）完全落在窗口內的所有起點。
    平手時取 (更早起點, 更靠週末) 以利週末出發。
    """
    first_h, last_h = cluster.holidays[0], cluster.holidays[-1]
    cluster_span = (last_h - first_h).days + 1
    if cluster_span > trip_days:
        return None  # cluster 本身已超過 trip_days，用橋接處理

    # 起點範圍：最早 = last_h - (trip_days-1)，最晚 = first_h
    earliest = last_h - timedelta(days=trip_days - 1)
    latest   = first_h
    best: Optional[HolidayWindow] = None
    d = earliest
    while d <= latest:
        end_d = d + timedelta(days=trip_days - 1)
        if end_d > scan_end:
            break
        w = _make_window(d, end_d, holidays)
        # 排序鍵：最少請假 → 起點接近週五（越晚越好，方便週五出發）→ 較早日期
        key = (w.leave_days, -d.weekday(), d)
        if best is None or key < (best.leave_days, -best.start_date.weekday(), best.start_date):
            best = w
        d += timedelta(days=1)
    return best



def print_holiday_windows(windows: List[HolidayWindow], top_n: int = 20) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title="🗓️  最佳出遊時間窗口（最少請假原則）", show_lines=True)
        table.add_column("出發日", style="cyan")
        table.add_column("回程日", style="cyan")
        table.add_column("總天數", justify="right", style="green")
        table.add_column("請假天", justify="right", style="yellow")
        table.add_column("效率",   justify="right", style="magenta")
        table.add_column("類型",   justify="center", style="dim")
        table.add_column("包含假日", style="dim")

        for w in windows[:top_n]:
            hols = " / ".join(w.holidays_included[:2])
            if len(w.holidays_included) > 2:
                hols += f" +{len(w.holidays_included)-2}"
            table.add_row(
                w.start_date.strftime("%Y-%m-%d (%a)"),
                w.end_date.strftime("%Y-%m-%d (%a)"),
                str(w.total_days),
                str(w.leave_days),
                str(w.efficiency),
                "[bold]橋接[/bold]" if w.is_bridge else "連假",
                hols or "—",
            )
        console.print(table)
    except ImportError:
        print(f"\n{'='*70}")
        print(f"{'最佳出遊時間窗口':^60}")
        print(f"{'='*70}")
        for w in windows[:top_n]:
            print(f"  {w.label}  效率={w.efficiency}")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    windows = get_holiday_windows(lookahead_days=365)
    print_holiday_windows(windows, top_n=25)
