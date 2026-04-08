"""
reporter.py — 結果顯示與報告產生
=====================================
傳統航空 vs 廉航分兩表顯示。
表格包含訂票連結欄位。
Vacation Mode 支援按日期分組顯示。
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import REPORT_DIR, TOP_N_RESULTS
from database import FlightRecord

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
    "NRT":"東京(成田)", "HND":"東京(羽田)", "KIX":"大阪",
    "NGO":"名古屋",     "CTS":"札幌",       "FUK":"福岡",
    "HKD":"函館",       "AKJ":"旭川",       "SDJ":"仙台",
    "HNA":"花卷",       "AXT":"秋田",       "FKS":"福島",
    "KMQ":"小松",       "HSG":"佐賀",       "KMJ":"熊本",
    "KOJ":"鹿兒島",     "OKJ":"岡山",       "TAK":"高松",
    "HIJ":"廣島",       "KCZ":"高知",       "OKA":"沖繩(那霸)",
    "MYJ":"松山",       "OIT":"大分",       "UKB":"神戶",
    "IBR":"茨城",
    "ICN":"首爾(仁川)", "GMP":"首爾(金浦)", "PUS":"釜山",
    "CJU":"濟州島",     "TAE":"大邱",
    "HKG":"香港",       "MFM":"澳門",
    "BKK":"曼谷(素旺那普)","DMK":"曼谷(廊曼)",
    "SIN":"新加坡",     "KUL":"吉隆坡",     "MNL":"馬尼拉",
    "CGK":"雅加達",     "DPS":"峇里島",     "HAN":"河內",
    "SGN":"胡志明市",   "RGN":"仰光",       "REP":"暹粒",
    "PNH":"金邊",       "VTE":"永珍",       "MDL":"曼德勒",
    "CNX":"清邁",       "PQC":"富國島",     "DAD":"峴港",
    "PEN":"檳城",       "CEB":"宿霧",
    "DEL":"新德里",     "BOM":"孟買",       "MAA":"清奈",
    "BLR":"班加羅爾",   "CMB":"可倫坡",     "KTM":"加德滿都",
    "DAC":"達卡",
    "DXB":"杜拜",       "DOH":"多哈",       "AUH":"阿布達比",
    "RUH":"利雅德",     "KWI":"科威特",     "AMM":"安曼",
    "BEY":"貝魯特",
    "LHR":"倫敦",       "CDG":"巴黎",       "FRA":"法蘭克福",
    "AMS":"阿姆斯特丹", "MAD":"馬德里",     "FCO":"羅馬",
    "BCN":"巴塞隆納",   "VIE":"維也納",     "ZRH":"蘇黎世",
    "IST":"伊斯坦堡",   "PRG":"布拉格",     "WAW":"華沙",
    "ARN":"斯德哥爾摩", "CPH":"哥本哈根",   "HEL":"赫爾辛基",
    "ATH":"雅典",       "LIS":"里斯本",     "DUB":"都柏林",
    "JFK":"紐約",       "LAX":"洛杉磯",     "SFO":"舊金山",
    "ORD":"芝加哥",     "SEA":"西雅圖",     "DFW":"達拉斯",
    "MIA":"邁阿密",     "BOS":"波士頓",     "YVR":"溫哥華",
    "YYZ":"多倫多",     "IAH":"休士頓",     "ONT":"安大略(加州)",
    "SYD":"雪梨",       "MEL":"墨爾本",     "BNE":"布里斯本",
    "PER":"伯斯",       "AKL":"奧克蘭",     "ROR":"帛琉",
    "NBO":"奈洛比",     "JNB":"約翰尼斯堡", "CAI":"開羅",
    "CMN":"卡薩布蘭卡", "ADD":"阿迪斯阿貝巴",
    "GRU":"聖保羅",     "EZE":"布宜諾斯艾利斯",
    "BOG":"波哥大",     "LIM":"利馬",       "SCL":"聖地牙哥",
    "TPE":"台北(桃園)", "TSA":"台北(松山)",
}

FLAG_MAP = {
    "NRT":"🇯🇵","HND":"🇯🇵","KIX":"🇯🇵","NGO":"🇯🇵","CTS":"🇯🇵","FUK":"🇯🇵",
    "HKD":"🇯🇵","AKJ":"🇯🇵","SDJ":"🇯🇵","HNA":"🇯🇵","AXT":"🇯🇵","FKS":"🇯🇵",
    "KMQ":"🇯🇵","HSG":"🇯🇵","KMJ":"🇯🇵","KOJ":"🇯🇵","OKJ":"🇯🇵","TAK":"🇯🇵",
    "HIJ":"🇯🇵","KCZ":"🇯🇵","OKA":"🇯🇵","MYJ":"🇯🇵","OIT":"🇯🇵","UKB":"🇯🇵",
    "IBR":"🇯🇵",
    "ICN":"🇰🇷","GMP":"🇰🇷","PUS":"🇰🇷","CJU":"🇰🇷","TAE":"🇰🇷",
    "HKG":"🇭🇰","MFM":"🇲🇴",
    "BKK":"🇹🇭","DMK":"🇹🇭","CNX":"🇹🇭",
    "SIN":"🇸🇬",
    "KUL":"🇲🇾","PEN":"🇲🇾",
    "MNL":"🇵🇭","CEB":"🇵🇭",
    "CGK":"🇮🇩","DPS":"🇮🇩",
    "HAN":"🇻🇳","SGN":"🇻🇳","DAD":"🇻🇳","PQC":"🇻🇳",
    "RGN":"🇲🇲","MDL":"🇲🇲",
    "REP":"🇰🇭","PNH":"🇰🇭",
    "VTE":"🇱🇦",
    "DEL":"🇮🇳","BOM":"🇮🇳","MAA":"🇮🇳","BLR":"🇮🇳",
    "CMB":"🇱🇰","KTM":"🇳🇵","DAC":"🇧🇩",
    "DXB":"🇦🇪","AUH":"🇦🇪","DOH":"🇶🇦","RUH":"🇸🇦","KWI":"🇰🇼",
    "AMM":"🇯🇴","BEY":"🇱🇧",
    "LHR":"🇬🇧","CDG":"🇫🇷","FRA":"🇩🇪","AMS":"🇳🇱","MAD":"🇪🇸",
    "FCO":"🇮🇹","BCN":"🇪🇸","VIE":"🇦🇹","ZRH":"🇨🇭","IST":"🇹🇷",
    "PRG":"🇨🇿","WAW":"🇵🇱","ARN":"🇸🇪","CPH":"🇩🇰","HEL":"🇫🇮",
    "ATH":"🇬🇷","LIS":"🇵🇹","DUB":"🇮🇪",
    "JFK":"🇺🇸","LAX":"🇺🇸","SFO":"🇺🇸","ORD":"🇺🇸","SEA":"🇺🇸",
    "DFW":"🇺🇸","MIA":"🇺🇸","BOS":"🇺🇸","IAH":"🇺🇸","ONT":"🇺🇸",
    "YVR":"🇨🇦","YYZ":"🇨🇦",
    "SYD":"🇦🇺","MEL":"🇦🇺","BNE":"🇦🇺","PER":"🇦🇺","AKL":"🇳🇿",
    "ROR":"🇵🇼",
    "NBO":"🇰🇪","JNB":"🇿🇦","CAI":"🇪🇬","CMN":"🇲🇦","ADD":"🇪🇹",
    "GRU":"🇧🇷","EZE":"🇦🇷","BOG":"🇨🇴","LIM":"🇵🇪","SCL":"🇨🇱",
    "TPE":"🇹🇼","TSA":"🇹🇼",
}


def dest_label(code: str) -> str:
    code = code.upper()
    flag = FLAG_MAP.get(code, "")
    name = REGION_MAP.get(code, code)
    return f"{flag} {name}" if flag else name


def format_price(price: float, currency: str = "") -> str:
    symbols = {
        "TWD":"NT$", "USD":"$", "EUR":"€", "GBP":"£",
        "JPY":"¥",   "MYR":"MYR ", "SGD":"S$", "HKD":"HK$",
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
    """縮短時間字串：'6:45 AM on Sun, May 3→11:15 AM' → '6:45 AM → 11:15 AM'"""
    if not dep and not arr:
        return "—"
    import re
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
#  主要輸出函式
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
    group_by_date=True: 先按出發日期分組，每組再分傳統/廉航（Vacation Mode 用）
    """
    if not records:
        _print("⚠️  沒有找到符合條件的機票。")
        return

    records = sorted(records, key=lambda r: r.price)

    if group_by_date:
        _print_by_date(records, title, top_n, split_lcc)
    elif split_lcc:
        traditional = [r for r in records if r.airline_type == "traditional"]
        lcc         = [r for r in records if r.airline_type == "LCC"]
        unknown     = [r for r in records if r.airline_type not in ("traditional", "LCC")]
        if traditional:
            _render_table(traditional[:top_n], f"✈  {title} — 傳統航空")
        if lcc:
            _render_table(lcc[:top_n],         f"💸 {title} — 廉航")
        if unknown and not traditional and not lcc:
            _render_table(unknown[:top_n], title)
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
            _render_table(traditional[:top_n], f"✈  {title}  📅 {dep_date} — 傳統航空")
        if lcc:
            _render_table(lcc[:top_n],         f"💸 {title}  📅 {dep_date} — 廉航")
        if unknown and not traditional and not lcc:
            _render_table(unknown[:top_n],     f"✈  {title}  📅 {dep_date}")


