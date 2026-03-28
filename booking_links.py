"""
booking_links.py — 訂票連結產生器
=====================================
設計原則：
  1. 航空公司官網連結優先
  2. 若官網票價比代理商貴超過 AGENT_PRICE_THRESHOLD (預設 10%)，附加代理商連結
  3. 代理商優先順序在 AGENT_PRIORITY 中集中設定，未來評估後可調整
  4. 所有 URL 樣板集中在各自的 builder class 內，易於維護

架構：
  BookingLinkSet     — 一筆航班的所有連結容器
  AirlineBooking     — 各航空公司官網 deep-link builder（一公司一 class）
  AgentBooking       — 代理商連結 builder（一代理商一 class）
  BookingLinkFactory — 主要入口，組合並回傳 BookingLinkSet
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlencode, quote


# ══════════════════════════════════════════════════════════════════════════════
#  設定（全部集中於此）
# ══════════════════════════════════════════════════════════════════════════════

# 官網票價比代理商貴幾 % 以上，才顯示代理商連結（10 = 10%）
AGENT_PRICE_THRESHOLD: float = 10.0

# ── 代理商優先順序 ────────────────────────────────────────────────────────────
# TODO: 評估各代理商的服務品質、手續費、退改票彈性後調整順序
# 格式：(代理商 ID, 顯示名稱)
# 若要暫時停用某代理商，在前面加 #
AGENT_PRIORITY: list[tuple[str, str]] = [
    # ── 優先推薦 ──────────────────────────────────────────────────────────────
    ("google_flights",  "Google Flights"),    # 最佳比價入口，無手續費導購
    ("skyscanner",      "Skyscanner"),        # TODO: 評估手續費政策
    ("trip_com",        "Trip.com"),          # TODO: 評估服務品質
    # ── 次要選項 ──────────────────────────────────────────────────────────────
    # ("kayak",         "Kayak"),             # TODO: 待評估
    # ("kiwi",          "Kiwi.com"),          # TODO: 待評估（注意退票政策）
    # ("expedia",       "Expedia"),           # TODO: 待評估
]

# 最多顯示幾個代理商連結
MAX_AGENT_LINKS: int = 2


# ══════════════════════════════════════════════════════════════════════════════
#  資料模型
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BookingLink:
    """單一訂票連結。"""
    label:     str    # 顯示名稱，如 "EVA Air 官網" / "Google Flights"
    url:       str    # 完整 URL
    is_direct: bool   # True = 航空公司官網；False = 代理商
    priority:  int    # 排序用，數字越小越優先

    def __str__(self) -> str:
        tag = "✈ 官網" if self.is_direct else "🔗 代理"
        return f"{tag} {self.label}: {self.url}"


@dataclass
class BookingLinkSet:
    """一筆航班的所有訂票連結組合。"""
    airline_links: List[BookingLink] = field(default_factory=list)   # 官網連結
    agent_links:   List[BookingLink] = field(default_factory=list)   # 代理商連結
    show_agents:   bool = False    # 是否因價差 > threshold 而顯示代理商

    @property
    def all_links(self) -> List[BookingLink]:
        links = list(self.airline_links)
        if self.show_agents:
            links.extend(self.agent_links)
        return sorted(links, key=lambda l: l.priority)

    @property
    def primary(self) -> Optional[BookingLink]:
        """最優先的單一連結。"""
        all_ = self.all_links
        return all_[0] if all_ else None

    def has_links(self) -> bool:
        return bool(self.airline_links or (self.show_agents and self.agent_links))


# ══════════════════════════════════════════════════════════════════════════════
#  航空公司官網 Builders
# ══════════════════════════════════════════════════════════════════════════════

class _AirlineBuilder:
    """所有航空公司 builder 的基底 class。子 class 只需實作 build()。"""

    # 子 class 填寫：小寫關鍵字，用於從 airline_name 比對
    KEYWORDS: tuple[str, ...] = ()

    @classmethod
    def matches(cls, airline_name: str) -> bool:
        name_lc = airline_name.lower()
        return any(kw in name_lc for kw in cls.KEYWORDS)

    @classmethod
    def build(
        cls,
        from_airport: str,
        to_airport: str,
        depart_date: str,        # YYYY-MM-DD
        return_date: str = "",   # YYYY-MM-DD or ""
        adults: int = 1,
    ) -> Optional[BookingLink]:
        raise NotImplementedError


class EvaAirBuilder(_AirlineBuilder):
    KEYWORDS = ("eva air", "eva", "evaair")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.evaair.com/en-global/book-and-manage/book-flights/"
            f"?tripType={trip}&from={from_airport}&to={to_airport}"
            f"&departDate={depart_date}{ret}&adults={adults}"
        )
        return BookingLink(label="EVA Air 官網", url=url, is_direct=True, priority=0)


class ChinaAirlinesBuilder(_AirlineBuilder):
    KEYWORDS = ("china airlines", "cal", "china air")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        base = "https://www.china-airlines.com/tw/zh/booking/book-tickets/search"
        params = {
            "tripType": "RT" if return_date else "OW",
            "from": from_airport, "to": to_airport,
            "departDate": depart_date.replace("-", "/"),
            "adult": adults,
        }
        if return_date:
            params["returnDate"] = return_date.replace("-", "/")
        return BookingLink(
            label="中華航空官網",
            url=f"{base}?{urlencode(params)}",
            is_direct=True, priority=0,
        )


class StarluxBuilder(_AirlineBuilder):
    KEYWORDS = ("starlux", "星宇")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.starlux-airlines.com/zh-TW/booking/flights"
            f"?tripType={trip}&origin={from_airport}&destination={to_airport}"
            f"&outbound={depart_date}{ret}&adt={adults}"
        )
        return BookingLink(label="星宇航空官網", url=url, is_direct=True, priority=0)


class CathayBuilder(_AirlineBuilder):
    KEYWORDS = ("cathay pacific", "cathay", "国泰", "國泰")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"/{return_date}" if return_date else ""
        url  = (
            f"https://www.cathaypacific.com/cx/en_TW/booking/flights/"
            f"{trip}/{from_airport}/{to_airport}/{depart_date}{ret}"
            f"?ADT={adults}"
        )
        return BookingLink(label="Cathay Pacific 官網", url=url, is_direct=True, priority=0)


class ScootBuilder(_AirlineBuilder):
    KEYWORDS = ("scoot", "酷航")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.flyscoot.com/zhtw/book/book-a-flight"
            f"?tripType={trip}&originStation={from_airport}"
            f"&destinationStation={to_airport}&departureDate={depart_date}"
            f"{ret}&adultCount={adults}"
        )
        return BookingLink(label="Scoot 酷航官網", url=url, is_direct=True, priority=0)


class JetstarBuilder(_AirlineBuilder):
    KEYWORDS = ("jetstar",)

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&ret={return_date}" if return_date else ""
        url  = (
            f"https://www.jetstar.com/tw/zh/flights?"
            f"type={trip}&from={from_airport}&to={to_airport}"
            f"&dep={depart_date}{ret}&ADT={adults}"
        )
        return BookingLink(label="Jetstar 官網", url=url, is_direct=True, priority=0)


class PeachBuilder(_AirlineBuilder):
    KEYWORDS = ("peach", "樂桃")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.flypeach.com/tw/lm/ai/airports/roundtrip?"
            f"from={from_airport}&to={to_airport}&departure={depart_date}"
            f"{ret}&paxAdult={adults}&type={trip}"
        )
        return BookingLink(label="Peach 樂桃官網", url=url, is_direct=True, priority=0)


class TigerairTWBuilder(_AirlineBuilder):
    KEYWORDS = ("tigerair taiwan", "tigerair tw", "台灣虎航")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&ReturnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.tigerairtw.com/zh-tw/booking/search?"
            f"trip={trip}&from={from_airport}&to={to_airport}"
            f"&DepartureDate={depart_date}{ret}&adults={adults}"
        )
        return BookingLink(label="台灣虎航官網", url=url, is_direct=True, priority=0)


class AirAsiaBuilder(_AirlineBuilder):
    KEYWORDS = ("airasia", "air asia", "亞洲航空")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.airasia.com/flights/search?"
            f"origin={from_airport}&destination={to_airport}"
            f"&departureDate={depart_date}{ret}&adult={adults}&tripType={trip}"
        )
        return BookingLink(label="AirAsia 官網", url=url, is_direct=True, priority=0)


class JalBuilder(_AirlineBuilder):
    KEYWORDS = ("jal", "japan airlines", "日本航空")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.jal.co.jp/en/inter/booking/search.html?"
            f"type={trip}&from={from_airport}&to={to_airport}"
            f"&dep={depart_date}{ret}&adt={adults}"
        )
        return BookingLink(label="JAL 日本航空官網", url=url, is_direct=True, priority=0)


class AnaBuilder(_AirlineBuilder):
    KEYWORDS = ("ana", "all nippon", "全日空")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RD" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.ana.co.jp/en/jp/book-plan/international-fare/"
            f"?triptype={trip}&dep={from_airport}&arr={to_airport}"
            f"&depdate={depart_date}{ret}&adult={adults}"
        )
        return BookingLink(label="ANA 全日空官網", url=url, is_direct=True, priority=0)


class ThaiLionAirBuilder(_AirlineBuilder):
    KEYWORDS = ("thai lion", "lion air thailand", "thai lion air")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        # Thai Lion Air uses a booking portal
        trip = "R" if return_date else "O"
        ret  = f"&r={return_date}" if return_date else ""
        url  = (
            f"https://www.lionairthai.com/en/book/flight-search?"
            f"type={trip}&from={from_airport}&to={to_airport}"
            f"&out={depart_date}{ret}&adt={adults}"
        )
        return BookingLink(label="Thai Lion Air 官網", url=url, is_direct=True, priority=0)


class KoreanAirBuilder(_AirlineBuilder):
    KEYWORDS = ("korean air", "大韓航空")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date.replace('-','')}" if return_date else ""
        url  = (
            f"https://www.koreanair.com/booking/flight-search?"
            f"tripType={trip}&origin={from_airport}&destination={to_airport}"
            f"&departureDate={depart_date.replace('-','')}{ret}&adultCount={adults}"
        )
        return BookingLink(label="Korean Air 官網", url=url, is_direct=True, priority=0)


class SingaporeAirlinesBuilder(_AirlineBuilder):
    KEYWORDS = ("singapore airlines", "sq", "新加坡航空")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.singaporeair.com/en_UK/us/plan-travel/book-a-flight/?tripType={trip}"
            f"&origin={from_airport}&destination={to_airport}"
            f"&departureDate={depart_date}{ret}&adults={adults}"
        )
        return BookingLink(label="Singapore Airlines 官網", url=url, is_direct=True, priority=0)


class BritishAirwaysBuilder(_AirlineBuilder):
    KEYWORDS = ("british airways", "ba ")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.britishairways.com/travel/book/public/en_tw?"
            f"eId=106011&Oc={from_airport}&Dc={to_airport}"
            f"&OS={depart_date}{ret}&AD={adults}&PA={trip}"
        )
        return BookingLink(label="British Airways 官網", url=url, is_direct=True, priority=0)


class LufthansaBuilder(_AirlineBuilder):
    KEYWORDS = ("lufthansa", "漢莎")

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&triptype=R&returnDate={return_date}" if return_date else ""
        url  = (
            f"https://www.lufthansa.com/tw/en/flight-search?"
            f"tripType={trip}&origin={from_airport}&destination={to_airport}"
            f"&departureDate={depart_date}{ret}&adults={adults}"
        )
        return BookingLink(label="Lufthansa 官網", url=url, is_direct=True, priority=0)


# ── 所有航空公司 builder 的註冊清單 ──────────────────────────────────────────
# 新增航空公司時，在此清單追加即可，其他程式碼不需修改。
_ALL_AIRLINE_BUILDERS: list[type[_AirlineBuilder]] = [
    EvaAirBuilder,
    ChinaAirlinesBuilder,
    StarluxBuilder,
    CathayBuilder,
    ScootBuilder,
    JetstarBuilder,
    PeachBuilder,
    TigerairTWBuilder,
    AirAsiaBuilder,
    JalBuilder,
    AnaBuilder,
    ThaiLionAirBuilder,
    KoreanAirBuilder,
    SingaporeAirlinesBuilder,
    BritishAirwaysBuilder,
    LufthansaBuilder,
]


# ══════════════════════════════════════════════════════════════════════════════
#  代理商連結 Builders
# ══════════════════════════════════════════════════════════════════════════════

class _AgentBuilder:
    """代理商 builder 基底 class。"""
    AGENT_ID:   str = ""
    AGENT_NAME: str = ""

    @classmethod
    def build(
        cls,
        from_airport: str,
        to_airport: str,
        depart_date: str,
        return_date: str = "",
        adults: int = 1,
    ) -> BookingLink:
        raise NotImplementedError


class GoogleFlightsBuilder(_AgentBuilder):
    AGENT_ID   = "google_flights"
    AGENT_NAME = "Google Flights"

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        # Google Flights deep link via query
        trip_label = "round-trip" if return_date else "one-way"
        q = f"Flights from {from_airport} to {to_airport}"
        params = {
            "q": q,
            "hl": "zh-TW",
            "curr": "TWD",
        }
        url = f"https://www.google.com/travel/flights?{urlencode(params)}"
        return BookingLink(label=cls.AGENT_NAME, url=url, is_direct=False, priority=1)


class SkyscannerBuilder(_AgentBuilder):
    AGENT_ID   = "skyscanner"
    AGENT_NAME = "Skyscanner"

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        # Skyscanner deep link format
        dep_fmt = depart_date.replace("-", "")   # YYYYMMDD
        if return_date:
            ret_fmt = return_date.replace("-", "")
            path = f"transport/flights/{from_airport}/{to_airport}/{dep_fmt}/{ret_fmt}"
        else:
            path = f"transport/flights/{from_airport}/{to_airport}/{dep_fmt}"
        url = (
            f"https://www.skyscanner.com.tw/{path}?"
            f"adults={adults}&children=0&infants=0&cabinclass=economy"
        )
        return BookingLink(label=cls.AGENT_NAME, url=url, is_direct=False, priority=2)


class TripComBuilder(_AgentBuilder):
    AGENT_ID   = "trip_com"
    AGENT_NAME = "Trip.com"

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "2" if return_date else "1"  # 1=one-way, 2=round-trip
        dep_enc = depart_date
        ret_part = f"&ReturnDate={return_date}" if return_date else ""
        url = (
            f"https://tw.trip.com/flights/flightlist?"
            f"dcity={from_airport}&acity={to_airport}"
            f"&ddate={dep_enc}{ret_part}"
            f"&triptype={trip}&class=y&adult={adults}"
        )
        return BookingLink(label=cls.AGENT_NAME, url=url, is_direct=False, priority=3)


class KayakBuilder(_AgentBuilder):
    """
    TODO: 評估 Kayak 手續費政策及服務品質後決定是否啟用。
    目前在 AGENT_PRIORITY 清單中已注解停用。
    """
    AGENT_ID   = "kayak"
    AGENT_NAME = "Kayak"

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        dep_fmt = depart_date  # YYYY-MM-DD
        if return_date:
            url = (
                f"https://www.kayak.com.tw/flights/"
                f"{from_airport}-{to_airport}/{dep_fmt}/{return_date}"
                f"/{adults}adults?cabin=economy"
            )
        else:
            url = (
                f"https://www.kayak.com.tw/flights/"
                f"{from_airport}-{to_airport}/{dep_fmt}"
                f"/{adults}adults?cabin=economy"
            )
        return BookingLink(label=cls.AGENT_NAME, url=url, is_direct=False, priority=4)


class KiwiBuilder(_AgentBuilder):
    """
    TODO: 評估 Kiwi.com 退票政策（已知有自訂退票規則，與航空公司政策不同）。
    目前在 AGENT_PRIORITY 清單中已注解停用。
    """
    AGENT_ID   = "kiwi"
    AGENT_NAME = "Kiwi.com"

    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        dep_from = f"{depart_date}T00:00:00"
        dep_to   = f"{depart_date}T23:59:59"
        params = {
            "from":     from_airport,
            "to":       to_airport,
            "depart":   dep_from,
            "return":   return_date if return_date else "",
            "adults":   adults,
            "currency": "TWD",
        }
        url = f"https://www.kiwi.com/en/search/results/{from_airport}/{to_airport}/{depart_date}"
        return BookingLink(label=cls.AGENT_NAME, url=url, is_direct=False, priority=5)


# ── 代理商 builder 的 ID → class 對照字典 ─────────────────────────────────────
_AGENT_BUILDER_MAP: dict[str, type[_AgentBuilder]] = {
    "google_flights": GoogleFlightsBuilder,
    "skyscanner":     SkyscannerBuilder,
    "trip_com":       TripComBuilder,
    "kayak":          KayakBuilder,
    "kiwi":           KiwiBuilder,
}


# ══════════════════════════════════════════════════════════════════════════════
#  主要工廠
# ══════════════════════════════════════════════════════════════════════════════

class BookingLinkFactory:
    """
    給定一筆 FlightRecord，產生一組 BookingLinkSet。

    使用方式：
        links = BookingLinkFactory.build(record)
        if links.has_links():
            for link in links.all_links:
                print(link)
    """

    @classmethod
    def build(
        cls,
        from_airport: str,
        to_airport: str,
        depart_date: str,
        return_date: str,
        airline_name: str,
        airline_type: str,
        airline_price: float,
        currency: str,
        adults: int = 1,
    ) -> BookingLinkSet:
        """
        建立 BookingLinkSet。

        airline_price: 抓到的票價（用於比較是否顯示代理商）
        """
        link_set = BookingLinkSet()

        # ── 1. 找航空公司官網連結 ──────────────────────────────────────────
        airline_links: list[BookingLink] = []
        for builder_cls in _ALL_AIRLINE_BUILDERS:
            # 跨航空公司組合名 (e.g. "Scoot / Jetstar") 各自試比對
            for name_part in airline_name.split("/"):
                if builder_cls.matches(name_part.strip()):
                    link = builder_cls.build(
                        from_airport=from_airport,
                        to_airport=to_airport,
                        depart_date=depart_date,
                        return_date=return_date,
                        adults=adults,
                    )
                    if link and link.url not in {l.url for l in airline_links}:
                        airline_links.append(link)

        link_set.airline_links = airline_links

        # ── 2. 建立代理商連結 ──────────────────────────────────────────────
        agent_links: list[BookingLink] = []
        for priority_idx, (agent_id, _agent_name) in enumerate(AGENT_PRIORITY):
            builder_cls = _AGENT_BUILDER_MAP.get(agent_id)
            if not builder_cls:
                continue
            link = builder_cls.build(
                from_airport=from_airport,
                to_airport=to_airport,
                depart_date=depart_date,
                return_date=return_date,
                adults=adults,
            )
            if link:
                link.priority = priority_idx
                agent_links.append(link)
            if len(agent_links) >= MAX_AGENT_LINKS:
                break

        link_set.agent_links = agent_links

        # ── 3. 決定是否顯示代理商 ─────────────────────────────────────────
        # 原則：官網連結存在時，比較價格差異；無官網連結時一律顯示代理商
        if not airline_links:
            link_set.show_agents = True   # 無官網連結，直接顯示代理商
        else:
            # 若沒有價格資訊無從比較，保守起見不顯示代理商（以免誤導）
            # 使用者若想要代理商選項可自行前往 Google Flights
            link_set.show_agents = False
            # Note: 實際票價比較需要代理商即時報價，此處使用 Google Flights
            # 作為永遠補充，因為 Google Flights 本身不賺差價
            google_link = next(
                (l for l in agent_links if "google" in l.label.lower()), None
            )
            if google_link:
                # Google Flights 無手續費，永遠作為參考連結
                link_set.show_agents = True
                link_set.agent_links = [google_link]  # 只給 Google Flights

        return link_set

    @classmethod
    def from_record(cls, record, adults: int = 1) -> BookingLinkSet:
        """從 FlightRecord 物件直接建立 BookingLinkSet。"""
        return cls.build(
            from_airport=record.departure_airport,
            to_airport=record.arrival_airport,
            depart_date=record.departure_date,
            return_date=record.return_date or "",
            airline_name=record.airline or "",
            airline_type=record.airline_type or "",
            airline_price=record.price,
            currency=record.currency,
            adults=adults,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  格式化工具（供 reporter.py 使用）
# ══════════════════════════════════════════════════════════════════════════════

def format_links_rich(link_set: BookingLinkSet) -> str:
    """
    產生 Rich markup 格式的連結字串，供 Rich Table 顯示。
    每個連結各佔一行。
    """
    if not link_set.has_links():
        return "[dim]—[/dim]"

    lines = []
    for link in link_set.all_links:
        if link.is_direct:
            lines.append(f"[bold green]✈[/bold green] [link={link.url}]{link.label}[/link]")
        else:
            lines.append(f"[dim]🔗[/dim] [link={link.url}]{link.label}[/link]")
    return "\n".join(lines)


def format_links_plain(link_set: BookingLinkSet) -> list[str]:
    """
    產生純文字連結清單。
    """
    if not link_set.has_links():
        return []
    return [f"{'✈ ' if l.is_direct else '🔗 '}{l.label}: {l.url}"
            for l in link_set.all_links]
