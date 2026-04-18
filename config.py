"""
config.py — Global configuration
=================================
All tunable parameters are centralised here.
"""
import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ── Departure airports ───────────────────────────────────────────────────────
DEPARTURE_AIRPORTS = ["TPE", "TSA"]
DEFAULT_DEPARTURE  = "TPE"

# ── Destination list (grouped by region) ────────────────────────────────────
# Each key is an atomic region name (canonical English key).
# Chinese aliases and composite regions are defined below in REGION_ALIASES / COMPOSITE_REGIONS.
WORLD_DESTINATIONS: dict[str, list[str]] = {
    "Japan": [
        # ✈ Nonstop from TPE
        "NRT", "HND", "KIX", "NGO", "CTS", "FUK", "OKA",
        "HKD", "AKJ", "AOJ", "SDJ", "HNA", "AXT", "FKS", "KMQ",
        "HSG", "KMJ", "KOJ", "OKJ", "TAK", "HIJ", "KCZ",
        "MYJ", "OIT", "UKB", "IBR", "KKJ", "ISG", "YGJ", "SHI",
    ],
    "Korea": [
        "ICN", "GMP", "PUS", "CJU", "TAE", "CJJ", "MWX",
    ],
    "SE Asia": [
        "BKK", "DMK", "SIN", "KUL", "CGK", "MNL", "CRK",
        "DPS", "HAN", "SGN", "DAD", "NHA", "CEB",
        "CNX", "PQC", "PEN", "BKI", "BWN",
        "RGN", "MDL", "REP", "PNH", "VTE",
    ],
    "Europe": [
        "AMS", "FRA", "LHR", "VIE", "IST", "PRG",
        "CDG", "FCO", "BCN", "MAD", "ZRH", "MUC", "BER",
        "WAW", "ARN", "CPH", "HEL", "ATH", "LIS", "DUB",
    ],
    "N America": [
        "SFO", "LAX", "SEA", "JFK", "ORD", "DFW",
        "PHX", "ONT", "GUM",
        "YVR", "YYZ",
        "BOS", "MIA", "IAD",
    ],
    "Oceania": [
        "SYD", "MEL", "BNE", "AKL", "PER",
    ],
    # "S Asia":       ["DEL", "BOM", "MAA", "BLR", "CMB", "KTM", "DAC"],
    # "Middle East":  ["DXB", "AUH", "DOH", "RUH", "KWI", "AMM", "BEY"],
    # "Africa":       ["NBO", "JNB", "CAI", "CMN", "ADD"],
    # "S America":    ["GRU", "EZE", "BOG", "LIM", "SCL"],
}

ALL_DESTINATIONS: list[str] = list(dict.fromkeys(
    code for codes in WORLD_DESTINATIONS.values() for code in codes
))

# ── Bilingual aliases → canonical key ───────────────────────────────────────
# Users can type Mandarin or English; automatically maps to a WORLD_DESTINATIONS key.
REGION_ALIASES: dict[str, str] = {
    # Mandarin
    "日本":   "Japan",
    "韓國":   "Korea",
    "東南亞": "SE Asia",
    "歐洲":   "Europe",
    "北美":   "N America",
    "大洋洲": "Oceania",
    # English variants
    "Southeast Asia": "SE Asia",
    "North America":  "N America",
    # Legacy keys (backward compatibility with old --dest arguments)
    "東南亞 SE Asia": "SE Asia",
    "歐洲 Europe":    "Europe",
    "北美 N America": "N America",
    "大洋洲 Oceania": "Oceania",
}

# ── Composite regions (semantic groups spanning multiple atomic regions) ──────
COMPOSITE_REGIONS: dict[str, list[str]] = {
    "NE Asia":   ["Japan", "Korea"],
    "East Asia": ["Japan", "Korea", "SE Asia"],
}
COMPOSITE_ALIASES: dict[str, str] = {
    "東北亞":         "NE Asia",
    "Northeast Asia": "NE Asia",
    "東亞":           "East Asia",
}