def _render_table(records: List[FlightRecord], title: str) -> None:
    if not records:
        return

    is_rt        = any(r.is_roundtrip for r in records)
    has_ret_time = is_rt and any(r.return_dep_time or r.return_arr_time for r in records)

    # 嘗試建立訂票連結
    try:
        from booking_links import BookingLinkFactory, format_links_rich, format_links_plain
        link_sets = [BookingLinkFactory.from_record(r) for r in records]
        _HAS_LINKS = True
    except Exception:
        link_sets   = [None] * len(records)
        _HAS_LINKS  = False

    if _HAS_RICH:
        t = Table(title=title, box=box.ROUNDED, show_lines=True, highlight=True)
        t.add_column("#",       justify="right",  style="dim",         width=3)
        t.add_column("目的地",  style="cyan",      min_width=12)
        t.add_column("去程日",  style="white",     min_width=10)
        t.add_column("去程班次", style="green",    min_width=15)
        t.add_column("去程時長", justify="right",  style="yellow",     min_width=7)
        if is_rt:
            t.add_column("回程日",  style="white",    min_width=10)
            t.add_column("回程班次", style="green",   min_width=15)
            t.add_column("回程時長", justify="right", style="yellow",  min_width=7)
        t.add_column("轉機",    justify="center",  style="magenta",    width=6)
        t.add_column("航空公司", style="dim",      min_width=14)
        t.add_column("來回總價" if is_rt else "票價",
                     justify="right", style="bold green", min_width=12)
        if _HAS_LINKS:
            t.add_column("訂票連結", style="blue",  min_width=16)

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
                ret_time = _fmt_time(r.return_dep_time, r.return_arr_time) if has_ret_time else "—"
                row += [r.return_date or "—", ret_time, format_duration(r.return_duration)]
            row += [r.stops_str, r.airline or "—", format_price(r.price, r.currency)]
            if _HAS_LINKS:
                row.append(format_links_rich(ls) if ls else "—")
            t.add_row(*row)

        console.print(t)
        console.print(f"  [dim]資料更新時間：{records[0].fetched_at[:19]}[/dim]\n")

    else:
        print(f"\n{'='*90}")
        print(f"  {title}")
        print(f"{'='*90}")
        for i, (r, ls) in enumerate(zip(records, link_sets), 1):
            ret_info = f" ↩{r.return_date}" if is_rt and r.return_date else ""
            ret_t    = (
                f" ({_fmt_time(r.return_dep_time, r.return_arr_time)})"
                if has_ret_time and (r.return_dep_time or r.return_arr_time) else ""
            )
            print(
                f"{i:>3}  {dest_label(r.arrival_airport):<16} "
                f"去:{r.departure_date} {_fmt_time(r.departure_time, r.arrival_time)}"
                f"{ret_info}{ret_t}"
                f"  {r.stops_str:>5}  {r.airline:<16}  "
                f"{format_price(r.price, r.currency):>12}"
            )
            if _HAS_LINKS and ls:
                for line in format_links_plain(ls):
                    print(f"       {line}")
        print(f"{'='*90}\n")


