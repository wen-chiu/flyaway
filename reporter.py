"""
reporter.py — 結果顯示與報告產生
====================================
傳統航空 vs 廉航分兩表顯示，支援來回票總價。
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional

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

# ── 目的地名稱對照 ────────────────────────────────────────────────────────────
REGION_MAP = {
    "HKD": "函館",       "AKJ": "旭川",       "SDJ": "仙台",
    "HNA": "花卷",       "AXT": "秋田",       "FKS": "福島",
    "KMQ": "小松",       "HSG": "佐賀",       "KMJ": "熊本",
    "KOJ": "鹿兒島",     "OKJ": "岡山",       "TAK": "高松",
    "HIJ": "廣島",       "KCZ": "高知",       "OKA": "沖繩(那霸)",
    "MYJ": "松山(四國)", "OIT": "大分",       "UKB": "神戶",
    "IBR": "茨城",

    "CJU": "濟州島",     "TAE": "大邱",

    "CNX": "清邁",       "PQC": "富國島",     "DAD": "峴港",
    "PEN": "檳城",       "CEB": "宿霧",

    "IAH": "休士頓",     "ONT": "安大略(加州)", "ROR": "帛琉",
    "CHC": "基督城",

    "NRT": "東京(成田)", "HND": "東京(羽田)", "KIX": "大阪",
    "NGO": "名古屋",     "CTS": "札幌",       "FUK": "福岡",
    "ICN": "首爾(仁川)", "GMP": "首爾(金浦)", "PUS": "釜山",
    "HKG": "香港",       "MFM": "澳門",
    "BKK": "曼谷(素旺那普)", "DMK": "曼谷(廊曼)",
    "SIN": "新加坡",     "KUL": "吉隆坡",     "MNL": "馬尼拉",
    "CGK": "雅加達",     "DPS": "峇里島",     "HAN": "河內",
    "SGN": "胡志明市",   "RGN": "仰光",       "REP": "暹粒",
    "PNH": "金邊",       "VTE": "永珍",       "MDL": "曼德勒",
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
    "YYZ": "多倫多",
    "SYD": "雪梨",       "MEL": "墨爾本",     "BNE": "布里斯本",
    "PER": "伯斯",       "AKL": "奧克蘭",
    "NBO": "奈洛比",     "JNB": "約翰尼斯堡", "CAI": "開羅",
    "CMN": "卡薩布蘭卡", "ADD": "阿迪斯阿貝巴",
    "GRU": "聖保羅",     "EZE": "布宜諾斯艾利斯",
    "BOG": "波哥大",     "LIM": "利馬",       "SCL": "聖地牙哥",
}

# 國旗 emoji 對照
FLAG_MAP = {
    "NRT":"🇯🇵","HND":"🇯🇵","KIX":"🇯🇵","NGO":"🇯🇵","CTS":"🇯🇵","FUK":"🇯🇵",
    "ICN":"🇰🇷","GMP":"🇰🇷","PUS":"🇰🇷",
    "HKG":"🇭🇰","MFM":"🇲🇴",
    "BKK":"🇹🇭","DMK":"🇹🇭",
    "SIN":"🇸🇬","KUL":"🇲🇾","MNL":"🇵🇭","CGK":"🇮🇩","DPS":"🇮🇩",
    "HAN":"🇻🇳","SGN":"🇻🇳","RGN":"🇲🇲","MDL":"🇲🇲",
    "REP":"🇰🇭","PNH":"🇰🇭","VTE":"🇱🇦",
    "DEL":"🇮🇳","BOM":"🇮🇳","MAA":"🇮🇳","BLR":"🇮🇳",
    "CMB":"🇱🇰","KTM":"🇳🇵","DAC":"🇧🇩",
    "DXB":"🇦🇪","AUH":"🇦🇪","DOH":"🇶🇦","RUH":"🇸🇦","KWI":"🇰🇼",
    "AMM":"🇯🇴","BEY":"🇱🇧",
    "LHR":"🇬🇧","CDG":"🇫🇷","FRA":"🇩🇪","AMS":"🇳🇱","MAD":"🇪🇸",
    "FCO":"🇮🇹","BCN":"🇪🇸","VIE":"🇦🇹","ZRH":"🇨🇭","IST":"🇹🇷",
    "PRG":"🇨🇿","WAW":"🇵🇱","ARN":"🇸🇪","CPH":"🇩🇰","HEL":"🇫🇮",
    "ATH":"🇬🇷","LIS":"🇵🇹","DUB":"🇮🇪",
    "JFK":"🇺🇸","LAX":"🇺🇸","SFO":"🇺🇸","ORD":"🇺🇸","SEA":"🇺🇸",
    "DFW":"🇺🇸","MIA":"🇺🇸","BOS":"🇺🇸",
    "YVR":"🇨🇦","YYZ":"🇨🇦",
    "SYD":"🇦🇺","MEL":"🇦🇺","BNE":"🇦🇺","PER":"🇦🇺","AKL":"🇳🇿",
    "NBO":"🇰🇪","JNB":"🇿🇦","CAI":"🇪🇬","CMN":"🇲🇦","ADD":"🇪🇹",
    "GRU":"🇧🇷","EZE":"🇦🇷","BOG":"🇨🇴","LIM":"🇵🇪","SCL":"🇨🇱",
    "TPE":"🇹🇼","TSA":"🇹🇼",
}


def dest_label(code: str) -> str:
    code = code.upper()
    flag = FLAG_MAP.get(code, "")
    name = REGION_MAP.get(code, code)
    return f"{flag} {name}" if flag else name


def format_price(price: float, currency: str = "TWD") -> str:
    symbols = {"USD": "$", "TWD": "NT$", "EUR": "€", "GBP": "£",
               "JPY": "¥", "MYR": "MYR ", "SGD": "S$", "HKD": "HK$"}
    sym = symbols.get(currency.upper(), f"{currency} ")
    if currency.upper() in ("JPY", "TWD", "KRW", "IDR", "VND"):
        return f"{sym}{int(price):,}"
    return f"{sym}{price:,.0f}"


def format_duration(minutes: int) -> str:
    if minutes <= 0:
        return "—"
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m"


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
) -> None:
    """
    印出機票結果。
    split_lcc=True：傳統航空 & 廉航各自顯示一張表。
    """
    if not records:
        _print("⚠️  沒有找到符合條件的機票。")
        return

    records = sorted(records, key=lambda r: r.price)

    if split_lcc:
        traditional = [r for r in records if r.airline_type == "traditional"]
        lcc         = [r for r in records if r.airline_type == "LCC"]
        unknown     = [r for r in records if r.airline_type not in ("traditional", "LCC")]

        if traditional:
            _render_table(traditional[:top_n], title=f"✈  {title} — 傳統航空",  header_style="bold blue")
        if lcc:
            _render_table(lcc[:top_n],         title=f"💸 {title} — 廉航",       header_style="bold yellow")
        if unknown and not traditional and not lcc:
            # Only show unknown section if no classified results
            _render_table(unknown[:top_n],     title=f"✈  {title}",              header_style="bold cyan")
        elif unknown:
            # Merge unknown into whichever bucket is smaller
            bucket = lcc if len(lcc) <= len(traditional) else traditional
            bucket.extend(unknown)
            # Re-render the merged bucket
            target_title = "廉航" if bucket is lcc else "傳統航空"
            merged = sorted(bucket, key=lambda r: r.price)
            _render_table(merged[:top_n], title=f"{'💸' if '廉' in target_title else '✈'}  {title} — {target_title}(含未分類)",
                          header_style="bold yellow" if "廉" in target_title else "bold blue")
    else:
        _render_table(records[:top_n], title=title)


def _render_table(records: List[FlightRecord], title: str, header_style: str = "bold cyan") -> None:
    if not records:
        return
    is_rt        = any(r.is_roundtrip for r in records)
    has_ret_time = is_rt and any(r.return_dep_time or r.return_arr_time for r in records)

    # Pre-build booking links for all records
    try:
        from booking_links import BookingLinkFactory, format_links_rich, format_links_plain
        link_sets = [BookingLinkFactory.from_record(r) for r in records]
        _HAS_LINKS = True
    except Exception:
        link_sets = [None] * len(records)
        _HAS_LINKS = False

    if _HAS_RICH:
        t = Table(title=title, box=box.ROUNDED, show_lines=True, highlight=True)
        t.add_column("#",         justify="right", style="dim",        width=3)
        t.add_column("目的地",    style="cyan",     min_width=12)
        t.add_column("去程日",    style="white",    min_width=10)
        t.add_column("去程班次",  style="green",    min_width=16)
        t.add_column("去程時長",  justify="right",  style="yellow",    min_width=7)
        if is_rt:
            t.add_column("回程日",    style="white",    min_width=10)
            t.add_column("回程班次",  style="green",    min_width=16)
            t.add_column("回程時長",  justify="right",  style="yellow",    min_width=7)
        t.add_column("轉機",      justify="center", style="magenta",   width=6)
        t.add_column("航空公司",  style="dim",      min_width=14)
        t.add_column("來回總價" if is_rt else "票價",
                     justify="right", style="bold green", min_width=12)
        if _HAS_LINKS:
            t.add_column("訂票連結", style="blue", min_width=18)

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
                row += [
                    r.return_date or "—",
                    ret_time,
                    format_duration(r.return_duration),
                ]
            row += [
                r.stops_str,
                r.airline or "—",
                format_price(r.price, r.currency),
            ]
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
            ret_t    = f" ({_fmt_time(r.return_dep_time, r.return_arr_time)})" \
                       if has_ret_time and (r.return_dep_time or r.return_arr_time) else ""
            print(
                f"{i:>3}  {dest_label(r.arrival_airport):<16} "
                f"去:{r.departure_date} {_fmt_time(r.departure_time, r.arrival_time)}"
                f"{ret_info}{ret_t}"
                f"  {r.stops_str:>5}  {r.airline:<16}  {format_price(r.price, r.currency):>12}"
            )
            if _HAS_LINKS and ls:
                for line in format_links_plain(ls):
                    print(f"       {line}")
        print(f"{'='*90}\n")


def _fmt_time(dep: str, arr: str) -> str:
    """格式化起降時間，縮短過長的英文日期。"""
    if not dep and not arr:
        return "—"
    # 縮短 "6:45 AM on Sun, May 3" → "06:45 → 11:15"
    import re
    def extract_time(s: str) -> str:
        m = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)', s, re.I)
        return m.group(1).strip() if m else s[:12]
    d = extract_time(dep) if dep else "?"
    a = extract_time(arr) if arr else "?"
    ahead = ""
    if "+1" in (arr or "") or "+2" in (arr or ""):
        ahead = " +1d" if "+1" in arr else " +2d"
    return f"{d} → {a}{ahead}"


# ══════════════════════════════════════════════════════════════════════════════
#  CSV 匯出
# ══════════════════════════════════════════════════════════════════════════════

def export_csv(records: List[FlightRecord], filename: Optional[str] = None) -> Path:
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
        ])
        for i, r in enumerate(sorted(records, key=lambda x: x.price), 1):
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
            ])

    _print(f"[green]✓ CSV 已儲存：{path}[/green]" if _HAS_RICH else f"✓ CSV 已儲存：{path}")
    return path