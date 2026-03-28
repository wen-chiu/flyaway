"""
booking_links.py — 訂票連結產生器
=====================================
設計原則
--------
1. Google Flights 搜尋連結（來自 fast-flights TFS URL）— 最精確，永遠優先顯示
2. 航空公司官網直達連結 — 由航線參數組合，作為備用管道
3. 其他代理商 — 暫停啟用，待評估後逐步開放

連結來源說明
------------
Google Flights 連結有兩種品質：
  - TFS URL（精確）：從 fast-flights 搜尋時捕捉的 tfs= 參數，
    直接對應到該航線、日期的搜尋結果頁
  - Generic URL（備用）：當 TFS 捕捉失敗時，用 from/to/date 參數構成
    的 Google Flights 搜尋 URL

航空公司官網連結
---------------
使用各航空公司的查詢參數 URL。由於各家公司可能更新 URL 結構，
建議定期驗證有效性。新增航空公司只需在 _ALL_AIRLINE_BUILDERS 追加 class。

架構
----
  BookingLink        — 單一連結（label + url + is_google_flights + is_direct）
  BookingLinkSet     — 一筆航班的所有連結組合
  _AirlineBuilder    — 各航空公司 URL builder 基底 class
  BookingLinkFactory — 主要入口，from_record(FlightRecord) → BookingLinkSet
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlencode


# ══════════════════════════════════════════════════════════════════════════════
#  設定（全部集中於此，修改只需動這裡）
# ══════════════════════════════════════════════════════════════════════════════

# 代理商優先順序
# TODO: 評估各代理商的服務品質、手續費、退改票彈性後調整順序
# 格式：(agent_id, 顯示名稱, 說明)
# 要啟用某代理商：取消 # 號後重啟程式，不需要其他改動
AGENT_PRIORITY: list[tuple[str, str]] = [
    # ("skyscanner",   "Skyscanner"),    # TODO: 評估手續費後開放
    # ("trip_com",     "Trip.com"),      # TODO: 評估服務品質後開放
    # ("kayak",        "Kayak"),         # TODO: 待評估
    # ("kiwi",         "Kiwi.com"),      # TODO: 退票政策待確認
]

MAX_AIRLINE_LINKS: int = 2   # 最多顯示幾個航空公司官網連結
MAX_AGENT_LINKS:  int = 2    # 最多顯示幾個代理商連結


# ══════════════════════════════════════════════════════════════════════════════
#  資料模型
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BookingLink:
    label:             str
    url:               str
    is_google_flights: bool = False   # True = Google Flights（無論 TFS 或 generic）
    is_direct:         bool = False   # True = 航空公司官網
    priority:          int  = 99

    def __str__(self) -> str:
        if self.is_google_flights:
            return f"🔍 {self.label}: {self.url}"
        if self.is_direct:
            return f"✈  {self.label}: {self.url}"
        return f"🔗 {self.label}: {self.url}"


@dataclass
class BookingLinkSet:
    google_link:   Optional[BookingLink]      = None   # Google Flights（TFS 或 generic）
    airline_links: List[BookingLink]          = field(default_factory=list)
    agent_links:   List[BookingLink]          = field(default_factory=list)

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
        all_ = self.all_links
        return all_[0] if all_ else None

    def has_links(self) -> bool:
        return bool(self.google_link or self.airline_links or self.agent_links)


# ══════════════════════════════════════════════════════════════════════════════
#  Google Flights URL 建構
# ══════════════════════════════════════════════════════════════════════════════

def _build_google_flights_link(
    from_airport: str,
    to_airport:   str,
    depart_date:  str,
    return_date:  str = "",
    tfs_url:      str = "",
) -> BookingLink:
    """
    建立 Google Flights 連結。
    若有 TFS URL（從 fast-flights 搜尋時捕捉），使用精確 TFS 連結。
    否則構建基本搜尋 URL。
    """
    if tfs_url and "tfs=" in tfs_url:
        # 精確 TFS URL：直接對應到該航線的搜尋結果
        url   = tfs_url
        label = "Google Flights 搜尋結果"
    else:
        # Fallback：一般搜尋 URL（含出發地、目的地）
        q = f"Flights from {from_airport} to {to_airport}"
        params: dict = {"q": q, "hl": "zh-TW"}
        url   = f"https://www.google.com/travel/flights?{urlencode(params)}"
        label = "Google Flights 搜尋"

    return BookingLink(
        label=label,
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
        n = airline_name.lower()
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
    KEYWORDS = ("eva air", "eva", "evaair")
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
    KEYWORDS = ("china airlines", "china air")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        params = {
            "tripType": "RT" if return_date else "OW",
            "from": from_airport, "to": to_airport,
            "departDate": depart_date.replace("-", "/"),
            "adult": adults,
        }
        if return_date:
            params["returnDate"] = return_date.replace("-", "/")
        return BookingLink(
            label="中華航空 China Airlines",
            url=f"https://www.china-airlines.com/tw/zh/booking/book-tickets/search?{urlencode(params)}",
            is_direct=True, priority=10,
        )


class StarluxBuilder(_AirlineBuilder):
    KEYWORDS = ("starlux", "星宇")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="星宇航空 STARLUX",
            url=(f"https://www.starlux-airlines.com/zh-TW/booking/flights"
                 f"?tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&outbound={depart_date}{ret}&adt={adults}"),
            is_direct=True, priority=10,
        )


# ── 亞太傳統航空 ──────────────────────────────────────────────────────────────

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


class KoreanAirBuilder(_AirlineBuilder):
    KEYWORDS = ("korean air", "대한항공")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&returnDate={return_date.replace('-','')}" if return_date else ""
        return BookingLink(
            label="大韓航空 Korean Air",
            url=(f"https://www.koreanair.com/booking/flight-search?"
                 f"tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date.replace('-','')}{ret}&adultCount={adults}"),
            is_direct=True, priority=10,
        )


class SingaporeAirlinesBuilder(_AirlineBuilder):
    KEYWORDS = ("singapore airlines", "sq ", "新加坡航空")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="新加坡航空 SQ",
            url=(f"https://www.singaporeair.com/en_UK/us/plan-travel/book-a-flight/"
                 f"?tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


class BritishAirwaysBuilder(_AirlineBuilder):
    KEYWORDS = ("british airways",)
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


class LufthansaBuilder(_AirlineBuilder):
    KEYWORDS = ("lufthansa", "漢莎")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "R" if return_date else "O"
        ret  = f"&triptype=R&returnDate={return_date}" if return_date else ""
        return BookingLink(
            label="漢莎航空 Lufthansa",
            url=(f"https://www.lufthansa.com/tw/en/flight-search?"
                 f"tripType={trip}&origin={from_airport}&destination={to_airport}"
                 f"&departureDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=10,
        )


# ── 亞太廉航 ─────────────────────────────────────────────────────────────────

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


class PeachBuilder(_AirlineBuilder):
    KEYWORDS = ("peach", "樂桃")
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


class TigerairTWBuilder(_AirlineBuilder):
    KEYWORDS = ("tigerair taiwan", "tiger air", "台灣虎航")
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        trip = "RT" if return_date else "OW"
        ret  = f"&ReturnDate={return_date}" if return_date else ""
        return BookingLink(
            label="台灣虎航 Tigerair",
            url=(f"https://www.tigerairtw.com/zh-tw/booking/search?"
                 f"trip={trip}&from={from_airport}&to={to_airport}"
                 f"&DepartureDate={depart_date}{ret}&adults={adults}"),
            is_direct=True, priority=20,
        )


class AirAsiaBuilder(_AirlineBuilder):
    KEYWORDS = ("airasia", "air asia", "亞洲航空")
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


# ── 所有航空公司 builder 清單（新增航空公司：在此追加即可）───────────────────
_ALL_AIRLINE_BUILDERS: list[type[_AirlineBuilder]] = [
    # 台灣本土
    EvaAirBuilder,
    ChinaAirlinesBuilder,
    StarluxBuilder,
    # 亞太傳統
    CathayBuilder,
    JalBuilder,
    AnaBuilder,
    KoreanAirBuilder,
    SingaporeAirlinesBuilder,
    BritishAirwaysBuilder,
    LufthansaBuilder,
    # 廉航
    ScootBuilder,
    JetstarBuilder,
    PeachBuilder,
    TigerairTWBuilder,
    AirAsiaBuilder,
    ThaiLionAirBuilder,
]


# ══════════════════════════════════════════════════════════════════════════════
#  代理商 Builders（目前全部停用，待評估後在 AGENT_PRIORITY 開放）
# ══════════════════════════════════════════════════════════════════════════════

class _AgentBuilder:
    AGENT_ID:   str = ""
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1) -> BookingLink:
        raise NotImplementedError


class SkyscannerBuilder(_AgentBuilder):
    AGENT_ID = "skyscanner"
    @classmethod
    def build(cls, from_airport, to_airport, depart_date, return_date="", adults=1):
        dep = depart_date.replace("-", "")
        if return_date:
            path = f"{from_airport}-{to_airport}/{dep}/{return_date.replace('-','')}"
        else:
            path = f"{from_airport}-{to_airport}/{dep}"
        return BookingLink(
            label="Skyscanner",
            url=f"https://www.skyscanner.com.tw/transport/flights/{path}?adults={adults}&cabinclass=economy",
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
    """TODO: 評估 Kayak 手續費後決定是否啟用。"""
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
    """TODO: 退票政策待確認後決定是否啟用。"""
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
      1. Google Flights（TFS 精確連結 或 generic 搜尋）
      2. 航空公司官網（由航線參數組合）
      3. 代理商（由 AGENT_PRIORITY 控制，預設全停用）

    使用範例：
      links = BookingLinkFactory.from_record(record)
      for link in links.all_links:
          print(link)
    """

    @classmethod
    def from_record(cls, record, adults: int = 1) -> BookingLinkSet:
        """從 FlightRecord 建立 BookingLinkSet。"""
        link_set = BookingLinkSet()

        # ── 1. Google Flights 連結（永遠建立）─────────────────────────────
        link_set.google_link = _build_google_flights_link(
            from_airport=record.departure_airport,
            to_airport=record.arrival_airport,
            depart_date=record.departure_date,
            return_date=record.return_date or "",
            tfs_url=record.google_search_url or "",
        )

        # ── 2. 航空公司官網連結 ────────────────────────────────────────────
        airline_links: list[BookingLink] = []
        # Handle combined names like "Scoot / Jetstar"
        for name_part in record.airline.split("/"):
            name_part = name_part.strip()
            if not name_part:
                continue
            for builder_cls in _ALL_AIRLINE_BUILDERS:
                if builder_cls.matches(name_part):
                    link = builder_cls.build(
                        from_airport=record.departure_airport,
                        to_airport=record.arrival_airport,
                        depart_date=record.departure_date,
                        return_date=record.return_date or "",
                        adults=adults,
                    )
                    if link:
                        # Avoid duplicate URLs
                        if link.url not in {l.url for l in airline_links}:
                            airline_links.append(link)
                    break  # Only match first airline builder per name part
            if len(airline_links) >= MAX_AIRLINE_LINKS:
                break
        link_set.airline_links = airline_links

        # ── 3. 代理商連結（由 AGENT_PRIORITY 控制）────────────────────────
        agent_links: list[BookingLink] = []
        for priority_idx, (agent_id, _) in enumerate(AGENT_PRIORITY):
            builder_cls = _AGENT_BUILDER_MAP.get(agent_id)
            if not builder_cls:
                continue
            link = builder_cls.build(
                from_airport=record.departure_airport,
                to_airport=record.arrival_airport,
                depart_date=record.departure_date,
                return_date=record.return_date or "",
                adults=adults,
            )
            if link:
                link.priority = 30 + priority_idx
                agent_links.append(link)
            if len(agent_links) >= MAX_AGENT_LINKS:
                break
        link_set.agent_links = agent_links

        return link_set


# ══════════════════════════════════════════════════════════════════════════════
#  格式化工具（供 reporter.py 使用）
# ══════════════════════════════════════════════════════════════════════════════

def format_links_rich(link_set: BookingLinkSet) -> str:
    """回傳 Rich markup 格式字串，供 Rich Table 顯示（可點擊連結）。"""
    if not link_set.has_links():
        return "[dim]—[/dim]"
    lines = []
    for link in link_set.all_links:
        if link.is_google_flights:
            lines.append(f"[bold cyan]🔍[/bold cyan] [link={link.url}]{link.label}[/link]")
        elif link.is_direct:
            lines.append(f"[green]✈[/green]  [link={link.url}]{link.label}[/link]")
        else:
            lines.append(f"[dim]🔗[/dim] [link={link.url}]{link.label}[/link]")
    return "\n".join(lines)


def format_links_plain(link_set: BookingLinkSet) -> list[str]:
    """回傳純文字連結清單。"""
    if not link_set.has_links():
        return []
    prefix_map = {
        "google": "🔍",
        "direct": "✈ ",
        "agent":  "🔗",
    }
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