def print_vacation_summary(
    all_records: List[FlightRecord],
    mode_label: str,
    top_n: int = 15,
) -> None:
    """
    Vacation Mode 專用：跨所有日期的總排行榜（傳統/廉航分開）。
    每行只顯示最重要資訊，讓使用者一眼看出最便宜的日期+目的地組合。
    """
    if not all_records:
        _print("⚠️  無資料可顯示。")
        return
    records = sorted(all_records, key=lambda r: r.price)

    def _summary_table(recs: List[FlightRecord], title: str) -> None:
        if not recs or not _HAS_RICH:
            return
        t = Table(title=title, box=box.ROUNDED, show_lines=True, highlight=True)
        t.add_column("#",       justify="right", style="dim",       width=3)
        t.add_column("去程日",  style="cyan",    min_width=10)
        t.add_column("回程日",  style="cyan",    min_width=10)
        t.add_column("目的地",  style="green",   min_width=12)
        t.add_column("去程班次", style="white",  min_width=14)
        t.add_column("回程班次", style="white",  min_width=14)
        t.add_column("轉機",    justify="center", style="magenta",  width=6)
        t.add_column("航空公司", style="dim",    min_width=14)
        t.add_column("來回總價", justify="right", style="bold green", min_width=12)
        t.add_column("訂票連結", style="blue",   min_width=14)

        try:
            from booking_links import BookingLinkFactory, format_links_rich
            _links = True
        except Exception:
            _links = False

        for i, r in enumerate(recs[:top_n], 1):
            out_t = _fmt_time(r.departure_time, r.arrival_time)
            ret_t = _fmt_time(r.return_dep_time, r.return_arr_time) if r.return_dep_time or r.return_arr_time else "—"
            link_str = "—"
            if _links:
                try:
                    ls = BookingLinkFactory.from_record(r)
                    link_str = format_links_rich(ls)
                except Exception:
                    pass
            t.add_row(
                str(i),
                r.departure_date,
                r.return_date or "—",
                dest_label(r.arrival_airport),
                out_t, ret_t,
                r.stops_str,
                r.airline or "—",
                format_price(r.price, r.currency),
                link_str,
            )
        console.print(t)

    traditional = [r for r in records if r.airline_type == "traditional"]
    lcc         = [r for r in records if r.airline_type == "LCC"]
    unknown     = [r for r in records if r.airline_type not in ("traditional", "LCC")]
    all_typed   = traditional + lcc + unknown

    if _HAS_RICH:
        console.print(
            f"\n[bold magenta]{'═'*55}[/bold magenta]\n"
            f"[bold magenta]  🏆 {mode_label}  全期間最低票價總排行[/bold magenta]\n"
            f"[bold magenta]{'═'*55}[/bold magenta]"
        )
        if traditional:
            _summary_table(traditional, f"✈  {mode_label} — 傳統航空 總排行")
        if lcc:
            _summary_table(lcc,         f"💸 {mode_label} — 廉航 總排行")
        if unknown and not traditional and not lcc:
            _summary_table(unknown,     f"✈  {mode_label} 總排行")
    else:
        print(f"\n=== {mode_label} 全期間最低票價 ===")
        for i, r in enumerate(all_typed[:top_n], 1):
            print(
                f"  {i:>2}. {r.departure_date}→{r.return_date or '—'}  "
                f"{dest_label(r.arrival_airport):<16}  "
                f"{r.airline:<16}  {format_price(r.price, r.currency)}"
            )


