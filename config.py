"""
config.py — 全域設定檔
=========================
所有可調整參數集中於此。
"""
import os
from pathlib import Path

# ── 路徑 ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ── 出發機場 ───────────────────────────────────────────────────────────────────
DEPARTURE_AIRPORTS = ["TPE", "TSA"]
DEFAULT_DEPARTURE  = "TPE"

# ── 目的地清單（依地區分組）───────────────────────────────────────────────────
WORLD_DESTINATIONS: dict[str, list[str]] = {
    "Japan": [
        "NRT", "HND", "KIX", "NGO", "CTS", "FUK",
        "HKD", "AKJ", "SDJ", "HNA", "AXT", "FKS", "KMQ",
        "HSG", "KMJ", "KOJ", "OKJ", "TAK", "HIJ", "KCZ",
        "OKA", "MYJ", "OIT", "UKB", "IBR",
    ],
    "東北亞 NE Asia": ["GMP", "ICN", "PUS", "CJU", "TAE", "CJJ", "HKG", "MFM"],
    "東南亞 SE Asia": [
        "BKK", "DMK", "SIN", "KUL", "MNL", "CGK",
        "DPS", "HAN", "SGN", "RGN", "REP", "PNH",
        "VTE", "MDL", "CNX", "PQC", "DAD", "PEN", "CEB",
    ],
    "歐洲 Europe": [
        "LHR", "CDG", "FRA", "AMS", "MAD", "FCO",
        "BCN", "VIE", "ZRH", "IST", "PRG", "WAW",
        "ARN", "CPH", "HEL", "ATH", "LIS", "DUB",
    ],
    "北美 N America": [
        "JFK", "LAX", "SFO", "ORD", "YVR", "YYZ",
        "SEA", "DFW", "MIA", "BOS",
    ],
    "大洋洲 Oceania": ["SYD", "MEL", "AKL", "BNE", "PER"],
    # "南亞 S Asia":       ["DEL", "BOM", "MAA", "BLR", "CMB", "KTM", "DAC"],
    # "中東 Middle East":  ["DXB", "DOH", "AUH", "RUH", "KWI", "AMM", "BEY"],
    # "非洲 Africa":       ["NBO", "JNB", "CAI", "CMN", "ADD"],
    # "南美 S America":    ["GRU", "EZE", "BOG", "LIM", "SCL"],
}

ALL_DESTINATIONS: list[str] = list(dict.fromkeys(
    code for codes in WORLD_DESTINATIONS.values() for code in codes
))

# ── 亞洲地區（短途 / Vacation Mode 用）────────────────────────────────────────
ASIA_REGIONS: set[str] = {
    "Japan", "東北亞 NE Asia", "東南亞 SE Asia", "南亞 S Asia", "中東 Middle East",
}
ASIA_DESTINATIONS: list[str] = list(dict.fromkeys(
    code
    for region, codes in WORLD_DESTINATIONS.items()
    if region in ASIA_REGIONS
    for code in codes
))

NON_ASIA_REGIONS: set[str] = {
    "歐洲 Europe", "北美 N America", "大洋洲 Oceania", "非洲 Africa", "南美 S America",
}
NON_ASIA_DESTINATIONS: list[str] = list(dict.fromkeys(
    code
    for region, codes in WORLD_DESTINATIONS.items()
    if region in NON_ASIA_REGIONS
    for code in codes
))

# ── 航點轉機規則 ───────────────────────────────────────────────────────────────
# Japan / 東北亞 / 東南亞 → 直達 (0 stops)
NONSTOP_ONLY_REGIONS: set[str] = {"Japan", "東北亞 NE Asia", "東南亞 SE Asia"}
INTERCONTINENTAL_REGIONS: set[str] = {
    "歐洲 Europe", "北美 N America", "大洋洲 Oceania", "非洲 Africa", "南美 S America",
}

# ── 自訂最愛目的地 ─────────────────────────────────────────────────────────────
MY_DESTINATIONS: list[str] = [
    "NRT", "KIX",        # 日本
    "ICN",               # 韓國
    "BKK", "DPS",        # 東南亞
    "SIN",               # 新加坡
    "LHR", "CDG",        # 歐洲
    "LAX", "SFO",        # 北美
]

FAVOURITE_GROUPS: dict[str, list[str]] = {
    # "🏖️  度假首選": ["DPS", "BKK", "SIN", "NRT", "KIX"],
    # "🗺️  長途探索": ["LHR", "CDG", "LAX", "SYD"],
}

_AIRPORT_TO_REGION: dict[str, str] = {
    code: region
    for region, codes in WORLD_DESTINATIONS.items()
    for code in codes
}


def get_region(airport: str) -> str:
    return _AIRPORT_TO_REGION.get(airport.upper(), "")


