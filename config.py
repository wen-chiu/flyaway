"""
config.py — 全域設定檔
=========================
所有可調整參數集中於此。
"""
from pathlib import Path
 
# ── 路徑 ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
 
# ── 出發機場 ───────────────────────────────────────────────────────────────────
DEPARTURE_AIRPORTS = ["TPE", "TSA"]
DEFAULT_DEPARTURE  = "TPE"

# ── 目的地清單 (依地區分組) ──────────────────────────────────────────────────
WORLD_DESTINATIONS: dict[str, list[str]] = {
    "Japan":    [ "NRT", "HND", "KIX", "NGO", "CTS", "FUK",
                  "HKD", "AKJ", "SDJ", "HNA", "AXT", "FKS", "KMQ", 
                  "HSG", "KMJ", "KOJ", "OKJ", "TAK", "HIJ", "KCZ",
                  "OKA", "MYJ", "OIT", "UKB", "IBR"],
    "東北亞 NE Asia":    ["GMP", "ICN", "PUS", "OKA", "CJU", "TAE"],
    "東南亞 SE Asia":    ["BKK", "DMK", "SIN", "KUL", "MNL", "CGK",
                          "DPS", "HAN", "SGN", "RGN", "REP", "PNH",
                          "VTE", "MDL", "CNX", "PQC", "DAD", "PEN", "CEB"],
    "歐洲 Europe":       ["LHR", "CDG", "FRA", "AMS", "MAD", "FCO",
                          "BCN", "VIE", "ZRH", "IST", "PRG", "WAW",
                          "ARN", "CPH", "HEL", "ATH", "LIS", "DUB"],
    "北美 N America":    ["JFK", "LAX", "SFO", "ORD", "YVR", "YYZ",
                          "SEA", "DFW", "MIA", "BOS", "IAH", "ONT"],
    "大洋洲 Oceania":    ["SYD", "MEL", "AKL", "BNE", "PER", "CHC"],
    # "南亞 S Asia":       ["DEL", "BOM", "MAA", "BLR", "CMB", "KTM", "DAC"],
    # "非洲 Africa":       ["NBO", "JNB", "CAI", "CMN", "ADD"],
    # "南美 S America":    ["GRU", "EZE", "BOG", "LIM", "SCL"],
    # "中東 Middle East":  ["DXB", "DOH", "AUH", "RUH", "KWI", "AMM", "BEY"],
}

ALL_DESTINATIONS: list[str] = [
    code for codes in WORLD_DESTINATIONS.values() for code in codes
]
 
# ── 亞洲地區（短途/假期模式用）────────────────────────────────────────────────
ASIA_REGIONS: set[str] = {
    "東北亞 NE Asia", "東南亞 SE Asia", "Japan"
    # , "南亞 S Asia", "中東 Middle East"
}
ASIA_DESTINATIONS: list[str] = [
    code for region, codes in WORLD_DESTINATIONS.items()
    if region in ASIA_REGIONS for code in codes
]
 
# 亞洲以外（長途/假期模式用）
NON_ASIA_REGIONS: set[str] = {
    "歐洲 Europe", "北美 N America", "大洋洲 Oceania"
    # , "非洲 Africa", "南美 S America"
}
NON_ASIA_DESTINATIONS: list[str] = [
    code for region, codes in WORLD_DESTINATIONS.items()
    if region in NON_ASIA_REGIONS for code in codes
]
 
# ── 自訂最愛目的地 ─────────────────────────────────────────────────────────────
MY_DESTINATIONS: list[str] = [
    "NRT", "KIX",       # 日本
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
 
# ── 航點轉機規則 ───────────────────────────────────────────────────────────────
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
 
# ── 飛行限制 ───────────────────────────────────────────────────────────────────
MAX_STOPS          = 2
MAX_DURATION_HOURS = 26
DEFAULT_FLEX_DAYS  = 0
 
# ── 旅行天數預設 ───────────────────────────────────────────────────────────────
ASIA_DEFAULT_TRIP_DAYS   = 5
INTER_DEFAULT_TRIP_DAYS  = 9
INTER_TRIP_MIN_DAYS      = 8
INTER_TRIP_MAX_DAYS      = 18
 
# ── 搜尋旅客 ──────────────────────────────────────────────────────────────────
ADULTS   = 1
CHILDREN = 0
INFANTS  = 0
 
# ── 排程設定 ──────────────────────────────────────────────────────────────────
SCHEDULE_TIME = "07:00"
 
# ── 假期搜尋設定 ──────────────────────────────────────────────────────────────
HOLIDAY_LOOKAHEAD_DAYS = 180
MIN_TRIP_DAYS = 3
MAX_TRIP_DAYS = 18
 
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
 
# 三種假期模式（固定天數為預設，可透過 --flex 開啟彈性）
VACATION_MODES: dict[str, dict] = {
    "short": {
        "label":        "🏖️  短途假期",
        "days":         5,          # 固定 5 天
        "flex_days":    1,          # 彈性時：4–6 天
        "weekends":     1,          # 需涵蓋至少 1 個完整週末
        "max_stops":    0,          # 直達
        "max_duration": 10,         # 單程飛行上限（小時）
        "destinations": "asia",     # 亞洲目的地
        "horizon":      180,        # 預設搜尋未來幾天
    },
    "long": {
        "label":        "✈️  長途假期",
        "days":         9,          # 固定 9 天
        "flex_days":    1,          # 彈性時：8–10 天
        "weekends":     2,          # 需涵蓋至少 2 個完整週末
        "max_stops":    2,
        "max_duration": 26,
        "destinations": "non_asia",
        "horizon":      365,
    },
    "happy": {
        "label":        "🌍 快樂假期",
        "days":         16,         # 固定 16 天
        "flex_days":    2,          # 彈性時：14–18 天
        "weekends":     3,          # 需涵蓋至少 3 個完整週末
        "max_stops":    2,
        "max_duration": 26,
        "destinations": "non_asia",
        "horizon":      365,
    },
}
 
VACATION_REQUIRE_TW_HOLIDAY = False  # True = 必含台灣假日
VACATION_TOP_WINDOWS        = 6      # 最多搜尋幾個時間窗口
VACATION_TOP_DEST           = 25     # 每窗口搜尋幾個目的地
VACATION_TOP_RESULTS        = 10     # 每窗口顯示幾筆