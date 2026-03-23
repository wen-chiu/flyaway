"""
airline_classifier.py — 傳統航空 vs 廉航分類
==============================================
"""
from __future__ import annotations

# 已知廉航清單（全小寫比對）
_LCC_NAMES: frozenset[str] = frozenset({
    # 亞太
    "scoot", "jetstar", "jetstar japan", "jetstar asia", "jetstar pacific",
    "peach", "peach aviation",
    "airasia", "airasia x", "air asia", "air asia x",
    "thai airasia", "thai airasia x", "thai air asia", "thai air asia x",
    "indonesia airasia", "airasia india",
    "cebu pacific", "cebu air",
    "lion air", "thai lion air", "malindo air", "batik air",
    "spring airlines", "spring japan",
    "vanilla air",
    "nok air", "nokair", "nok scoot",
    "vietjet", "vietjet air",
    "bamboo airways",
    "citilink",
    "tigerair", "tigerair taiwan", "tiger air", "tiger airways",
    "starflyer",
    "air do", "solaseed air", "skymark",
    "t'way air", "tway air", "jeju air", "jin air",
    "eastar jet", "air busan",
    "flyscoot",
    "indigo", "spicejet", "go first", "go air", "air india express",
    "flydubai", "air arabia", "jazeera airways",
    "flynas", "flyadeal",
    # 歐洲
    "ryanair", "easyjet", "wizz air", "volotea", "vueling",
    "transavia", "norwegian", "jet2", "blue air",
    "flybe", "lauda", "lauda europe",
    # 北美
    "southwest", "frontier", "spirit", "allegiant", "sun country",
    "flair airlines", "swoop",
    # 大洋洲
    "jetstar airways",
})

def classify_airline(airline_name: str) -> str:
    """
    回傳 'LCC'、'traditional' 或 'unknown'。
    支援 'Airline1 / Airline2' 格式的組合名稱（取最優分類）。
    """
    if not airline_name or not airline_name.strip():
        return "unknown"

    # Handle combined names like "Scoot / Jetstar" or "EVA Air / Peach"
    parts = [p.strip() for p in airline_name.split("/")]
    results = set()
    for part in parts:
        name_lower = part.strip().lower()
        if not name_lower:
            continue
        if name_lower in _LCC_NAMES:
            results.add("LCC")
            continue
        matched = False
        for lcc in _LCC_NAMES:
            if lcc in name_lower:
                results.add("LCC")
                matched = True
                break
        if not matched:
            results.add("traditional")

    if not results:
        return "unknown"
    # LCC wins over traditional (shows user cheapest option category)
    if "LCC" in results:
        return "LCC"
    return "traditional"

def is_lcc(airline_name: str) -> bool:
    return classify_airline(airline_name) == "LCC"