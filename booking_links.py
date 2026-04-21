"""
booking_links.py — 訂票連結產生器
=====================================
設計原則
--------
1. Google Flights 搜尋連結（TFS 編碼 URL）— 最精確，永遠優先顯示
2. 航空公司官網直達連結 — 由航線參數組合，作為備用管道
3. 代理商連結 — 由 AGENT_PRIORITY 控制，預設全停用，待評估後逐步開放

連結來源說明
------------
Google Flights 連結：
  使用 #flt= hash 格式產生深層連結 URL，包含出發/回程日期、
  機場、經停等完整資訊，直接對應到搜尋結果頁。

航空公司官網連結：
  使用各航空公司的查詢參數 URL。由於各家公司可能更新 URL 結構，
  建議定期驗證有效性。新增航空公司只需在 _ALL_AIRLINE_BUILDERS 追加 class。

代理商連結（目前停用）：
  架構保留，未來評估後在 AGENT_PRIORITY 解除註解即可啟用。
  Playwright 批次擷取（精確取得代理人直售連結）也保留為未來擴充點。

架構
----
  BookingLink        — 單一連結（label + url + is_google_flights + is_direct）
  BookingLinkSet     — 一筆航班的所有連結組合
  _AirlineBuilder    — 各航空公司 URL builder 基底 class
  BookingLinkFactory — 主要入口，from_record(FlightRecord) → BookingLinkSet
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from urllib.parse import urlencode

if TYPE_CHECKING:
    from database import FlightRecord

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  設定（全部集中於此，修改只需動這裡）
# ══════════════════════════════════════════════════════════════════════════════

# 代理商優先順序
# 要啟用某代理商：取消 # 號後重啟程式，不需要其他改動
AGENT_PRIORITY: list[tuple[str, str]] = [
    # ("skyscanner",   "Skyscanner"),    # TODO: 評估手續費後開放
    # ("trip_com",     "Trip.com"),      # TODO: 評估服務品質後開放
    # ("kayak",        "Kayak"),         # TODO: 待評估
    # ("kiwi",         "Kiwi.com"),      # TODO: 退票政策待確認
]

MAX_AIRLINE_LINKS: int = 2   # 最多顯示幾個航空公司官網連結
MAX_AGENT_LINKS:   int = 2   # 最多顯示幾個代理商連結


# ══════════════════════════════════════════════════════════════════════════════
#  資料模型
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BookingLink:
    label:             str
    url:               str
    is_google_flights: bool = False   # True = Google Flights
    is_direct:         bool = False   # True = 航空公司官網
    priority:          int  = 99

    def __str__(self) -> str:
        if self.is_google_flights:
            return f"🔍 {self.label}:\n     {self.url}"
        if self.is_direct:
            return f"✈  {self.label}:\n     {self.url}"
        return f"🔗 {self.label}:\n     {self.url}"


@dataclass
class BookingLinkSet:
    google_link:   Optional[BookingLink] = None
    airline_links: List[BookingLink]     = field(default_factory=list)
    agent_links:   List[BookingLink]     = field(default_factory=list)

    @property
    def all_links(self) -> List[BookingLink]:
        links: list[BookingLink] = []
        if self.google_link:
            links.append(self.google_link)
        links.extend(self.airline_links)
        links.extend(self.agent_links)
        return sorted(links, key=lambda l: l.priority)

    @property
    def primary(self) -> Optional[BookingLink]:
        """最優先的訂票連結（通常是航空公司直售，若無則 Google Flights）。"""
        # Prefer airline direct over Google Flights
        if self.airline_links:
            return self.airline_links[0]
        return self.google_link

    @property
    def google_or_primary(self) -> Optional[BookingLink]:
        """Google Flights 連結（CSV 用）。"""
        return self.google_link

    def has_links(self) -> bool:
        return bool(self.google_link or self.airline_links or self.agent_links)


# ══════════════════════════════════════════════════════════════════════════════
#  Google Flights URL 建構
# ══════════════════════════════════════════════════════════════════════════════

def _build_google_flights_url(
    from_airport: str,
    to_airport: str,
    depart_date: str,
    return_date: str = "",
    adults: int = 1,
    max_stops: int = -1,
    currency: str = "TWD",
) -> str:
    """
    Build a Google Flights search URL that actually populates the search form.

    Google Flights stopped parsing the legacy `#flt=` hash fragment, so we now
    use the documented natural-language `q=` query parameter. The Google
    Travel search handler parses IATA codes, dates ("on YYYY-MM-DD"), and
    return dates ("through YYYY-MM-DD") and pre-fills the Flights UI.
    """
    # Natural-language query — Google Travel parses this into the Flights form.
    parts = [f"Flights from {from_airport} to {to_airport} on {depart_date}"]
    if return_date:
        parts.append(f"through {return_date}")
    query = " ".join(parts)
    params = urlencode({"q": query, "curr": currency, "hl": "zh-TW"})
    return f"https://www.google.com/travel/flights?{params}"


def _build_google_flights_link(record: "FlightRecord") -> BookingLink:
    """
    建立 Google Flights 深層連結。
    使用 #flt= hash 格式，包含完整的出發/回程日期、機場、經停資訊。
    使用者點擊後直接看到該航線的搜尋結果，無需重新輸入任何資訊。
    """
    url = _build_google_flights_url(
        from_airport=record.departure_airport,
        to_airport=record.arrival_airport,
        depart_date=record.departure_date,
        return_date=record.return_date if record.is_roundtrip else "",
        max_stops=record.stops if record.stops >= 0 else -1,
    )
    return BookingLink(
        label="Google Flights 搜尋結果",
        url=url,
        is_google_flights=True,
        is_direct=False,
        priority=0,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  航空公司官網 Builders
# ══════════════════════════════════════════════════════════════════════════════

class _AirlineBuilder:
    """
    基底 class。子 class 只需實作 build()。
    新增航空公司：建立子 class 後加入 _ALL_AIRLINE_BUILDERS 即可。
    """
    KEYWORDS: tuple[str, ...] = ()

    @classmethod
    def matches(cls, airline_name: str) -> bool:
        n = airline_name.lower().strip()
        return any(kw in n for kw in cls.KEYWORDS)

    @classmethod
    def build(
        cls,
        from_airport: str,
        to_airport:   str,
        depart_date:  str,
        return_date:  str = "",
        adults:       int = 1,
    ) -> Optional[BookingLink]:
        raise NotImplementedError


# ── 台灣本土航空 ──────────────────────────────────────────────────────────────

class EvaAirBuilder(_AirlineBuilder):
    KEYWORDS = ("eva air", "eva", "evaair", "長榮")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="長榮航空 EVA Air",
            url=(f"https://www.evaair.com/en-global/book-and-manage/book-flights/"
                 f"?tripType={trip}&from={from_airport}&to={to_airport}"
                 f"&departDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


class ChinaAirlinesBuilder(_AirlineBuilder):
    KEYWORDS = ("china airlines", "china air", "中華航空", "中华航空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        # CI 官網為 SPA，以下 URL 帶上參數供參考，實際可能需手動輸入
        trip = "roundTrip" if return_date else "oneWay"
        params = urlencode({
            "tripType": trip,
            "departureCity": from_airport,
            "arrivalCity": to_airport,
            "departureDate": depart_date,
            **(({"returnDate": return_date}) if return_date else {}),
            "adultCount": adults,
        })
        return BookingLink(
            label="中華航空 China Airlines",
            url=f"https://www.china-airlines.com/tw/zh?{params}",
            is_direct=True, priority=10,
        )


class StarluxBuilder(_AirlineBuilder):
    KEYWORDS = ("starlux", "星宇")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        # Starlux 官網為 SPA，/booking 頁面正常但 deep link 參數可能被忽略
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="星宇航空 STARLUX",
            url=(f"https://www.starlux-airlines.com/zh-TW/booking"
                 f"?tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date}{ret}&adt={adults}"),
            is_direct=True, priority=10,
        )


class MandarinAirlinesBuilder(_AirlineBuilder):
    KEYWORDS = ("mandarin airlines", "華信", "华信")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        # Mandarin is a regional subsidiary of China Airlines; redirect to CI booking
        return ChinaAirlinesBuilder.build(from_airport, to_airport, depart_date, return_date, adults)


# ── 港澳 ──────────────────────────────────────────────────────────────────────

class CathayBuilder(_AirlineBuilder):
    KEYWORDS = ("cathay pacific", "cathay", "國泰", "国泰")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"/{return_date}" if return_date else ""
        return BookingLink(
            label="國泰航空 Cathay Pacific",
            url=(f"https://www.cathaypacific.com/cx/en_TW/booking/flights/"
                 f"{trip}/{from_airport}/{to_airport}/{depart_date}{ret}?ADT={adults}"),
            is_direct=True, priority=10,
        )


class HongKongExpressBuilder(_AirlineBuilder):
    KEYWORDS = ("hong kong express", "hk express", "香港快運", "香港快运")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="香港快運 HK Express",
            url=(f"https://www.hkexpress.com/zh-tw/booking/book-flight?"
                 f"tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


# ── 日本航空 ──────────────────────────────────────────────────────────────────

class JalBuilder(_AirlineBuilder):
    KEYWORDS = ("jal", "japan airlines", "日本航空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="日本航空 JAL",
            url=(f"https://www.jal.co.jp/en/inter/booking/search.html?"
                 f"type={trip}&from={from_airport}&to={to_airport}"
                 f"&dep={depart_date}{ret}&adt={adults}"),
            is_direct=True, priority=10,
        )


class AnaBuilder(_AirlineBuilder):
    KEYWORDS = ("ana", "all nippon", "全日空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RD" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="全日空 ANA",
            url=(f"https://www.ana.co.jp/en/jp/book-plan/international-fare/"
                 f"?triptype={trip}&dep={from_airport}&arr={to_airport}"
                 f"&depdate={depart_date}{ret}&adult={adults}"),
            is_direct=True, priority=10,
        )


class PeachBuilder(_AirlineBuilder):
    KEYWORDS = ("peach", "樂桃", "乐桃")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="樂桃航空 Peach",
            url=(f"https://www.flypeach.com/tw/lm/ai/airports/roundtrip?"
                 f"from={from_airport}&to={to_airport}&departure={depart_date}"
                 f"{ret}&paxAdult={adults}&type={trip}"),
            is_direct=True, priority=20,
        )


class JetstarBuilder(_AirlineBuilder):
    KEYWORDS = ("jetstar",)
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&ret={return_date}" if return_date else ""
        return BookingLink(
            label="捷星 Jetstar",
            url=(f"https://www.jetstar.com/tw/zh/flights?"
                 f"type={trip}&from={from_airport}&to={to_airport}"
                 f"&dep={depart_date}{ret}&ADT={adults}"),
            is_direct=True, priority=20,
        )


# ── 韓國 ─────────────────────────────────────────────────────────────────────

class KoreanAirBuilder(_AirlineBuilder):
    KEYWORDS = ("korean air", "大韓航空", "대한항공")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date.replace('-', '')}" if return_date else ""
        return BookingLink(
            label="大韓航空 Korean Air",
            url=(f"https://www.koreanair.com/booking/flight-search?"
                 f"tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date.replace('-', '')}{ret}&adultCount={adults}"),
            is_direct=True, priority=10,
        )


class AsianaBuilder(_AirlineBuilder):
    KEYWORDS = ("asiana", "韓亞", "아시아나")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="韓亞航空 Asiana",
            url=(f"https://flyasiana.com/C/TW/ZH/booking/availability?"
                 f"tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&departDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


class JejuAirBuilder(_AirlineBuilder):
    KEYWORDS = ("jeju air", "濟州", "제주항공")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date.replace('-','')}" if return_date else ""
        return BookingLink(
            label="濟州航空 Jeju Air",
            url=(f"https://www.jejuair.net/jejuair/en/booking/selectFlight.do?"
                 f"tripType={trip}&depAirportCode={from_airport}&arrAirportCode={to_airport}"
                 f"&depDate={depart_date.replace('-','')}{ret}&adultCnt={adults}"),
            is_direct=True, priority=20,
        )


# ── 東南亞 ────────────────────────────────────────────────────────────────────

class SingaporeAirlinesBuilder(_AirlineBuilder):
    KEYWORDS = ("singapore airlines", "新加坡航空", "sq ")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="新加坡航空 Singapore Airlines",
            url=(f"https://www.singaporeair.com/en_UK/us/plan-travel/book-a-flight/"
                 f"?tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


class ScootBuilder(_AirlineBuilder):
    KEYWORDS = ("scoot", "酷航")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="酷航 Scoot",
            url=(f"https://www.flyscoot.com/zhtw/book/book-a-flight"
                 f"?tripType={trip}&originStation={from_airport}"
                 f"&destinationStation={to_airport}&departureDate={depart_date}"
                 f"{ret}&adultCount={adults}"),
            is_direct=True, priority=20,
        )


class TigerairTWBuilder(_AirlineBuilder):
    KEYWORDS = ("tigerair taiwan", "tiger air", "台灣虎航", "台湾虎航")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&ReturnDate={return_date}" if return_date else ""
        return BookingLink(
            label="台灣虎航 Tigerair Taiwan",
            url=(f"https://www.tigerairtw.com/zh-tw/booking/search?"
                 f"trip={trip}&from={from_airport}&to={to_airport}"
                 f"&DepartureDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=20,
        )


class AirAsiaBuilder(_AirlineBuilder):
    KEYWORDS = ("airasia", "air asia", "亞洲航空", "亚洲航空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="亞洲航空 AirAsia",
            url=(f"https://www.airasia.com/flights/search?"
                 f"origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date}{ret}&adult={adults}&tripType={trip}"),
            is_direct=True, priority=20,
        )


class MalaysiaAirlinesBuilder(_AirlineBuilder):
    KEYWORDS = ("malaysia airlines", "馬來西亞航空", "马来西亚航空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="馬來西亞航空 Malaysia Airlines",
            url=(f"https://www.malaysiaairlines.com/tw/zh/flight-search.html?"
                 f"tripType={trip}&from={from_airport}&to={to_airport}"
                 f"&departDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


class ThaiAirwaysBuilder(_AirlineBuilder):
    KEYWORDS = ("thai airways", "泰國航空", "泰国航空", "การบินไทย")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&return_date={return_date}" if return_date else ""
        return BookingLink(
            label="泰國航空 Thai Airways",
            url=(f"https://www.thaiairways.com/en_TH/book_a_flight/search_flights.page?"
                 f"origin={from_airport}&destination={to_airport}"
                 f"&departure_date={depart_date}{ret}&adults={adults}&trip_type={trip}"),
            is_direct=True, priority=10,
        )


class VietjetBuilder(_AirlineBuilder):
    KEYWORDS = ("vietjet", "越捷")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="越捷航空 VietJet",
            url=(f"https://www.vietjetair.com/en/pages/search-select-flight?"
                 f"tripType={trip}&from={from_airport}&to={to_airport}"
                 f"&departureDate={depart_date}{ret}&adult={adults}"),
            is_direct=True, priority=20,
        )


class PhilippineAirlinesBuilder(_AirlineBuilder):
    KEYWORDS = ("philippine airlines", "philippine air", "菲律賓航空", "菲律宾航空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="菲律賓航空 Philippine Airlines",
            url=(f"https://www.philippineairlines.com/en/ph/home/bookflights?"
                 f"tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


class ThaiLionAirBuilder(_AirlineBuilder):
    KEYWORDS = ("thai lion", "lion air thailand")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&r={return_date}" if return_date else ""
        return BookingLink(
            label="泰國獅子航空 Thai Lion Air",
            url=(f"https://www.lionairthai.com/en/book/flight-search?"
                 f"type={trip}&from={from_airport}&to={to_airport}"
                 f"&out={depart_date}{ret}&adt={adults}"),
            is_direct=True, priority=20,
        )


# ── 中東 ─────────────────────────────────────────────────────────────────────

class EmiratesBuilder(_AirlineBuilder):
    KEYWORDS = ("emirates", "阿聯酋", "阿联酋")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="阿聯酋航空 Emirates",
            url=(f"https://www.emirates.com/tw/chinese/booking/flexiCalendar/?"
                 f"origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date}{ret}&adult={adults}&type={trip}"),
            is_direct=True, priority=10,
        )


class QatarAirwaysBuilder(_AirlineBuilder):
    KEYWORDS = ("qatar airways", "qatar", "卡達", "卡塔尔")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returningDate={return_date}" if return_date else ""
        return BookingLink(
            label="卡達航空 Qatar Airways",
            url=(f"https://www.qatarairways.com/zh-tw/booking/flights?"
                 f"tripType={trip}&fromStation={from_airport}&toStation={to_airport}"
                 f"&departingDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


class TurkishAirlinesBuilder(_AirlineBuilder):
    KEYWORDS = ("turkish airlines", "土耳其航空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="土耳其航空 Turkish Airlines",
            url=(f"https://www.turkishairlines.com/zh-int/flights?"
                 f"from={from_airport}&to={to_airport}"
                 f"&departure={depart_date}{ret}&pax={adults}&type={trip}"),
            is_direct=True, priority=10,
        )


# ── 歐洲 ─────────────────────────────────────────────────────────────────────

class LufthansaBuilder(_AirlineBuilder):
    KEYWORDS = ("lufthansa", "漢莎", "汉莎")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="漢莎航空 Lufthansa",
            url=(f"https://www.lufthansa.com/tw/en/flight-search?"
                 f"tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


class BritishAirwaysBuilder(_AirlineBuilder):
    KEYWORDS = ("british airways", "英國航空", "英国航空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="英國航空 British Airways",
            url=(f"https://www.britishairways.com/travel/book/public/en_tw?"
                 f"eId=106011&Oc={from_airport}&Dc={to_airport}"
                 f"&OS={depart_date}{ret}&AD={adults}&PA={trip}"),
            is_direct=True, priority=10,
        )


class AirFranceBuilder(_AirlineBuilder):
    KEYWORDS = ("air france", "法國航空", "法国航空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "ROUND_TRIP" if return_date else "ONE_WAY"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="法國航空 Air France",
            url=(f"https://wwws.airfrance.tw/search/offers?"
                 f"tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&outwardDate={depart_date}{ret}&adults={adults}&cabin=ECONOMY"),
            is_direct=True, priority=10,
        )


class KlmBuilder(_AirlineBuilder):
    KEYWORDS = ("klm", "荷蘭皇家", "荷兰皇家")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "ROUND_TRIP" if return_date else "ONE_WAY"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="荷蘭皇家航空 KLM",
            url=(f"https://www.klm.com/search/offers?"
                 f"tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&outwardDate={depart_date}{ret}&adults={adults}&cabin=ECONOMY"),
            is_direct=True, priority=10,
        )


class FinnairBuilder(_AirlineBuilder):
    KEYWORDS = ("finnair", "芬蘭", "芬兰")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "return" if return_date else "oneway"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="芬蘭航空 Finnair",
            url=(f"https://www.finnair.com/tw-zh/flights/{from_airport.lower()}-{to_airport.lower()}"
                 f"?trip={trip}&outbound={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


# ── 大洋洲 ────────────────────────────────────────────────────────────────────

class QantasBuilder(_AirlineBuilder):
    KEYWORDS = ("qantas", "澳洲航空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "return" if return_date else "oneway"
        ret  = f"&return={return_date}" if return_date else ""
        return BookingLink(
            label="澳洲航空 Qantas",
            url=(f"https://www.qantas.com/au/en/book-a-trip/flights?"
                 f"adults={adults}&departure={from_airport}&destination={to_airport}"
                 f"&travel={depart_date}{ret}&type={trip}"),
            is_direct=True, priority=10,
        )


class AirNewZealandBuilder(_AirlineBuilder):
    KEYWORDS = ("air new zealand", "紐西蘭", "纽西兰")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "return" if return_date else "oneway"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="紐西蘭航空 Air New Zealand",
            url=(f"https://www.airnewzealand.co.nz/flights?"
                 f"origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date}{ret}&adults={adults}&type={trip}"),
            is_direct=True, priority=10,
        )


# ── 所有航空公司 builder 清單（新增航空公司：在此追加即可）─────────────────────
_ALL_AIRLINE_BUILDERS: list[type[_AirlineBuilder]] = [
    # 台灣本土
    EvaAirBuilder,
    ChinaAirlinesBuilder,
    StarluxBuilder,
    MandarinAirlinesBuilder,
    # 港澳
    CathayBuilder,
    HongKongExpressBuilder,
    # 韓國（Asiana 必須在 ANA 之前，避免 "ana" 子字串誤匹配 "asiana"）
    KoreanAirBuilder,
    AsianaBuilder,
    JejuAirBuilder,
    # 日本
    JalBuilder,
    AnaBuilder,
    PeachBuilder,
    JetstarBuilder,
    # 東南亞 傳統
    SingaporeAirlinesBuilder,
    MalaysiaAirlinesBuilder,
    ThaiAirwaysBuilder,
    PhilippineAirlinesBuilder,
    VietjetBuilder,
    # 東南亞 廉航
    ScootBuilder,
    TigerairTWBuilder,
    AirAsiaBuilder,
    ThaiLionAirBuilder,
    # 中東
    EmiratesBuilder,
    QatarAirwaysBuilder,
    TurkishAirlinesBuilder,
    # 歐洲
    LufthansaBuilder,
    BritishAirwaysBuilder,
    AirFranceBuilder,
    KlmBuilder,
    FinnairBuilder,
    # 大洋洲
    QantasBuilder,
    AirNewZealandBuilder,
]


# ══════════════════════════════════════════════════════════════════════════════
#  代理商 Builders（目前全部停用，待評估後在 AGENT_PRIORITY 開放）
# ══════════════════════════════════════════════════════════════════════════════

class _AgentBuilder:
    AGENT_ID: str = ""
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1) -> BookingLink:
        raise NotImplementedError


class SkyscannerBuilder(_AgentBuilder):
    AGENT_ID = "skyscanner"
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        # Skyscanner 使用 lowercase IATA / YYMMDD 日期 / 分段路徑
        orig = from_airport.lower()
        dest = to_airport.lower()
        dep  = depart_date.replace("-", "")[2:]   # YYYYMMDD → YYMMDD
        if return_date:
            ret  = return_date.replace("-", "")[2:]
            path = f"{orig}/{dest}/{dep}/{ret}"
        else:
            path = f"{orig}/{dest}/{dep}"
        return BookingLink(
            label="Skyscanner",
            url=f"https://www.skyscanner.com.tw/transport/flights/{path}/?adults={adults}&cabinclass=economy",
            priority=30,
        )


class TripComBuilder(_AgentBuilder):
    AGENT_ID = "trip_com"
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "2" if return_date else "1"
        ret  = f"&ReturnDate={return_date}" if return_date else ""
        return BookingLink(
            label="Trip.com",
            url=(f"https://tw.trip.com/flights/flightlist?"
                 f"dcity={from_airport}&acity={to_airport}"
                 f"&ddate={depart_date}{ret}&triptype={trip}&class=y&adult={adults}"),
            priority=31,
        )


class KayakBuilder(_AgentBuilder):
    AGENT_ID = "kayak"
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        base = f"{from_airport}-{to_airport}/{depart_date}"
        if return_date:
            base += f"/{return_date}"
        return BookingLink(
            label="Kayak",
            url=f"https://www.kayak.com.tw/flights/{base}/{adults}adults?cabin=economy",
            priority=32,
        )


class KiwiBuilder(_AgentBuilder):
    AGENT_ID = "kiwi"
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        return BookingLink(
            label="Kiwi.com",
            url=f"https://www.kiwi.com/en/search/results/{from_airport}/{to_airport}/{depart_date}",
            priority=33,
        )


_AGENT_BUILDER_MAP: dict[str, type[_AgentBuilder]] = {
    "skyscanner": SkyscannerBuilder,
    "trip_com":   TripComBuilder,
    "kayak":      KayakBuilder,
    "kiwi":       KiwiBuilder,
}


# ══════════════════════════════════════════════════════════════════════════════
#  主要工廠
# ══════════════════════════════════════════════════════════════════════════════

class BookingLinkFactory:
    """
    主要入口：給定一筆 FlightRecord，產生 BookingLinkSet。

    連結優先順序：
      1. Google Flights（TFS 精確連結）— 永遠產生
      2. 航空公司官網（由航線參數組合）
      3. 代理商（由 AGENT_PRIORITY 控制，預設全停用）

    未來擴充：
      Playwright 批次擷取可在 reporter.export_csv() 前呼叫
      airline_booking_urls.enrich_booking_urls()，將結果存入
      record.booking_url，此工廠不需改動。

    使用範例：
      link_set = BookingLinkFactory.from_record(record)
      for link in link_set.all_links:
          print(link)
    """

    @classmethod
    def from_record(cls, record: "FlightRecord", adults: int = 1) -> BookingLinkSet:
        link_set = BookingLinkSet()

        # ── 1. Google Flights 連結（永遠建立）─────────────────────────────
        link_set.google_link = _build_google_flights_link(record)

        # ── 2. 航空公司官網連結 ────────────────────────────────────────────
        airline_links: list[BookingLink] = []
        # Handle combined names like "Scoot / Jetstar" or "EVA Air / Peach"
        for name_part in (record.airline or "").split("/"):
            name_part = name_part.strip()
            if not name_part:
                continue
            for builder_cls in _ALL_AIRLINE_BUILDERS:
                if builder_cls.matches(name_part):
                    try:
                        link = builder_cls.build(
                            from_airport=record.departure_airport,
                            to_airport=record.arrival_airport,
                            depart_date=record.departure_date,
                            return_date=record.return_date if record.is_roundtrip else "",
                            adults=adults,
                        )
                        if link and link.url not in {l.url for l in airline_links}:
                            airline_links.append(link)
                    except Exception as e:
                        logger.debug(f"Builder {builder_cls.__name__} failed: {e}")
                    break  # Only first matching builder per name part
            if len(airline_links) >= MAX_AIRLINE_LINKS:
                break
        link_set.airline_links = airline_links

        # ── 3. 代理商連結（由 AGENT_PRIORITY 控制）────────────────────────
        agent_links: list[BookingLink] = []
        for priority_idx, (agent_id, _) in enumerate(AGENT_PRIORITY):
            builder_cls = _AGENT_BUILDER_MAP.get(agent_id)
            if not builder_cls:
                continue
            try:
                link = builder_cls.build(
                    from_airport=record.departure_airport,
                    to_airport=record.arrival_airport,
                    depart_date=record.departure_date,
                    return_date=record.return_date if record.is_roundtrip else "",
                    adults=adults,
                )
                if link:
                    link.priority = 30 + priority_idx
                    agent_links.append(link)
            except Exception as e:
                logger.debug(f"Agent builder {agent_id} failed: {e}")
            if len(agent_links) >= MAX_AGENT_LINKS:
                break
        link_set.agent_links = agent_links

        return link_set


# ══════════════════════════════════════════════════════════════════════════════
#  格式化工具（供 reporter.py 使用）
# ══════════════════════════════════════════════════════════════════════════════

def format_links_rich(link_set: BookingLinkSet) -> str:
    """
    回傳 Rich 格式字串供表格欄位顯示（只顯示標籤，不嵌入 URL）。
    URL 含特殊字元（&、=、%）會導致 Rich MarkupError，所以不嵌超連結。
    完整 URL 在表格下方的「訂票連結」區塊另行列印。
    """
    if not link_set.has_links():
        return "[dim]—[/dim]"
    lines = []
    for link in link_set.all_links:
        if link.is_google_flights:
            lines.append(f"[bold cyan]🔍 {link.label}[/bold cyan]")
        elif link.is_direct:
            lines.append(f"[green]✈  {link.label}[/green]")
        else:
            lines.append(f"[dim]🔗 {link.label}[/dim]")
    return "\n".join(lines)


def format_links_plain(link_set: BookingLinkSet) -> list[str]:
    """回傳純文字連結清單（含完整 URL），供 plain text 模式或表格下方列印。"""
    if not link_set.has_links():
        return []
    result = []
    for link in link_set.all_links:
        if link.is_google_flights:
            pfx = "🔍"
        elif link.is_direct:
            pfx = "✈ "
        else:
            pfx = "🔗"
        result.append(f"{pfx} {link.label}:\n     {link.url}")
    return result