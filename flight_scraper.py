"""
flight_scraper.py — Google Flights 機票抓取引擎
=================================================
策略：
  1. fast-flights（直打 Google Flights protobuf API，優先）
  2. Playwright（備用瀏覽器模擬）
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple
import random

from config import (
    ADULTS, CHILDREN, INFANTS,
    MAX_DURATION_HOURS, MAX_STOPS,
    REQUEST_DELAY_SEC, MAX_RETRIES,
    PLAYWRIGHT_HEADLESS, PLAYWRIGHT_TIMEOUT,
    DEFAULT_DEPARTURE,
)
from database import FlightRecord

logger = logging.getLogger(__name__)

try:
    from fast_flights import (
        FlightData, Passengers, Result,
        create_filter, get_flights,
    )
    _HAS_FAST_FLIGHTS = True
    logger.info("fast-flights 已載入 ✓")
except ImportError:
    _HAS_FAST_FLIGHTS = False
    logger.warning("fast-flights 未安裝，將使用 Playwright 備用方案")


class FlightScraper:
    def __init__(
        self,
        max_stops: int = MAX_STOPS,
        max_duration_hours: int = MAX_DURATION_HOURS,
    ):
        self.max_stops = max_stops
        self.max_duration_hours = max_duration_hours
        self._backend = "fast_flights" if _HAS_FAST_FLIGHTS else "playwright"
        logger.info(f"FlightScraper 後端: {self._backend}")

    # ── 單程搜尋 ─────────────────────────────────────────────────────────────

    def search(
        self,
        from_airport: str,
        to_airport: str,
        departure_date: date,
        adults: int = ADULTS,
        max_stops_override: Optional[int] = None,
    ) -> List[FlightRecord]:
        from config import get_max_stops_for
        effective_stops = (
            max_stops_override if max_stops_override is not None
            else get_max_stops_for(to_airport, self.max_stops)
        )
        date_str = departure_date.strftime("%Y-%m-%d")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if self._backend == "fast_flights":
                    records = self._search_fast_flights(
                        from_airport, to_airport, date_str, adults,
                        max_stops=effective_stops,
                    )
                else:
                    records = asyncio.run(
                        self._search_playwright(from_airport, to_airport, date_str)
                    )
                filtered = [
                    r for r in records
                    if (r.stops == -1 or r.stops <= effective_stops)
                    and (r.duration_minutes == 0 or
                         r.duration_minutes <= self.max_duration_hours * 60)
                ]
                return filtered
            except Exception as e:
                logger.warning(f"  搜尋嘗試 {attempt}/{MAX_RETRIES} 失敗: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(REQUEST_DELAY_SEC * attempt + random.uniform(0.5, 1.5))
        return []

    # ── 來回搜尋（主要方法）────────────────────────────────────────────────────

    def search_roundtrip(
        self,
        from_airport: str,
        to_airport: str,
        outbound_date: date,
        return_date: date,
        adults: int = ADULTS,
        max_stops_override: Optional[int] = None,
    ) -> List[FlightRecord]:
        from config import get_max_stops_for
        effective_stops = (
            max_stops_override if max_stops_override is not None
            else get_max_stops_for(to_airport, self.max_stops)
        )
        out_str = outbound_date.strftime("%Y-%m-%d")
        ret_str = return_date.strftime("%Y-%m-%d")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if self._backend == "fast_flights":
                    records = self._search_roundtrip_fast_flights(
                        from_airport, to_airport, out_str, ret_str,
                        adults, max_stops=effective_stops,
                    )
                else:
                    records = self._playwright_roundtrip_fallback(
                        from_airport, to_airport, out_str, ret_str,
                        adults, effective_stops,
                    )
                filtered = [
                    r for r in records
                    if (r.stops == -1 or r.stops <= effective_stops)
                    and (r.duration_minutes == 0 or
                         r.duration_minutes <= self.max_duration_hours * 60)
                ]
                return self._dedup(filtered)
            except Exception as e:
                logger.warning(f"  來回搜尋嘗試 {attempt}/{MAX_RETRIES} 失敗: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(REQUEST_DELAY_SEC * attempt + random.uniform(0.5, 1.5))
        return []

    def search_roundtrip_many(
        self,
        from_airport: str,
        destinations: List[str],
        outbound_dates: List[date],
        return_dates: List[date],
        adults: int = ADULTS,
    ) -> List[FlightRecord]:
        if len(return_dates) == 1:
            return_dates = return_dates * len(outbound_dates)

        all_records: List[FlightRecord] = []
        combos = [
            (dest, out, ret)
            for dest in destinations
            for out, ret in zip(outbound_dates, return_dates)
        ]
        total = len(combos)

        for idx, (dest, out_d, ret_d) in enumerate(combos, 1):
            from config import get_max_stops_for, get_region
            eff_stops  = get_max_stops_for(dest, self.max_stops)
            region_tag = f"[{get_region(dest) or '?'}]"
            stops_tag  = "直達" if eff_stops == 0 else f"≤{eff_stops}轉"
            logger.info(
                f"[{idx}/{total}] 來回 {from_airport}⇄{dest} "
                f"去:{out_d} 回:{ret_d} {region_tag} {stops_tag}"
            )
            records = self.search_roundtrip(from_airport, dest, out_d, ret_d, adults)
            all_records.extend(records)
            time.sleep(REQUEST_DELAY_SEC + random.uniform(0, 0.8))

        return all_records

    def search_many(
        self,
        from_airport: str,
        destinations: List[str],
        departure_dates: List[date],
        adults: int = ADULTS,
    ) -> List[FlightRecord]:
        all_records: List[FlightRecord] = []
        total = len(destinations) * len(departure_dates)
        done  = 0
        for dest in destinations:
            for dep_date in departure_dates:
                done += 1
                from config import get_max_stops_for, get_region
                eff_stops  = get_max_stops_for(dest, self.max_stops)
                region_tag = f"[{get_region(dest) or '?'}]"
                stops_tag  = "直達" if eff_stops == 0 else f"≤{eff_stops}轉"
                logger.info(
                    f"[{done}/{total}] {from_airport} → {dest} "
                    f"{dep_date.strftime('%Y-%m-%d')} {region_tag} {stops_tag}"
                )
                records = self.search(from_airport, dest, dep_date, adults)
                all_records.extend(records)
                time.sleep(REQUEST_DELAY_SEC + random.uniform(0, 0.8))
        return self._dedup(all_records)

    @staticmethod
    def _dedup(records: List[FlightRecord]) -> List[FlightRecord]:
        seen: set = set()
        result: List[FlightRecord] = []
        for r in records:
            key = (
                r.departure_airport, r.arrival_airport,
                r.departure_date, r.return_date,
                r.airline, round(r.price, 0),
                r.departure_time,
            )
            if key not in seen:
                seen.add(key)
                result.append(r)
        return result

    # ── fast-flights 後端 ─────────────────────────────────────────────────────

    def _search_fast_flights(
        self,
        from_airport: str,
        to_airport: str,
        date_str: str,
        adults: int = 1,
        max_stops: Optional[int] = None,
    ) -> List[FlightRecord]:
        if not _HAS_FAST_FLIGHTS:
            raise RuntimeError("fast-flights 未安裝")

        pax = Passengers(adults=adults, children=CHILDREN, infants_in_seat=INFANTS)
        fd  = [FlightData(date=date_str, from_airport=from_airport, to_airport=to_airport)]

        effective_max = max_stops if max_stops is not None else self.max_stops
        api_max_stops = effective_max if effective_max < 2 else None

        # ── 擷取 Google Flights TFS URL ──────────────────────────────────────
        google_search_url = _build_google_flights_url(from_airport, to_airport, date_str)
        try:
            tfs_obj = create_filter(
                flight_data=fd, trip="one-way", seat="economy",
                passengers=pax, max_stops=api_max_stops,
            )
            tfs_str = _extract_tfs_string(tfs_obj)
            if tfs_str:
                google_search_url = (
                    f"https://www.google.com/travel/flights"
                    f"?tfs={tfs_str}&hl=zh-TW&tfu=EgQIABABIgA"
                )
        except Exception as e:
            logger.debug(f"  TFS URL 擷取失敗: {e}")

        # ── 嘗試不同 fetch_mode ───────────────────────────────────────────────
        result = None
        for mode in ("fallback", "force-fallback", "common"):
            try:
                candidate = get_flights(
                    flight_data=fd, trip="one-way", seat="economy",
                    passengers=pax, max_stops=api_max_stops, fetch_mode=mode,
                )
                flights_check = []
                for attr in ("flights", "best_flights", "other_flights"):
                    b = getattr(candidate, attr, None)
                    if b:
                        flights_check.extend(b)
                if not flights_check:
                    continue
                has_times = any(
                    getattr(f, "departure", "") or getattr(f, "arrival", "")
                    for f in flights_check[:5]
                )
                logger.debug(
                    f"  fetch_mode={mode} → {len(flights_check)} 筆, "
                    f"times={'✓' if has_times else '✗'}"
                )
                if has_times or result is None:
                    result = candidate
                if has_times:
                    break
            except Exception as e:
                logger.debug(f"  fetch_mode={mode} 失敗: {e}")

        if not result:
            return []

        fetched_at = datetime.now().isoformat()
        records: List[FlightRecord] = []
        flights_raw = []
        for attr in ("flights", "best_flights", "other_flights"):
            bucket = getattr(result, attr, None)
            if bucket:
                flights_raw.extend(bucket)
        if not flights_raw:
            return records

        currency = (
            getattr(result, "currency", None)
            or getattr(result, "price_currency", None)
            or ""
        )

        from airline_classifier import classify_airline
        for f in flights_raw:
            try:
                rec = _parse_flight_obj(
                    f, from_airport, to_airport, date_str,
                    fetched_at, currency, classify_airline,
                    google_search_url=google_search_url,
                )
                if rec:
                    records.append(rec)
            except Exception as e:
                logger.debug(f"  解析 flight 物件時出錯: {e}")
        return records

    def _search_roundtrip_fast_flights(
        self,
        from_airport: str,
        to_airport: str,
        outbound_date: str,
        return_date: str,
        adults: int = 1,
        max_stops: Optional[int] = None,
    ) -> List[FlightRecord]:
        """
        Google Flights round-trip API 目前無法使用（回傳 loading page）。
        策略：分別搜尋去程和回程單程，再配對組合成來回票。
        """
        if not _HAS_FAST_FLIGHTS:
            raise RuntimeError("fast-flights 未安裝")

        from airline_classifier import classify_airline

        out_recs = self._search_fast_flights(
            from_airport, to_airport, outbound_date, adults, max_stops
        )
        ret_recs = self._search_fast_flights(
            to_airport, from_airport, return_date, adults, max_stops
        )

        if not out_recs and not ret_recs:
            return []

        fetched_at = datetime.now().isoformat()
        MAX_PAIR = 15

        def has_time(r: FlightRecord) -> bool:
            return bool(r.departure_time or r.arrival_time)

        # 有時間資料的優先排在前面
        out_top = sorted(out_recs, key=lambda r: (0 if has_time(r) else 1, r.price))[:MAX_PAIR]
        ret_top = sorted(ret_recs, key=lambda r: (0 if has_time(r) else 1, r.price))[:MAX_PAIR]

        if not ret_top:
            for r in out_top: r.is_roundtrip = False
            return out_top
        if not out_top:
            for r in ret_top: r.is_roundtrip = False
            return ret_top

        def merge_airline(a1: str, a2: str) -> str:
            a1 = (a1 or "").strip(); a2 = (a2 or "").strip()
            if a1 == a2 and a1: return a1
            if not a1: return a2
            if not a2: return a1
            return f"{a1} / {a2}"

        def merge_airline_type(t1: str, t2: str) -> str:
            if "LCC" in (t1, t2): return "LCC"
            if "traditional" in (t1, t2): return "traditional"
            return "unknown"

        full_pairs:    List[FlightRecord] = []
        partial_pairs: List[FlightRecord] = []

        for out in out_top:
            for ret in ret_top:
                # BUG FIX: _combine_prices no longer depends on TWD_FALLBACK_RATES
                combined_price, combined_currency = _combine_prices(
                    out.price, out.currency, ret.price, ret.currency
                )
                rec = FlightRecord(
                    departure_airport=from_airport.upper(),
                    arrival_airport=to_airport.upper(),
                    departure_date=outbound_date,
                    price=combined_price,
                    currency=combined_currency,
                    duration_minutes=out.duration_minutes,
                    stops=out.stops,
                    airline=merge_airline(out.airline, ret.airline),
                    flight_numbers=out.flight_numbers,
                    departure_time=out.departure_time,
                    arrival_time=out.arrival_time,
                    fetched_at=fetched_at,
                    source="fast_flights_paired",
                    is_roundtrip=True,
                    return_date=return_date,
                    return_duration=ret.duration_minutes,
                    return_dep_time=ret.departure_time,
                    return_arr_time=ret.arrival_time,
                    airline_type=merge_airline_type(out.airline_type, ret.airline_type),
                    # Use outbound's captured Google Flights URL
                    google_search_url=out.google_search_url or ret.google_search_url,
                )
                if has_time(out) and has_time(ret):
                    full_pairs.append(rec)
                elif has_time(out) or has_time(ret):
                    partial_pairs.append(rec)
                # Skip both-empty pairs — they add no value to display

        # BUG FIX: merge both buckets instead of choosing one
        # Previously `full_pairs if full_pairs else partial_pairs` caused
        # traditional airlines to vanish whenever any LCC formed a full pair.
        return full_pairs + partial_pairs

    def _playwright_roundtrip_fallback(
        self,
        from_airport: str,
        to_airport: str,
        out_str: str,
        ret_str: str,
        adults: int,
        effective_stops: int,
    ) -> List[FlightRecord]:
        """Playwright 備用：搜尋兩趟單程後配對。"""
        from airline_classifier import classify_airline
        out_recs = asyncio.run(self._search_playwright(from_airport, to_airport, out_str))
        ret_recs = asyncio.run(self._search_playwright(to_airport, from_airport, ret_str))
        if not out_recs:
            return []
        if not ret_recs:
            for r in out_recs: r.is_roundtrip = False
            return out_recs
        MAX_PAIR = 15
        out_top = sorted(out_recs, key=lambda r: r.price)[:MAX_PAIR]
        ret_top = sorted(ret_recs, key=lambda r: r.price)[:MAX_PAIR]
        fetched_at = datetime.now().isoformat()
        records: List[FlightRecord] = []
        for out in out_top:
            for ret in ret_top:
                combined_price, combined_currency = _combine_prices(
                    out.price, out.currency, ret.price, ret.currency
                )
                records.append(FlightRecord(
                    departure_airport=from_airport.upper(),
                    arrival_airport=to_airport.upper(),
                    departure_date=out_str,
                    price=combined_price,
                    currency=combined_currency,
                    duration_minutes=out.duration_minutes,
                    stops=out.stops,
                    airline=f"{out.airline or '?'} / {ret.airline or '?'}",
                    flight_numbers="",
                    departure_time=out.departure_time,
                    arrival_time=out.arrival_time,
                    fetched_at=fetched_at,
                    source="playwright_paired",
                    is_roundtrip=True,
                    return_date=ret_str,
                    return_duration=ret.duration_minutes,
                    return_dep_time=ret.departure_time,
                    return_arr_time=ret.arrival_time,
                    airline_type=classify_airline(out.airline),
                ))
        return records

    # ── Playwright 後端 ────────────────────────────────────────────────────────

    async def _search_playwright(
        self,
        from_airport: str,
        to_airport: str,
        date_str: str,
    ) -> List[FlightRecord]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError("Playwright 未安裝。請執行: playwright install chromium")

        url       = _build_google_flights_url(from_airport, to_airport, date_str)
        records   = []
        fetched_at = datetime.now().isoformat()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="zh-TW", timezone_id="Asia/Taipei",
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=PLAYWRIGHT_TIMEOUT)
                await page.wait_for_timeout(3000)
                try:
                    show_more = page.locator('[aria-label*="更多航班"],[aria-label*="more flights"]')
                    if await show_more.count() > 0:
                        await show_more.first.click()
                        await page.wait_for_timeout(2000)
                except Exception:
                    pass
                flight_items = await page.locator('[data-testid="flight-card"],.pIav2d,li.Rk10dc').all()
                if not flight_items:
                    flight_items = await page.locator('li[class*="flight"]').all()
                for item in flight_items[:30]:
                    try:
                        rec = await _parse_playwright_item(
                            item, from_airport, to_airport, date_str, fetched_at
                        )
                        if rec:
                            records.append(rec)
                    except Exception:
                        continue
            finally:
                await browser.close()
        return records


# ══════════════════════════════════════════════════════════════════════════════
#  Playwright 解析輔助
# ══════════════════════════════════════════════════════════════════════════════

async def _parse_playwright_item(
    item, from_airport: str, to_airport: str,
    date_str: str, fetched_at: str
) -> Optional[FlightRecord]:
    text  = await item.inner_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    price = 0.0
    for line in lines:
        p = _parse_price(line)
        if p > 0: price = p; break
    if price <= 0:
        return None
    duration = 0
    for line in lines:
        d = _parse_duration(line)
        if d > 0: duration = d; break
    if duration <= 0:
        return None
    stops = 0
    for line in lines:
        if "直飛" in line or "Nonstop" in line.lower():
            stops = 0; break
        m = re.search(r"(\d)\s*次?轉機|(\d)\s*stop", line, re.I)
        if m:
            stops = int(m.group(1) or m.group(2)); break
    airline  = lines[0] if lines else ""
    dep_time = arr_time = ""
    times    = re.compile(r"\d{1,2}:\d{2}").findall(text)
    if len(times) >= 2:
        dep_time, arr_time = times[0], times[1]
    return FlightRecord(
        departure_airport=from_airport.upper(),
        arrival_airport=to_airport.upper(),
        departure_date=date_str,
        price=price, currency="",
        duration_minutes=duration, stops=stops,
        airline=airline, flight_numbers="",
        departure_time=dep_time, arrival_time=arr_time,
        fetched_at=fetched_at, source="playwright",
    )


# ══════════════════════════════════════════════════════════════════════════════
#  工具函式
# ══════════════════════════════════════════════════════════════════════════════

def _extract_tfs_string(tfs_obj) -> str:
    """
    從 fast-flights TFSData 物件提取 tfs= 字串。

    fast-flights 的 TFSData.__str__() 通常直接返回 base64 編碼字串，
    即 Google Flights URL 中 ?tfs= 之後的值。
    """
    if tfs_obj is None:
        return ""

    # Strategy 1: str(tfs_obj) is usually the base64 tfs string directly
    try:
        s = str(tfs_obj)
        # Valid tfs strings: base64url, 20+ chars, mix of upper/lower
        if (len(s) >= 20 and
                any(c.isupper() for c in s) and
                any(c.islower() for c in s) and
                not s.startswith("<") and
                "\n" not in s):
            return s
    except Exception:
        pass

    # Strategy 2: known attribute names
    for attr in ("tfs_str", "tfs", "encoded", "b64", "raw_tfs", "value", "data"):
        val = getattr(tfs_obj, attr, None)
        if val and isinstance(val, str) and len(val) >= 20:
            return val

    # Strategy 3: parse repr for base64url-looking string (40+ chars)
    try:
        from urllib.parse import unquote
        s = repr(tfs_obj)
        import re as _re
        # Look for base64 strings (may be percent-encoded in repr)
        for pattern in [
            r"[A-Za-z0-9+/=]{40,}",      # raw base64
            r"[A-Za-z0-9%+/=_-]{40,}",   # percent-encoded
        ]:
            matches = _re.findall(pattern, s)
            for m in matches:
                decoded = unquote(m)
                if (len(decoded) >= 20 and
                        any(c.isupper() for c in decoded) and
                        any(c.islower() for c in decoded)):
                    return decoded
    except Exception:
        pass

    return ""


def _parse_flight_obj(
    f,
    from_airport: str,
    to_airport: str,
    date_str: str,
    fetched_at: str,
    currency: str,
    classify_fn,
    google_search_url: str = "",
) -> Optional[FlightRecord]:
    price_raw = str(getattr(f, "price", None) or getattr(f, "min_price", None) or "")
    price, flight_currency = _parse_price_and_currency(price_raw)
    if price <= 0:
        return None
    use_currency = flight_currency or currency

    dur_raw  = getattr(f, "duration", None) or getattr(f, "travel_duration", None) or ""
    duration = (
        int(dur_raw) if isinstance(dur_raw, (int, float)) and dur_raw > 0
        else _parse_duration(str(dur_raw))
    )

    stops_raw = getattr(f, "stops", None) or getattr(f, "layover_count", None)
    stops_str = str(stops_raw).strip() if stops_raw is not None else ""
    if stops_str.lower() in ("unknown", "", "none"):
        stops = -1
    else:
        try:
            stops = int(stops_str)
        except ValueError:
            stops = _parse_stops_str(stops_str)

    airline  = str(getattr(f, "name", "") or getattr(f, "airline", "") or "").strip()
    fn_raw   = getattr(f, "flight_number", None) or getattr(f, "flight_numbers", None) or []
    fn_str   = (
        ", ".join(str(x) for x in fn_raw)
        if isinstance(fn_raw, (list, tuple)) else str(fn_raw)
    )
    dep_time = str(getattr(f, "departure", "") or getattr(f, "departure_time", "") or "").strip()
    arr_time = str(getattr(f, "arrival", "")   or getattr(f, "arrival_time", "")   or "").strip()
    ahead    = str(getattr(f, "arrival_time_ahead", "") or "").strip()
    if ahead and arr_time:
        arr_time = f"{arr_time} {ahead}"

    return FlightRecord(
        departure_airport=from_airport.upper(),
        arrival_airport=to_airport.upper(),
        departure_date=date_str,
        price=price,
        currency=use_currency,
        duration_minutes=duration,
        stops=stops,
        airline=airline,
        flight_numbers=fn_str,
        departure_time=dep_time,
        arrival_time=arr_time,
        fetched_at=fetched_at,
        source="fast_flights",
        airline_type=classify_fn(airline),
        google_search_url=google_search_url,
    )


def _combine_prices(price1: float, cur1: str, price2: float, cur2: str) -> tuple:
    """
    合計去程 + 回程票價。
    若幣別相同直接相加；不同則各自換算成 MYR（Google Flights 預設幣別）。
    
    BUG FIX: 不再依賴 config.TWD_FALLBACK_RATES（已移除）。
    使用精簡的內建匯率表，避免 ImportError 導致搜尋結果全空。
    """
    if not cur1: cur1 = cur2 or ""
    if not cur2: cur2 = cur1 or ""
    if cur1 == cur2:
        return round(price1 + price2, 2), cur1 or "MYR"

    # Minimal built-in rates: 1 unit → MYR equivalent
    # Used only when outbound/return legs have different currencies (rare)
    _RATES_TO_MYR = {
        "MYR": 1.0, "TWD": 0.138, "USD": 4.48, "EUR": 4.85,
        "GBP": 5.69, "JPY": 0.030, "KRW": 0.0033, "HKD": 0.574,
        "SGD": 3.34, "THB": 0.129, "AUD": 2.85, "NZD": 2.64,
        "CAD": 3.26, "CNY": 0.622, "INR": 0.054, "AED": 1.22,
        "QAR": 1.23,
    }
    rate1 = _RATES_TO_MYR.get(cur1.upper(), 1.0)
    rate2 = _RATES_TO_MYR.get(cur2.upper(), 1.0)
    total_myr = round(price1 * rate1 + price2 * rate2, 0)
    return total_myr, "MYR"


def _parse_price_and_currency(text: str) -> tuple:
    if not text:
        return 0.0, ""
    text     = text.replace("\xa0", " ").strip()
    currency = ""
    m = re.match(r"^([A-Z]{3})\s*(.+)$", text)
    if m:
        currency = m.group(1)
        text     = m.group(2)
    digits = re.sub(r"[^\d.]", "", text)
    parts  = digits.split(".")
    if len(parts) > 2:
        digits = "".join(parts[:-1]) + "." + parts[-1]
    try:
        price = float(digits) if digits else 0.0
    except ValueError:
        price = 0.0
    return price, currency


def _parse_price(text: str) -> float:
    price, _ = _parse_price_and_currency(text)
    return price


def _parse_duration(text: str) -> int:
    if not text:
        return 0
    text = str(text).strip()
    m = re.search(r"(\d+)\s*(?:hr|h|小時|時)[^\d]*(\d*)\s*(?:min|m|分)?", text, re.I)
    if m:
        return int(m.group(1)) * 60 + (int(m.group(2)) if m.group(2) else 0)
    m = re.search(r"^(\d+)\s*(?:min|分)$", text, re.I)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return 0


def _parse_stops_str(text: str) -> int:
    if not text or text in ("None", "0", ""):
        return 0
    low = text.lower()
    if "nonstop" in low or "direct" in low or "直飛" in low:
        return 0
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else 0


def _build_google_flights_url(from_airport: str, to_airport: str, date_str: str) -> str:
    """Google Flights 通用備用搜尋 URL（當 TFS 捕捉失敗時使用）。"""
    from urllib.parse import urlencode
    params = {"q": f"Flights from {from_airport} to {to_airport}", "hl": "zh-TW"}
    return f"https://www.google.com/travel/flights?{urlencode(params)}"


def build_date_range(center_date: date, flexibility_days: int = 3) -> List[date]:
    return [
        center_date + timedelta(days=delta)
        for delta in range(-flexibility_days, flexibility_days + 1)
    ]