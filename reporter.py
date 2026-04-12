"""
reporter.py — 結果顯示與報告產生
====================================
傳統航空 vs 廉航分兩表顯示，支援來回票去程與回程完整資訊。
每筆航班附帶訂票連結：
  - CLI：表格中「訂票連結」欄 + 完整 URL 標籤
  - CSV：Google Flights 欄 + 航空公司直售欄（若有）

回程資訊顯示規則：
  - 只要有任一筆記錄的 is_roundtrip=True 或 return_date 有值，就顯示回程欄位
  - 回程時間若 API 未回傳則顯示 "—"，但回程日期一定顯示
  - 回程時間欄直接呼叫 _fmt_time()，空值自動回傳 "—"
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import REPORT_DIR, TOP_N_RESULTS
from database import FlightRecord
from booking_links import BookingLinkFactory, format_links_plain, format_links_rich

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    _HAS_RICH = True
    console = Console()
except ImportError:
    _HAS_RICH = False
    console = None

# ── 目的地對照 ────────────────────────────────────────────────────────────────
REGION_MAP = {
    "NRT": "東京(成田)", "HND": "東京(羽田)", "KIX": "大阪",
    "NGO": "名古屋",     "CTS": "札幌",       "FUK": "福岡",
    "HKD": "函館",       "AKJ": "旭川",       "SDJ": "仙台",
    "HNA": "花卷",       "AXT": "秋田",       "FKS": "福島",
    "KMQ": "小松",       "HSG": "佐賀",       "KMJ": "熊本",
    "KOJ": "鹿兒島",     "OKJ": "岡山",       "TAK": "高松",
    "HIJ": "廣島",       "KCZ": "高知",       "OKA": "沖繩(那霸)",
    "MYJ": "松山",       "OIT": "大分",       "UKB": "神戶",
    "IBR": "茨城",
    "ICN": "首爾(仁川)", "GMP": "首爾(金浦)", "PUS": "釜山",
    "CJU": "濟州島",     "TAE": "大邱",       "CJJ": "清州",
    "HKG": "香港",       "MFM": "澳門",
    "BKK": "曼谷(素旺那普)", "DMK": "曼谷(廊曼)",
    "SIN": "新加坡",     "KUL": "吉隆坡",     "MNL": "馬尼拉",
    "CGK": "雅加達",     "DPS": "峇里島",     "HAN": "河內",
    "SGN": "胡志明市",   "RGN": "仰光",       "REP": "暹粒",
    "PNH": "金邊",       "VTE": "永珍",       "MDL": "曼德勒",
    "CNX": "清邁",       "PQC": "富國島",     "DAD": "峴港",
    "PEN": "檳城",       "CEB": "宿霧",
    "DEL": "新德里",     "BOM": "孟買",       "MAA": "清奈",
    "BLR": "班加羅爾",   "CMB": "可倫坡",     "KTM": "加德滿都",
    "DAC": "達卡",
    "DXB": "杜拜",       "DOH": "多哈",       "AUH": "阿布達比",
    "RUH": "利雅德",     "KWI": "科威特",     "AMM": "安曼",
    "BEY": "貝魯特",
    "LHR": "倫敦",       "CDG": "巴黎",       "FRA": "法蘭克福",
    "AMS": "阿姆斯特丹", "MAD": "馬德里",     "FCO": "羅馬",
    "BCN": "巴塞隆納",   "VIE": "維也納",     "ZRH": "蘇黎世",
    "IST": "伊斯坦堡",   "PRG": "布拉格",     "WAW": "華沙",
    "ARN": "斯德哥爾摩", "CPH": "哥本哈根",   "HEL": "赫爾辛基",
    "ATH": "雅典",       "LIS": "里斯本",     "DUB": "都柏林",
    "JFK": "紐約",       "LAX": "洛杉磯",     "SFO": "舊金山",
    "ORD": "芝加哥",     "SEA": "西雅圖",     "DFW": "達拉斯",
    "MIA": "邁阿密",     "BOS": "波士頓",     "YVR": "溫哥華",
    "YYZ": "多倫多",     "IAH": "休士頓",     "ONT": "安大略(加州)",
    "SYD": "雪梨",       "MEL": "墨爾本",     "BNE": "布里斯本",
    "PER": "伯斯",       "AKL": "奧克蘭",     "ROR": "帛琉",
    "NBO": "奈洛比",     "JNB": "約翰尼斯堡", "CAI": "開羅",
    "CMN": "卡薩布蘭卡", "ADD": "阿迪斯阿貝巴",
    "GRU": "聖保羅",     "EZE": "布宜諾斯艾利斯",
    "BOG": "波哥大",     "LIM": "利馬",       "SCL": "聖地牙哥",
    "TPE": "台北(桃園)", "TSA": "台北(松山)",
}

FLAG_MAP = {
    "NRT": "🇯🇵", "HND": "🇯🇵", "KIX": "🇯🇵", "NGO": "🇯🇵", "CTS": "🇯🇵",
    "FUK": "🇯🇵", "HKD": "🇯🇵", "AKJ": "🇯🇵", "SDJ": "🇯🇵", "HNA": "🇯🇵",
    "AXT": "🇯🇵", "FKS": "🇯🇵", "KMQ": "🇯🇵", "HSG": "🇯🇵", "KMJ": "🇯🇵",
    "KOJ": "🇯🇵", "OKJ": "🇯🇵", "TAK": "🇯🇵", "HIJ": "🇯🇵", "KCZ": "🇯🇵",
    "OKA": "🇯🇵", "MYJ": "🇯🇵", "OIT": "🇯🇵", "UKB": "🇯🇵", "IBR": "🇯🇵",
    "ICN": "🇰🇷", "GMP": "🇰🇷", "PUS": "🇰🇷", "CJU": "🇰🇷", "TAE": "🇰🇷",
    "CJJ": "🇰🇷",
    "HKG": "🇭🇰", "MFM": "🇲🇴",
    "BKK": "🇹🇭", "DMK": "🇹🇭", "CNX": "🇹🇭",
    "SIN": "🇸🇬",
    "KUL": "🇲🇾", "PEN": "🇲🇾",
    "MNL": "🇵🇭", "CEB": "🇵🇭",
    "CGK": "🇮🇩", "DPS": "🇮🇩",
    "HAN": "🇻🇳", "SGN": "🇻🇳", "DAD": "🇻🇳", "PQC": "🇻🇳",
    "RGN": "🇲🇲", "MDL": "🇲🇲",
    "REP": "🇰🇭", "PNH": "🇰🇭",
    "VTE": "🇱🇦",
    "DEL": "🇮🇳", "BOM": "🇮🇳", "MAA": "🇮🇳", "BLR": "🇮🇳",
    "CMB": "🇱🇰", "KTM": "🇳🇵", "DAC": "🇧🇩",
    "DXB": "🇦🇪", "AUH": "🇦🇪", "DOH": "🇶🇦", "RUH": "🇸🇦", "KWI": "🇰🇼",
    "AMM": "🇯🇴", "BEY": "🇱🇧",
    "LHR": "🇬🇧", "CDG": "🇫🇷", "FRA": "🇩🇪", "AMS": "🇳🇱", "MAD": "🇪🇸",
    "FCO": "🇮🇹", "BCN": "🇪🇸", "VIE": "🇦🇹", "ZRH": "🇨🇭", "IST": "🇹🇷",
    "PRG": "🇨🇿", "WAW": "🇵🇱", "ARN": "🇸🇪", "CPH": "🇩🇰", "HEL": "🇫🇮",
    "ATH": "🇬🇷", "LIS": "🇵🇹", "DUB": "🇮🇪",
    "JFK": "🇺🇸", "LAX": "🇺🇸", "SFO": "🇺🇸", "ORD": "🇺🇸", "SEA": "🇺🇸",
    "DFW": "🇺🇸", "MIA": "🇺🇸", "BOS": "🇺🇸", "IAH": "🇺🇸", "ONT": "🇺🇸",
    "YVR": "🇨🇦", "YYZ": "🇨🇦",
    "SYD": "🇦🇺", "MEL": "🇦🇺", "BNE": "🇦🇺", "PER": "🇦🇺", "AKL": "🇳🇿",
    "ROR": "🇵🇼",
    "NBO": "🇰🇪", "JNB": "🇿🇦", "CAI": "🇪🇬", "CMN": "🇲🇦", "ADD": "🇪🇹",
    "GRU": "🇧🇷", "EZE": "🇦🇷", "BOG": "🇨🇴", "LIM": "🇵🇪", "SCL": "🇨🇱",
    "TPE": "🇹🇼", "TSA": "🇹🇼",
}


def dest_label(code: str) -> str:
    code = code.upper()
    flag = FLAG_MAP.get(code, "")
    name = REGION_MAP.get(code, code)
    return f"{flag} {name}" if flag else name


def format_price(price: float, currency: str = "") -> str:
    symbols = {
        "TWD": "NT$", "USD": "$",    "EUR": "€",    "GBP": "£",
        "JPY": "¥",   "MYR": "MYR ", "SGD": "S$",  "HKD": "HK$",
    }
    sym = symbols.get((currency or "").upper(), f"{currency} " if currency else "")
    if (currency or "").upper() in ("JPY", "TWD", "KRW", "IDR", "VND"):
        return f"{sym}{int(price):,}"
    return f"{sym}{price:,.0f}"


def format_duration(minutes: int) -> str:
    if minutes <= 0:
        return "—"
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m"


def _fmt_time(dep: str, arr: str) -> str:
    """
    縮短時間字串，只保留時:分格式。
    若兩者皆空則回傳 "—"。
    """
    if not dep and not arr:
        return "—"

    def extract_time(s: str) -> str:
        m = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM)?)", s, re.I)
        return m.group(1).strip() if m else s[:12]

    d = extract_time(dep) if dep else "?"
    a = extract_time(arr) if arr else "?"
    ahead = ""
    if "+1" in (arr or ""):
        ahead = " +1d"
    elif "+2" in (arr or ""):
        ahead = " +2d"
    return f"{d} → {a}{ahead}"


def _print(msg: str) -> None:
    if _HAS_RICH:
        console.print(msg)
    else:
        print(msg)


# ══════════════════════════════════════════════════════════════════════════════
# 主要輸出函式
# ══════════════════════════════════════════════════════════════════════════════

def print_results(
    records: List[FlightRecord],
    title: str = "機票搜尋結果",
    top_n: int = TOP_N_RESULTS,
    split_lcc: bool = True,
    group_by_date: bool = False,
) -> None:
    """
    印出機票結果。
    split_lcc=True    : 傳統航空 & 廉航各自一張表
    group_by_date=True: 先按出發日期分組，每組再分傳統/廉航（彈性日期搜尋用）
    """
    if not records:
        _print("⚠️ 沒有找到符合條件的機票。")
        return

    records = sorted(records, key=lambda r: r.price)

    if group_by_date:
        _print_by_date(records, title, top_n, split_lcc)
        return

    if split_lcc:
        traditional = [r for r in records if r.airline_type == "traditional"]
        lcc         = [r for r in records if r.airline_type == "LCC"]
        unknown     = [r for r in records if r.airline_type not in ("traditional", "LCC")]

        if traditional:
            _render_table(traditional[:top_n],
                          title=f"✈ {title} — 傳統航空",
                          header_style="bold blue")
        if lcc:
            _render_table(lcc[:top_n],
                          title=f"💸 {title} — 廉航",
                          header_style="bold yellow")
        if unknown:
            # P2 FIX: always render unknown rows in their own table.
            # Previous code extended an already-rendered classified list with
            # unknown rows and re-rendered it, duplicating every classified fare.
            if traditional or lcc:
                _render_table(unknown[:top_n],
                              title=f"✈ {title} — 未分類航空",
                              header_style="bold cyan")
            else:
                _render_table(unknown[:top_n],
                              title=f"✈ {title}",
                              header_style="bold cyan")
    else:
        _render_table(records[:top_n], title)


def _print_by_date(
    records: List[FlightRecord],
    title: str,
    top_n: int,
    split_lcc: bool,
) -> None:
    """按出發日期分組，每組再分傳統/廉航顯示。"""
    by_date: Dict[str, List[FlightRecord]] = defaultdict(list)
    for r in records:
        by_date[r.departure_date].append(r)

    for dep_date in sorted(by_date.keys()):
        group = sorted(by_date[dep_date], key=lambda r: r.price)
        if not split_lcc:
            _render_table(group[:top_n], f"{title}  📅 {dep_date}")
            continue
        traditional = [r for r in group if r.airline_type == "traditional"]
        lcc         = [r for r in group if r.airline_type == "LCC"]
        unknown     = [r for r in group if r.airline_type not in ("traditional", "LCC")]
        if traditional:
            _render_table(traditional[:top_n], f"✈  {title}  📅 {dep_date} — 傳統航空",
                          header_style="bold blue")
        if lcc:
            _render_table(lcc[:top_n], f"💸 {title}  📅 {dep_date} — 廉航",
                          header_style="bold yellow")
        if unknown:
            # P2 FIX: was `if unknown and not traditional and not lcc:` which
            # silently dropped all unknown-airline fares whenever classified
            # rows existed in the same date group.
            if traditional or lcc:
                _render_table(unknown[:top_n],
                              f"✈  {title}  📅 {dep_date} — 未分類航空",
                              header_style="bold cyan")
            else:
                _render_table(unknown[:top_n],
                              f"✈  {title}  📅 {dep_date}",
                              header_style="bold cyan")


def _render_table(
    records: List[FlightRecord],
    title: str,
    header_style: str = "bold",
) -> None:
    """
    核心渲染函式。

    回程欄位顯示規則（BUG FIX）：
    ─────────────────────────────
    原本用 is_rt = any(r.is_roundtrip ...) 判斷是否顯示回程欄；
    當 API 只返回去程資料時 is_roundtrip 被設為 False，導致回程欄消失。

    修正：只要任一筆記錄有 return_date 或 is_roundtrip=True，就顯示回程欄。
    回程時間直接呼叫 _fmt_time()，若時間為空自動回傳 "—"，
    不再用全域 flag 控制整欄內容，_fmt_time 在時間為空時自動回傳 "—"。
    """
    if not records:
        return

    # Show return columns if ANY record is roundtrip OR has a return date set.
    # Previously `any(r.is_roundtrip ...)` caused return columns to disappear
    # when a leg returned no flights (is_roundtrip was forced to False).
    is_rt = any(r.is_roundtrip or bool(r.return_date) for r in records)

    link_sets = [BookingLinkFactory.from_record(r) for r in records]

    if _HAS_RICH:
        t = Table(
            title=title,
            box=box.ROUNDED,
            show_lines=True,
            highlight=True,
            header_style=header_style,
        )
        t.add_column("#",        justify="right",  style="dim",          width=3)
        t.add_column("目的地",   style="cyan",     min_width=12)
        t.add_column("去程日",   style="white",    min_width=10)
        t.add_column("去程時間", style="green",    min_width=15)
        t.add_column("去程時長", justify="right",  style="yellow",       min_width=7)
        if is_rt:
            t.add_column("回程日",   style="white",    min_width=10)
            t.add_column("回程時間", style="green",    min_width=15)
            t.add_column("回程時長", justify="right",  style="yellow",   min_width=7)
        t.add_column("轉機",     justify="center", style="magenta",      width=6)
        t.add_column("航空公司", style="dim",      min_width=14)
        t.add_column("來回總價" if is_rt else "票價",
                     justify="right", style="bold green", min_width=12)
        t.add_column("訂票連結", style="blue",     min_width=16)

        for i, (r, ls) in enumerate(zip(records, link_sets), 1):
            out_time = _fmt_time(r.departure_time, r.arrival_time)
            row = [
                str(i),
                dest_label(r.arrival_airport),
                r.departure_date,
                out_time,
                format_duration(r.duration_minutes),
            ]
            if is_rt:
                # Always show return date; _fmt_time returns "—" when time is empty
                ret_time = _fmt_time(r.return_dep_time, r.return_arr_time)
                row += [
                    r.return_date or "—",
                    ret_time,
                    format_duration(r.return_duration),
                ]
            row += [r.stops_str, r.airline or "—", format_price(r.price, r.currency)]
            row.append(format_links_rich(ls) if ls else "—")
            t.add_row(*row)

        console.print(t)
        console.print(f"  [dim]資料更新時間：{records[0].fetched_at[:19]}[/dim]\n")

    else:
        print(f"\n{'='*100}")
        print(f"  {title}")
        print(f"{'='*100}")
        for i, (r, ls) in enumerate(zip(records, link_sets), 1):
            ret_info = f" ↩{r.return_date}" if r.return_date else ""
            ret_time = (
                f"  回:{_fmt_time(r.return_dep_time, r.return_arr_time)}"
                if is_rt else ""
            )
            print(
                f"{i:>3}  {dest_label(r.arrival_airport):<16} "
                f"去:{r.departure_date} {_fmt_time(r.departure_time, r.arrival_time)}"
                f"{ret_info}{ret_time}"
                f"  {r.stops_str:>5}  {r.airline:<16}  "
                f"{format_price(r.price, r.currency):>12}"
            )
            for line in format_links_plain(ls):
                print(f"       {line}")
        print(f"{'='*100}\n")


def print_vacation_summary(
    all_records: List[FlightRecord],
    mode_label: str,
    top_n: int = 15,
) -> None:
    """
    Vacation Mode 專用：跨所有日期的總排行榜（傳統/廉航分開）。
    """
    if not all_records:
        _print("⚠️  無資料可顯示。")
        return

    records     = sorted(all_records, key=lambda r: r.price)
    traditional = [r for r in records if r.airline_type == "traditional"]
    lcc         = [r for r in records if r.airline_type == "LCC"]
    unknown     = [r for r in records if r.airline_type not in ("traditional", "LCC")]

    if _HAS_RICH:
        console.print(
            f"\n[bold magenta]{'═'*55}[/bold magenta]\n"
            f"[bold magenta]  🏆 {mode_label}  全期間最低票價總排行[/bold magenta]\n"
            f"[bold magenta]{'═'*55}[/bold magenta]"
        )
        if traditional:
            _summary_table(traditional, f"✈  {mode_label} — 傳統航空 總排行", top_n)
        if lcc:
            _summary_table(lcc,         f"💸 {mode_label} — 廉航 總排行",       top_n)
        if unknown:
            title = f"✈  {mode_label} 總排行" if not (traditional or lcc) else f"✈  {mode_label} — 未分類航空 總排行"
            _summary_table(unknown, title, top_n)
    else:
        all_typed = traditional + lcc + unknown
        print(f"\n=== {mode_label} 全期間最低票價 ===")
        for i, r in enumerate(all_typed[:top_n], 1):
            ret_info = f"↩{r.return_date}" if r.return_date else "—"
            print(
                f"  {i:>2}. {r.departure_date} {ret_info}  "
                f"{dest_label(r.arrival_airport):<16}  "
                f"{r.airline:<16}  {format_price(r.price, r.currency)}"
            )


def _summary_table(recs: List[FlightRecord], title: str, top_n: int) -> None:
    """Vacation summary 精簡表格（Rich only）。"""
    if not recs or not _HAS_RICH:
        return
    t = Table(title=title, box=box.ROUNDED, show_lines=True, highlight=True)
    t.add_column("#",        justify="right",  style="dim",        width=3)
    t.add_column("去程日",   style="cyan",     min_width=10)
    t.add_column("去程時間", style="green",    min_width=14)
    t.add_column("回程日",   style="cyan",     min_width=10)
    t.add_column("回程時間", style="green",    min_width=14)
    t.add_column("目的地",   style="green",    min_width=12)
    t.add_column("轉機",     justify="center", style="magenta",    width=6)
    t.add_column("航空公司", style="dim",      min_width=14)
    t.add_column("來回總價", justify="right",  style="bold green", min_width=12)
    t.add_column("訂票連結", style="blue",     min_width=14)

    for i, r in enumerate(recs[:top_n], 1):
        out_t = _fmt_time(r.departure_time, r.arrival_time)
        # Always show return time; _fmt_time returns "—" when empty
        ret_t = _fmt_time(r.return_dep_time, r.return_arr_time)
        try:
            link_str = format_links_rich(BookingLinkFactory.from_record(r))
        except Exception:
            link_str = "—"
        t.add_row(
            str(i),
            r.departure_date,
            out_t,
            r.return_date or "—",
            ret_t,
            dest_label(r.arrival_airport),
            r.stops_str,
            r.airline or "—",
            format_price(r.price, r.currency),
            link_str,
        )
    console.print(t)


# ══════════════════════════════════════════════════════════════════════════════
# CSV 匯出
# ══════════════════════════════════════════════════════════════════════════════

def export_csv(
    records:  List[FlightRecord],
    filename: Optional[str] = None,
) -> Path:
    """
    匯出 CSV。
    欄位包含完整去程與回程資訊（日期、時間、時長）及兩種訂票連結。
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not filename:
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"flights_{ts}.csv"
    path = REPORT_DIR / filename

    sorted_records = sorted(records, key=lambda x: x.price)
    link_sets      = [BookingLinkFactory.from_record(r) for r in sorted_records]

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "排名", "票種", "航空類型",
            "目的地代碼", "目的地",
            "出發機場",
            "去程日", "去程出發時間", "去程抵達時間", "去程時長(分)", "轉機",
            "回程日", "回程出發時間", "回程抵達時間", "回程時長(分)",
            "航空公司", "航班號", "票價", "幣別", "資料時間",
            "Google Flights 連結",
            "航空官網連結",
        ])
        for i, (r, ls) in enumerate(zip(sorted_records, link_sets), 1):
            google_url  = ls.google_link.url      if ls.google_link      else ""
            airline_url = ls.airline_links[0].url if ls.airline_links    else ""
            writer.writerow([
                i,
                "來回" if r.is_roundtrip else "單程",
                r.airline_type or "unknown",
                r.arrival_airport, dest_label(r.arrival_airport),
                r.departure_airport,
                r.departure_date, r.departure_time, r.arrival_time,
                r.duration_minutes, r.stops_str,
                r.return_date or "",
                r.return_dep_time or "",
                r.return_arr_time or "",
                r.return_duration or "",
                r.airline, r.flight_numbers,
                r.price, r.currency, r.fetched_at[:19],
                google_url,
                airline_url,
            ])

    _print(f"[green]✓ CSV 已儲存：{path}[/green]" if _HAS_RICH else f"✓ CSV 已儲存：{path}")
    return path