# ══════════════════════════════════════════════════════════════════════════════
#  CSV 匯出（含訂票連結欄位）
# ══════════════════════════════════════════════════════════════════════════════

def export_csv(records: List[FlightRecord], filename: Optional[str] = None) -> Path:
    from flight_scraper import build_booking_url
    from config import get_max_stops_for

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"flights_{ts}.csv"
    path = REPORT_DIR / filename

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "排名", "票種", "航空類型",
            "目的地代碼", "目的地",
            "出發機場", "去程日", "回程日",
            "去程時間", "抵達時間", "飛行時長(分)", "轉機",
            "航空公司", "航班號", "票價", "幣別", "資料時間",
            "訂票連結",  # ← NEW
        ])

        for i, r in enumerate(sorted(records, key=lambda x: x.price), 1):
            max_stops = get_max_stops_for(r.arrival_airport)
            link = build_booking_url(
                from_airport=r.departure_airport,
                to_airport=r.arrival_airport,
                outbound_date=r.departure_date,
                return_date=r.return_date if r.is_roundtrip else "",
                max_stops=max_stops,
            )
            writer.writerow([
                i,
                "來回" if r.is_roundtrip else "單程",
                r.airline_type or "unknown",
                r.arrival_airport, dest_label(r.arrival_airport),
                r.departure_airport, r.departure_date, r.return_date,
                r.departure_time, r.arrival_time,
                r.duration_minutes, r.stops_str,
                r.airline, r.flight_numbers,
                r.price, r.currency, r.fetched_at[:19],
                link,  # ← NEW
            ])

    _print(f"[green]✓ CSV 已儲存：{path}[/green]" if _HAS_RICH else f"✓ CSV 已儲存：{path}")
    return path