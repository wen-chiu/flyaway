"""
config.py — 全域設定檔 / Global Configuration
=================================================
所有可調整的參數都在這裡，方便集中管理。

敏感設定（如通知 Token）請放在 .env 檔案，不要硬寫在這裡。
環境變數優先於此檔的預設值。
"""

import os
import sys
from pathlib import Path

# ── Python 版本檢查 ────────────────────────────────────────────────────────────
if sys.version_info < (3, 10):
    raise RuntimeError(
        f"Flyaway requires Python 3.10+. You are running {sys.version}.\n"
        "Please upgrade: https://www.python.org/downloads/"
    )

# ── 載入 .env（若存在）────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 未安裝時靜默跳過

# ── 專案根目錄 ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ── 出發機場 ──────────────────────────────────────────────────────────────────
DEPARTURE_AIRPORTS = ["TPE", "TSA"]
DEFAULT_DEPARTURE = os.getenv("DEFAULT_DEPARTURE", "TPE")

# ── 目的地清單 (依地區分組) ──────────────────────────────────────────────────────
WORLD_DESTINATIONS: dict[str, list[str]] = {
    "東北亞 NE Asia": ["NRT", "HND", "KIX", "NGO", "CTS", "FUK", "GMP"],
    "東南亞 SE Asia": ["BKK", "DMK", "SIN", "KUL", "MNL", "CGK",
                      "DPS", "HAN", "SGN", "RGN", "REP", "PNH",
                      "VTE", "MDL"],
    "南亞 S Asia":    ["DEL", "BOM", "MAA", "BLR", "CMB", "KTM", "DAC"],
    "歐洲 Europe":    ["LHR", "CDG", "FRA", "AMS", "MAD", "FCO",
                      "BCN", "VIE", "ZRH", "IST", "PRG", "WAW",
                      "ARN", "CPH", "HEL", "ATH", "LIS", "DUB"],
    "大洋洲 Oceania": ["SYD", "MEL", "AKL", "BNE", "PER"],
    # "北美 N America": ["JFK", "LAX", "SFO", "ORD", "YVR", "YYZ",
    #                    "SEA", "DFW", "MIA", "BOS"],
    # "中東 Middle East": ["DXB", "DOH", "AUH", "RUH", "KWI", "AMM", "BEY"],
    # "非洲 Africa": ["NBO", "JNB", "CAI", "CMN", "ADD"],
    # "南美 S America": ["GRU", "EZE", "BOG", "LIM", "SCL"],
}

ALL_DESTINATIONS: list[str] = [
    code for codes in WORLD_DESTINATIONS.values() for code in codes
]

# ══════════════════════════════════════════════════════════════════════════════
# ✏️ 自訂最愛目的地
# ══════════════════════════════════════════════════════════════════════════════
MY_DESTINATIONS: list[str] = [
    "NRT", "KIX",        # 日本
    "ICN",               # 韓國
    "BKK", "DPS",        # 東南亞
    "SIN",               # 新加坡
    "LHR", "CDG",        # 歐洲
    "LAX", "SFO",        # 北美
]

FAVOURITE_GROUPS: dict[str, list[str]] = {
    # "🏖️ 度假首選": ["DPS", "BKK", "SIN", "NRT", "KIX"],
    # "🗺️ 長途探索": ["LHR", "CDG", "LAX", "SYD"],
}

# ── 航點 max_stops 規則 ───────────────────────────────────────────────────────
NONSTOP_ONLY_REGIONS: set[str] = {"東北亞 NE Asia", "東南亞 SE Asia"}
INTERCONTINENTAL_REGIONS: set[str] = {
    "歐洲 Europe", "北美 N America", "大洋洲 Oceania", "非洲 Africa", "南美 S America"
}

_AIRPORT_TO_REGION: dict[str, str] = {
    code: region
    for region, codes in WORLD_DESTINATIONS.items()
    for code in codes
}


def get_region(airport: str) -> str:
    return _AIRPORT_TO_REGION.get(airport.upper(), "")


def get_max_stops_for(airport: str, default_max: int = 2) -> int:
    region = get_region(airport)
    if region in NONSTOP_ONLY_REGIONS:
        return 0
    return default_max


def is_intercontinental(airport: str) -> bool:
    return get_region(airport) in INTERCONTINENTAL_REGIONS


# ── 旅行天數預設 ────────────────────────────────────────────────────────────────
ASIA_DEFAULT_TRIP_DAYS = 5
INTER_TRIP_MIN_DAYS = 9
INTER_TRIP_MAX_DAYS = 16
INTER_DEFAULT_TRIP_DAYS = 12

# ── 飛行限制（通用預設）──────────────────────────────────────────────────────────
MAX_STOPS = int(os.getenv("MAX_STOPS", "2"))
MAX_DURATION_HOURS = int(os.getenv("MAX_DURATION_HOURS", "26"))