# ── Asia regions (short-haul / Vacation Mode) ───────────────────────────────
ASIA_REGIONS: set[str] = {
    "Japan", "Korea", "SE Asia",
    # "S Asia", "Middle East",
}
ASIA_DESTINATIONS: list[str] = list(dict.fromkeys(
    code
    for region, codes in WORLD_DESTINATIONS.items()
    if region in ASIA_REGIONS
    for code in codes
))

# ── Non-Asia regions (intercontinental / Vacation Mode) ─────────────────────
NON_ASIA_REGIONS: set[str] = {
    "Europe", "N America", "Oceania",
    # "Africa", "S America",
}
NON_ASIA_DESTINATIONS: list[str] = list(dict.fromkeys(
    code
    for region, codes in WORLD_DESTINATIONS.items()
    if region in NON_ASIA_REGIONS
    for code in codes
))

# ── Transfer rules ───────────────────────────────────────────────────────────
# Short-haul Asia → nonstop only (0 stops)
NONSTOP_ONLY_REGIONS: set[str] = {"Japan", "Korea", "SE Asia"}
INTERCONTINENTAL_REGIONS: set[str] = {
    "Europe", "N America", "Oceania",
    # "Africa", "S America",
}

# ── Personal favourite destinations ──────────────────────────────────────────
MY_DESTINATIONS: list[str] = [
    "NRT", "KIX",        # Japan
    "ICN",               # Korea
    "BKK", "DPS",        # SE Asia
    "SIN",               # Singapore
    "LHR", "CDG",        # Europe
    "LAX", "SFO",        # N America
]

FAVOURITE_GROUPS: dict[str, list[str]] = {
    # "🏖️  Holiday picks": ["DPS", "BKK", "SIN", "NRT", "KIX"],
    # "🗺️  Long-haul": ["LHR", "CDG", "LAX", "SYD"],
}

# ── User-defined destinations (airports outside any region, freely added) ─────
USER_DESTINATIONS: list[str] = [
    # Add any airport codes you want to track that are not covered above, e.g.:
    # "KTM",  # Kathmandu
    # "DXB",  # Dubai
]

_AIRPORT_TO_REGION: dict[str, str] = {
    code: region
    for region, codes in WORLD_DESTINATIONS.items()
    for code in codes
}


def get_region(airport: str) -> str:
    return _AIRPORT_TO_REGION.get(airport.upper(), "")


def resolve_destinations(name: str) -> list[str] | None:
    """
    Unified destination name resolver.
    1. WORLD_DESTINATIONS canonical key (e.g. "Japan")
    2. REGION_ALIASES (e.g. "歐洲" → all Europe airports)
    3. COMPOSITE_REGIONS / COMPOSITE_ALIASES (e.g. "東北亞" → Japan + Korea)
    Returns a list of airport codes, or None if not found.
    """
    # 1. 直接 key
    if name in WORLD_DESTINATIONS:
        return list(WORLD_DESTINATIONS[name])
    # 2. alias → atomic region
    canonical = REGION_ALIASES.get(name)
    if canonical and canonical in WORLD_DESTINATIONS:
        return list(WORLD_DESTINATIONS[canonical])
    # 3. composite key
    if name in COMPOSITE_REGIONS:
        return _expand_composite(name)
    # 4. composite alias
    comp_key = COMPOSITE_ALIASES.get(name)
    if comp_key and comp_key in COMPOSITE_REGIONS:
        return _expand_composite(comp_key)
    return None


def _expand_composite(comp_key: str) -> list[str]:
    codes: list[str] = []
    for region_key in COMPOSITE_REGIONS[comp_key]:
        codes.extend(WORLD_DESTINATIONS.get(region_key, []))
    return list(dict.fromkeys(codes))


