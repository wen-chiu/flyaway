"""
config.py — 全域設定檔 / Global Configuration
=================================================
所有可調整的參數都在這裡，方便集中管理。
"""

from pathlib import Path

# ── 專案根目錄 ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ── 出發機場 (可多選) ────────────────────────────────────────────────────────
DEPARTURE_AIRPORTS = ["TPE", "TSA"]
DEFAULT_DEPARTURE  = "TPE"

# ── 目的地清單 (依地區分組) ──────────────────────────────────────────────────
WORLD_DESTINATIONS: dict[str, list[str]] = {
    "Japan":    [ "NRT", "HND", "KIX", "NGO", "CTS", "FUK",
                  "HKD", "AKJ", "SDJ", "HNA", "AXT", "FKS", "KMQ", 
                  "HSG", "KMJ", "KOJ", "OKJ", "TAK", "HIJ", "KCZ",
                  "OKA", "MYJ", "OIT", "UKB", "IBR"],
    "東北亞 NE Asia":    ["NRT", "HND", "KIX", "NGO", "CTS", "FUK", "GMP",
                          "ICN", "PUS", "OKA", "CJU", "TAE"],
    "東南亞 SE Asia":    ["BKK", "DMK", "SIN", "KUL", "MNL", "CGK",
                          "DPS", "HAN", "SGN", "RGN", "REP", "PNH",
                          "VTE", "MDL", "CNX", "PQC", "DAD", "PEN", "CEB"],
    "南亞 S Asia":       ["DEL", "BOM", "MAA", "BLR", "CMB", "KTM", "DAC"],
    "歐洲 Europe":       ["LHR", "CDG", "FRA", "AMS", "MAD", "FCO",
                          "BCN", "VIE", "ZRH", "IST", "PRG", "WAW",
                          "ARN", "CPH", "HEL", "ATH", "LIS", "DUB"],
    "北美 N America":    ["JFK", "LAX", "SFO", "ORD", "YVR", "YYZ",
                          "SEA", "DFW", "MIA", "BOS", "IAH", "ONT"],
    "大洋洲 Oceania":    ["SYD", "MEL", "AKL", "BNE", "PER"],
    "非洲 Africa":       ["NBO", "JNB", "CAI", "CMN", "ADD"],
    "南美 S America":    ["GRU", "EZE", "BOG", "LIM", "SCL"],
    "中東 Middle East":  ["DXB", "DOH", "AUH", "RUH", "KWI", "AMM", "BEY"],
}

ALL_DESTINATIONS: list[str] = [
    code for codes in WORLD_DESTINATIONS.values() for code in codes
]

# ── 亞洲地區（短途假期預設目的地）───────────────────────────────────────────────
ASIA_REGIONS: set[str] = {
    "東北亞 NE Asia", "東南亞 SE Asia", "南亞 S Asia", "中東 Middle East"
}
ASIA_DESTINATIONS: list[str] = [
    code for region, codes in WORLD_DESTINATIONS.items()
    if region in ASIA_REGIONS
    for code in codes
]

# 亞洲以外地區（長途假期預設目的地）
NON_ASIA_REGIONS: set[str] = {
    "歐洲 Europe", "北美 N America", "大洋洲 Oceania", "非洲 Africa", "南美 S America"
}
NON_ASIA_DESTINATIONS: list[str] = [
    code for region, codes in WORLD_DESTINATIONS.items()
    if region in NON_ASIA_REGIONS
    for code in codes
]

# ══════════════════════════════════════════════════════════════════════════════
#  ✏️  Vacation Mode 設定
# ══════════════════════════════════════════════════════════════════════════════

# ── 搜尋範圍 ──────────────────────────────────────────────────────────────────
VACATION_HORIZON_6M  = 180   # 6 個月
VACATION_HORIZON_1Y  = 365   # 1 年

# ── 短途假期（short）─────────────────────────────────────────────────────────
# 目的地：亞洲（短程），只接受直達航班
VACATION_SHORT_DAYS_MIN = 5
VACATION_SHORT_DAYS_MAX = 6
VACATION_SHORT_WEEKENDS = 1          # 必須涵蓋至少 N 個完整週末
VACATION_SHORT_MAX_STOPS = 0         # 直達
VACATION_SHORT_MAX_DURATION_H = 10   # 短途飛行上限（小時）

# ── 長途假期（long）──────────────────────────────────────────────────────────
# 目的地：亞洲以外，允許轉機
VACATION_LONG_2W_DAYS_MIN = 8
VACATION_LONG_2W_DAYS_MAX = 11
VACATION_LONG_2W_WEEKENDS = 2        # 涵蓋 2 個完整週末

VACATION_LONG_3W_DAYS_MIN = 15
VACATION_LONG_3W_DAYS_MAX = 18
VACATION_LONG_3W_WEEKENDS = 3        # 涵蓋 3 個完整週末

VACATION_LONG_MAX_STOPS       = 2    # 最多轉機次數
VACATION_LONG_MAX_DURATION_H  = 26   # 總飛行時間上限（小時）