# ── 彈性出發日期 ──────────────────────────────────────────────────────────────
DEFAULT_FLEX_DAYS = int(os.getenv("DEFAULT_FLEX_DAYS", "0"))

# ── 搜尋旅客 ─────────────────────────────────────────────────────────────────
ADULTS = int(os.getenv("ADULTS", "1"))
CHILDREN = int(os.getenv("CHILDREN", "0"))
INFANTS = int(os.getenv("INFANTS", "0"))

# ── 排程設定 ─────────────────────────────────────────────────────────────────
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "07:00")

# ── 假期搜尋設定 ─────────────────────────────────────────────────────────────
HOLIDAY_LOOKAHEAD_DAYS = int(os.getenv("HOLIDAY_LOOKAHEAD_DAYS", "180"))
MIN_TRIP_DAYS = int(os.getenv("MIN_TRIP_DAYS", "3"))
MAX_TRIP_DAYS = int(os.getenv("MAX_TRIP_DAYS", "16"))

# ── 資料庫 ───────────────────────────────────────────────────────────────────
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "flights.db")))

# ── 輸出報告 ─────────────────────────────────────────────────────────────────
REPORT_DIR = Path(os.getenv("REPORT_DIR", str(BASE_DIR / "reports")))
TOP_N_RESULTS = int(os.getenv("TOP_N_RESULTS", "20"))

# ── 請求速率控制 ─────────────────────────────────────────────────────────────
REQUEST_DELAY_SEC = float(os.getenv("REQUEST_DELAY_SEC", "2.5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# ── 來回配對上限 ─────────────────────────────────────────────────────────────
# 每條航線最多配對的去/回程候選數，避免組合爆炸 (N×N pairs per route)
MAX_ROUNDTRIP_PAIR_CANDIDATES = int(os.getenv("MAX_ROUNDTRIP_PAIR_CANDIDATES", "10"))
# 每條航線最終保留的來回票數量上限
MAX_ROUNDTRIP_OUTPUT_PER_ROUTE = int(os.getenv("MAX_ROUNDTRIP_OUTPUT_PER_ROUTE", "20"))

# ── Playwright 設定 ───────────────────────────────────────────────────────────
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
PLAYWRIGHT_TIMEOUT = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))

# ── 通知設定（放在 .env，不要 hardcode）─────────────────────────────────────────
# LINE Notify token（選填）
LINE_NOTIFY_TOKEN: str = os.getenv("LINE_NOTIFY_TOKEN", "")

# Telegram Bot token + chat_id（選填）
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# Email（選填）
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_TO: str = os.getenv("ALERT_EMAIL_TO", "")

# 低價警示閾值（TWD）：低於此價格時發送通知
PRICE_ALERT_THRESHOLD_TWD: float = float(os.getenv("PRICE_ALERT_THRESHOLD_TWD", "5000"))

# ── 幣別 & TWD 匯率 ───────────────────────────────────────────────────────────
DISPLAY_CURRENCY = os.getenv("DISPLAY_CURRENCY", "TWD")

# 備用固定匯率（對 TWD）：無法取得即時匯率時使用
TWD_FALLBACK_RATES: dict[str, float] = {
    "TWD": 1.0,
    "USD": 32.5,
    "EUR": 35.0,
    "GBP": 41.0,
    "JPY": 0.22,
    "KRW": 0.024,
    "HKD": 4.15,
    "MYR": 7.2,
    "SGD": 24.0,
    "THB": 0.93,
    "AUD": 20.5,
    "NZD": 19.0,
    "CAD": 23.5,
    "CNY": 4.5,
    "INR": 0.39,
    "AED": 8.85,
    "QAR": 8.93,
    "SAR": 8.67,
    "MOP": 4.02,
    "BDT": 0.28,
    "NPR": 0.24,
    "LKR": 0.11,
    "MMK": 0.015,
    "VND": 0.0013,
    "PHP": 0.57,
    "IDR": 0.002,
    "PKR": 0.115,
    "KWD": 105.0,
    "BHD": 86.0,
    "OMR": 84.5,
    "JOD": 45.8,
    "LBP": 0.00035,
    "EGP": 0.67,
    "KES": 0.25,
    "ZAR": 1.75,
    "ETB": 0.58,
    "MAD": 3.25,
    "BRL": 5.6,
    "ARS": 0.033,
    "COP": 0.008,
    "PEN": 8.7,
    "CLP": 0.034,
    "PLN": 8.0,
    "CZK": 1.4,
    "HUF": 0.089,
    "SEK": 3.0,
    "NOK": 2.95,
    "DKK": 4.7,
    "CHF": 36.5,
    "TRY": 0.95,
    "GEL": 12.0,
    "UAH": 0.79,
}