def get_max_stops_for(airport: str, default_max: int = 2) -> int:
    """
    Determine max_stops for a destination:
    - Short-haul Asia regions → 0 (nonstop only)
    - All other regions → default_max
    """
    region = get_region(airport.upper())
    if region in NONSTOP_ONLY_REGIONS:
        return 0
    return default_max


def is_intercontinental(airport: str) -> bool:
    return get_region(airport) in INTERCONTINENTAL_REGIONS


# ── Flight constraints ───────────────────────────────────────────────────────
MAX_STOPS          = 2
MAX_DURATION_HOURS = 26
DEFAULT_FLEX_DAYS  = 0

# ── Default trip lengths ─────────────────────────────────────────────────────
ASIA_DEFAULT_TRIP_DAYS  = 5
INTER_DEFAULT_TRIP_DAYS = 9
INTER_TRIP_MIN_DAYS     = 8
INTER_TRIP_MAX_DAYS     = 18

# ── Search passengers ────────────────────────────────────────────────────────
ADULTS   = 1
CHILDREN = 0
INFANTS  = 0

# ── Scheduler ────────────────────────────────────────────────────────────────
SCHEDULE_TIME = "07:00"

# ── Holiday search settings ───────────────────────────────────────────────────
HOLIDAY_LOOKAHEAD_DAYS = 180
MIN_TRIP_DAYS          = 3
MAX_TRIP_DAYS          = 18

# ── Database ─────────────────────────────────────────────────────────────────
DB_PATH = BASE_DIR / "flights.db"

# ── Reports ───────────────────────────────────────────────────────────────────
REPORT_DIR    = BASE_DIR / "reports"
TOP_N_RESULTS = 20

# ── Request rate limiting ─────────────────────────────────────────────────────
REQUEST_DELAY_SEC = 2.5
MAX_RETRIES       = 3

# ── Playwright settings ───────────────────────────────────────────────────────
PLAYWRIGHT_HEADLESS = True
PLAYWRIGHT_TIMEOUT  = 30_000

# ══════════════════════════════════════════════════════════════════════════════
#  Vacation modes
# ══════════════════════════════════════════════════════════════════════════════

VACATION_MODES: dict[str, dict] = {
    "short": {
        "label":        "🏖️  Short trip",
        "days":         5,
        "flex_days":    1,
        "weekends":     1,
        "max_stops":    0,          # nonstop only (forced)
        "max_duration": 10,
        "destinations": "asia",
        "horizon":      180,
    },
    "long": {
        "label":        "✈️  Long-haul trip",
        "days":         9,
        "flex_days":    1,
        "weekends":     2,
        "max_stops":    2,
        "max_duration": 26,
        "destinations": "non_asia",
        "horizon":      365,
    },
    "happy": {
        "label":        "🌍 Happy holiday",
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
#  Notification settings (optional — set env vars or fill in strings below)
#  Supports LINE Notify, Telegram Bot, Email (SMTP)
# ══════════════════════════════════════════════════════════════════════════════

LINE_NOTIFY_TOKEN  = os.getenv("LINE_NOTIFY_TOKEN",  "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "")

SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER",     "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

# Send notification only when price is below this threshold (TWD)
PRICE_ALERT_THRESHOLD_TWD = int(os.getenv("PRICE_ALERT_THRESHOLD_TWD", "15000"))

# Display currency for reports (does not affect search, only notification formatting)
DISPLAY_CURRENCY = os.getenv("DISPLAY_CURRENCY", "TWD")

# Fallback exchange rates for converting non-TWD prices in notifications (approximate)
TWD_FALLBACK_RATES: dict[str, float] = {
    "TWD": 1.0,
    "USD": 32.5,  "EUR": 35.0,  "GBP": 41.0,
    "JPY": 0.22,  "KRW": 0.025, "HKD": 4.1,
    "SGD": 24.0,  "MYR": 7.2,   "THB": 0.91,
    "AUD": 21.5,  "NZD": 19.5,  "CAD": 24.0,
    "CNY": 4.5,   "INR": 0.39,  "AED": 8.8,
    "QAR": 8.9,
}