# ── 是否必須包含台灣國定假日（預設可關閉）──────────────────────────────────────
VACATION_REQUIRE_TW_HOLIDAY = False  # True = 必含台灣假日；False = 一般周末也可

# ── 每個窗口最多搜尋幾個目的地（控制 API 呼叫數量）──────────────────────────
VACATION_TOP_WINDOWS   = 8           # 最多取幾個時間窗口
VACATION_TOP_DEST      = 30          # 每個窗口搜尋幾個目的地
VACATION_TOP_RESULTS   = 15          # 每個窗口顯示幾筆結果

# ══════════════════════════════════════════════════════════════════════════════
#  ✏️  自訂最愛目的地（可直接在這裡編輯，不影響其他設定）
# ══════════════════════════════════════════════════════════════════════════════
# 在選單中會顯示為「⭐ 我的最愛」群組，可在互動模式直接選擇。
# 按 IATA 代碼填入，用逗號隔開即可。
MY_DESTINATIONS: list[str] = [
    "NRT", "KIX",       # 日本
    "ICN",               # 韓國
    "BKK", "DPS",        # 東南亞
    "SIN",               # 新加坡
    "LHR", "CDG",        # 歐洲
    "LAX", "SFO",        # 北美
]

# 也可以自訂多個命名群組，在選單顯示為獨立選項
FAVOURITE_GROUPS: dict[str, list[str]] = {
    # 範例：移除 # 號啟用
    # "🏖️  度假首選": ["DPS", "BKK", "SIN", "NRT", "KIX"],
    # "🗺️  長途探索": ["LHR", "CDG", "LAX", "SYD"],
}

# ── 航點 max_stops 規則 ───────────────────────────────────────────────────────
# 東北亞 & 東南亞 → 只接受直達 (0 stops)
NONSTOP_ONLY_REGIONS: set[str] = {"東北亞 NE Asia", "東南亞 SE Asia"}

# 跨洲地區（超出亞洲）→ 維持轉機上限
INTERCONTINENTAL_REGIONS: set[str] = {
    "歐洲 Europe", "北美 N America", "大洋洲 Oceania", "非洲 Africa", "南美 S America"
}

# 根據機場代碼快速查出所屬地區
_AIRPORT_TO_REGION: dict[str, str] = {
    code: region
    for region, codes in WORLD_DESTINATIONS.items()
    for code in codes
}

def get_region(airport: str) -> str:
    return _AIRPORT_TO_REGION.get(airport.upper(), "")

def get_max_stops_for(airport: str, default_max: int = 2) -> int:
    """依目的地地區決定 max_stops：東北亞/東南亞 = 0，其他 = default_max"""
    region = get_region(airport)
    if region in NONSTOP_ONLY_REGIONS:
        return 0
    return default_max

def is_intercontinental(airport: str) -> bool:
    return get_region(airport) in INTERCONTINENTAL_REGIONS

# ── 旅行天數預設 ───────────────────────────────────────────────────────────────
# 亞洲（東北亞、東南亞、南亞、中東）：預設 5 天
ASIA_DEFAULT_TRIP_DAYS   = 5

# 跨洲：預設 9–16 天（含完整週六日）
INTER_TRIP_MIN_DAYS = 9
INTER_TRIP_MAX_DAYS = 16
INTER_DEFAULT_TRIP_DAYS = 12   # 預設中間值

# ── 飛行限制（通用預設）────────────────────────────────────────────────────────
MAX_STOPS          = 2       # 通用上限（東北亞/東南亞會被覆蓋為 0）
MAX_DURATION_HOURS = 26

# ── 彈性出發日期 (預設值) ─────────────────────────────────────────────────────
# 在使用者指定日期前後 ±N 天各多搜尋一次
DEFAULT_FLEX_DAYS = 0        # 0=不彈性，1=±1天，2=±2天

# ── 搜尋旅客 ─────────────────────────────────────────────────────────────────
ADULTS   = 1
CHILDREN = 0
INFANTS  = 0

# ── 排程設定 ─────────────────────────────────────────────────────────────────
SCHEDULE_TIME = "07:00"

# ── 假期搜尋設定 ─────────────────────────────────────────────────────────────
HOLIDAY_LOOKAHEAD_DAYS = 180
MIN_TRIP_DAYS = 3
MAX_TRIP_DAYS = 16

# ── 資料庫 ───────────────────────────────────────────────────────────────────
DB_PATH = BASE_DIR / "flights.db"

# ── 輸出報告 ─────────────────────────────────────────────────────────────────
REPORT_DIR    = BASE_DIR / "reports"
TOP_N_RESULTS = 20

# ── 請求速率控制 ──────────────────────────────────────────────────────────────
REQUEST_DELAY_SEC = 2.5
MAX_RETRIES       = 3

# ── Playwright 設定 ───────────────────────────────────────────────────────────
PLAYWRIGHT_HEADLESS = True
PLAYWRIGHT_TIMEOUT  = 30_000

# ── 幣別 & TWD 匯率 ───────────────────────────────────────────────────────────
DISPLAY_CURRENCY = "TWD"    # 顯示幣別

# 備用固定匯率（對 TWD）：若無法取得即時匯率時使用
# 格式：1 外幣 = N 台幣
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