def get_max_stops_for(airport: str, default_max: int = 2) -> int:
    """
    依目的地決定 max_stops：
    - Japan / 東北亞 / 東南亞 → 0（直達）
    - 其他地區 → default_max
    """
    region = get_region(airport.upper())
    if region in NONSTOP_ONLY_REGIONS:
        return 0
    return default_max


def is_intercontinental(airport: str) -> bool:
    return get_region(airport) in INTERCONTINENTAL_REGIONS


# ── 飛行限制 ───────────────────────────────────────────────────────────────────
MAX_STOPS          = 2
MAX_DURATION_HOURS = 26
DEFAULT_FLEX_DAYS  = 0

# ── 旅行天數預設 ───────────────────────────────────────────────────────────────
ASIA_DEFAULT_TRIP_DAYS  = 5
INTER_DEFAULT_TRIP_DAYS = 9
INTER_TRIP_MIN_DAYS     = 8
INTER_TRIP_MAX_DAYS     = 18

# ── 搜尋旅客 ──────────────────────────────────────────────────────────────────
ADULTS   = 1
CHILDREN = 0
INFANTS  = 0

# ── 排程設定 ──────────────────────────────────────────────────────────────────
SCHEDULE_TIME = "07:00"

# ── 假期搜尋設定 ──────────────────────────────────────────────────────────────
HOLIDAY_LOOKAHEAD_DAYS = 180
MIN_TRIP_DAYS          = 3
MAX_TRIP_DAYS          = 18

# ── 資料庫 ────────────────────────────────────────────────────────────────────
DB_PATH = BASE_DIR / "flights.db"

# ── 輸出報告 ──────────────────────────────────────────────────────────────────
REPORT_DIR    = BASE_DIR / "reports"
TOP_N_RESULTS = 20

# ── 請求速率控制 ──────────────────────────────────────────────────────────────
REQUEST_DELAY_SEC = 2.5
MAX_RETRIES       = 3

# ── Playwright 設定 ───────────────────────────────────────────────────────────
PLAYWRIGHT_HEADLESS = True
PLAYWRIGHT_TIMEOUT  = 30_000

# ══════════════════════════════════════════════════════════════════════════════
#  Vacation Mode 設定
# ══════════════════════════════════════════════════════════════════════════════

VACATION_MODES: dict[str, dict] = {
    "short": {
        "label":        "🏖️  短途假期",
        "days":         5,
        "flex_days":    1,
        "weekends":     1,
        "max_stops":    0,          # 直達（強制）
        "max_duration": 10,
        "destinations": "asia",
        "horizon":      180,
    },
    "long": {
        "label":        "✈️  長途假期",
        "days":         9,
        "flex_days":    1,
        "weekends":     2,
        "max_stops":    2,
        "max_duration": 26,
        "destinations": "non_asia",
        "horizon":      365,
    },
    "happy": {
        "label":        "🌍 快樂假期",
        "days":         16,
        "flex_days":    2,
        "weekends":     3,
        "max_stops":    2,
        "max_duration": 26,
        "destinations": "non_asia",
        "horizon":      365,
    },
}

VACATION_REQUIRE_TW_HOLIDAY = False
VACATION_TOP_WINDOWS        = 6
VACATION_TOP_DEST           = 25
VACATION_TOP_RESULTS        = 10

# ══════════════════════════════════════════════════════════════════════════════
#  通知設定（選填 — 設定環境變數或直接填入下方字串）
#  支援 LINE Notify、Telegram Bot、Email (SMTP)
# ══════════════════════════════════════════════════════════════════════════════

LINE_NOTIFY_TOKEN  = os.getenv("LINE_NOTIFY_TOKEN",  "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "")

SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER",     "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

# 低於此金額（TWD）才發出通知
PRICE_ALERT_THRESHOLD_TWD = int(os.getenv("PRICE_ALERT_THRESHOLD_TWD", "15000"))

# 報告顯示幣別（不影響搜尋，僅影響通知訊息格式）
DISPLAY_CURRENCY = os.getenv("DISPLAY_CURRENCY", "TWD")

# 匯率對照表（用於通知模組將非 TWD 票價換算顯示，非精確值僅供參考）
TWD_FALLBACK_RATES: dict[str, float] = {
    "TWD": 1.0,
    "USD": 32.5,  "EUR": 35.0,  "GBP": 41.0,
    "JPY": 0.22,  "KRW": 0.025, "HKD": 4.1,
    "SGD": 24.0,  "MYR": 7.2,   "THB": 0.91,
    "AUD": 21.5,  "NZD": 19.5,  "CAD": 24.0,
    "CNY": 4.5,   "INR": 0.39,  "AED": 8.8,
    "QAR": 8.9,
}
