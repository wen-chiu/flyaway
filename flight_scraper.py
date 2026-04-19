"""
flight_scraper.py — Google Flights 機票抓取引擎

=================================================
兩層策略：
1. fast-flights（輕量，直接打 Google Flights protobuf API）
2. Playwright（備用，完整瀏覽器模擬）
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

# ── 試著 import fast-flights ──────────────────────────────────────────────────
try:
    from fast_flights import (
        FlightData, Passengers, Result,
        get_flights,
    )
    _HAS_FAST_FLIGHTS = True
    logger.info("fast-flights 已載入 ✓")
except ImportError:
    _HAS_FAST_FLIGHTS = False
    logger.warning("fast-flights 未安裝，將使用 Playwright 備用方案")

# ══════════════════════════════════════════════════════════════════════════════
# 公用介面
# ══════════════════════════════════════════════════════════════════════════════

class FlightScraper:
    """
    統一的機票搜尋介面。
    自動選擇可用的後端（fast-flights 優先，Playwright 備用）。
    """

    def __init__(
        self,
        max_stops: int = MAX_STOPS,
        max_duration_hours: int = MAX_DURATION_HOURS,
    ):
        self.max_stops = max_stops
        self.max_duration_hours = max_duration_hours
        self._backend = "fast_flights" if _HAS_FAST_FLIGHTS else "playwright"
        logger.info(f"FlightScraper 後端: {self._backend}")

    # ── 主要搜尋方法 ──────────────────────────────────────────────────────────

    def search(
        self,
        from_airport: str,
        to_airport: str,
        departure_date: date,
        adults: int = ADULTS,
        max_stops_override: Optional[int] = None,
    ) -> List[FlightRecord]:
        """
        搜尋單一航線在指定日期的機票。
        max_stops_override: 若指定則覆蓋 self.max_stops（用於東北亞/東南亞強制直達）
        """
        from config import get_max_stops_for

        effective_stops = (
            max_stops_override
            if max_stops_override is not None
            else get_max_stops_for(to_airport, self.max_stops)
        )

        date_str = departure_date.strftime("%Y-%m-%d")
        logger.debug(f"搜尋 {from_airport} → {to_airport} on {date_str} (max_stops={effective_stops})")

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

                # stops=-1 = API 未提供，不丟棄；否則嚴格按 effective_stops 過濾
                filtered = [
                    r for r in records
                    if (r.stops == -1 or r.stops <= effective_stops)
                    and (r.duration_minutes == 0 or
                         r.duration_minutes <= self.max_duration_hours * 60)
                ]

                logger.debug(
                    f"  {from_airport}→{to_airport} {date_str}: "
                    f"{len(records)} 筆 → 過濾後 {len(filtered)} 筆"
                )
                return filtered

            except Exception as e:
                logger.warning(f"  嘗試 {attempt}/{MAX_RETRIES} 失敗: {e}")
                if attempt < MAX_RETRIES:
                    sleep_sec = REQUEST_DELAY_SEC * attempt + random.uniform(0.5, 1.5)
                    time.sleep(sleep_sec)

        return []

    def search_roundtrip(
        self,
        from_airport: str,
        to_airport: str,
        outbound_date: date,
        return_date: date,
        adults: int = ADULTS,
        max_stops_override: Optional[int] = None,
    ) -> List[FlightRecord]:
        """搜尋單一航線的來回票（一本票）。"""
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
                    # Playwright fallback: combine two one-way searches
                    from airline_classifier import classify_airline

                    out_recs = asyncio.run(self._search_playwright(from_airport, to_airport, out_str))
                    ret_recs = asyncio.run(self._search_playwright(to_airport, from_airport, ret_str))

                    if not out_recs or not ret_recs:
                        # Both legs must have data to form a valid roundtrip
                        logger.warning(
                            f"  Playwright: {from_airport}⇄{to_airport} 來回其中一段無班機，略過"
                        )
                        records = []
                    else:
                        MAX_PAIR = 15
                        out_top = sorted(out_recs, key=lambda r: r.price)[:MAX_PAIR]
                        ret_top = sorted(ret_recs, key=lambda r: r.price)[:MAX_PAIR]

                        def merge_airline(a1: str, a2: str) -> str:
                            a1 = (a1 or "").strip()
                            a2 = (a2 or "").strip()
                            if a1 == a2 and a1:
                                return a1
                            if not a1:
                                return a2
                            if not a2:
                                return a1
                            return f"{a1} / {a2}"

                        def merge_airline_type(t1: str, t2: str) -> str:
                            if "LCC" in (t1, t2):
                                return "LCC"
                            if "traditional" in (t1, t2):
                                return "traditional"
                            return "unknown"

                        def has_time(r: FlightRecord) -> bool:
                            return bool((r.departure_time or r.arrival_time))

                        full_pairs: List[FlightRecord] = []
                        partial_pairs: List[FlightRecord] = []
                        fetched_at = datetime.now().isoformat()

                        for out in out_top:
                            for ret in ret_top:
                                combined_price, combined_currency = _combine_prices(
                                    out.price, out.currency, ret.price, ret.currency
                                )
                                rec = FlightRecord(
                                    departure_airport=from_airport.upper(),
                                    arrival_airport=to_airport.upper(),
                                    departure_date=out_str,
                                    price=combined_price,
                                    currency=combined_currency,
                                    duration_minutes=out.duration_minutes,
                                    stops=out.stops,
                                    airline=merge_airline(out.airline, ret.airline),
                                    flight_numbers=(out.flight_numbers or ret.flight_numbers),
                                    departure_time=out.departure_time,
                                    arrival_time=out.arrival_time,
                                    fetched_at=fetched_at,
                                    source="playwright_paired",
                                    is_roundtrip=True,
                                    return_date=ret_str,
                                    return_duration=ret.duration_minutes,
                                    return_dep_time=ret.departure_time,
                                    return_arr_time=ret.arrival_time,
                                    airline_type=merge_airline_type(
                                        classify_airline(out.airline),
                                        classify_airline(ret.airline),
                                    ),
                                )
                                if has_time(out) and has_time(ret):
                                    full_pairs.append(rec)
                                elif has_time(out) or has_time(ret):
                                    partial_pairs.append(rec)

                        records = full_pairs if full_pairs else partial_pairs

                filtered = [
                    r for r in records
                    if (r.stops == -1 or r.stops <= effective_stops)
                    and (r.duration_minutes == 0 or r.duration_minutes <= self.max_duration_hours * 60)
                ]
                return self._dedup(filtered)

            except Exception as e:
                logger.warning(f"  round-trip 嘗試 {attempt}/{MAX_RETRIES} 失敗: {e}")
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
        """
        批量搜尋來回票。
        outbound_dates 與 return_dates 一對一對應；若 return_dates 只有一個則廣播。
        Uses Rich progress bar when available.
        """
        if len(return_dates) == 1:
            return_dates = return_dates * len(outbound_dates)

        all_records: List[FlightRecord] = []

        combos = [(dest, out, ret)
                  for dest in destinations
                  for out, ret in zip(outbound_dates, return_dates)]
        total = len(combos)

        # Use Rich progress bar if available and there are multiple combos
        try:
            from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
            _use_progress = total > 1
        except ImportError:
            _use_progress = False

        def _do_search(idx, dest, out_d, ret_d):
            from config import get_max_stops_for, get_region

            eff_stops = get_max_stops_for(dest, self.max_stops)
            region_tag = f"[{get_region(dest) or '?'}]"
            stops_tag = "直達" if eff_stops == 0 else f"≤{eff_stops}轉"

            logger.info(
                f"[{idx}/{total}] 來回 {from_airport}⇄{dest} "
                f"去:{out_d} 回:{ret_d} {region_tag} {stops_tag}"
            )

            records = self.search_roundtrip(from_airport, dest, out_d, ret_d, adults)
            all_records.extend(records)
            time.sleep(REQUEST_DELAY_SEC + random.uniform(0, 0.8))

        if _use_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task("搜尋來回票…", total=total)
                for idx, (dest, out_d, ret_d) in enumerate(combos, 1):
                    progress.update(task, description=f"搜尋 {from_airport}⇄{dest} {out_d}")
                    _do_search(idx, dest, out_d, ret_d)
                    progress.advance(task)
        else:
            for idx, (dest, out_d, ret_d) in enumerate(combos, 1):
                _do_search(idx, dest, out_d, ret_d)

        return all_records

    @staticmethod
    def _dedup(records: List[FlightRecord]) -> List[FlightRecord]:
        """去除重複紀錄（以航空公司、日期、時間、價格為唯一鍵）。"""
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

    def search_many(
        self,
        from_airport: str,
        destinations: List[str],
        departure_dates: List[date],
        adults: int = ADULTS,
    ) -> List[FlightRecord]:
        """批量搜尋單程（每個目的地自動套用 max_stops 規則）。"""
        all_records: List[FlightRecord] = []
        total = len(destinations) * len(departure_dates)
        done = 0

        for dest in destinations:
            for dep_date in departure_dates:
                done += 1
                from config import get_max_stops_for, get_region

                eff_stops = get_max_stops_for(dest, self.max_stops)
                region_tag = f"[{get_region(dest) or '?'}]"
                stops_tag = "直達" if eff_stops == 0 else f"≤{eff_stops}轉"

                logger.info(
                    f"[{done}/{total}] {from_airport} → {dest} "
                    f"{dep_date.strftime('%Y-%m-%d')} {region_tag} {stops_tag}"
                )

                records = self.search(from_airport, dest, dep_date, adults)
                all_records.extend(records)
                time.sleep(REQUEST_DELAY_SEC + random.uniform(0, 0.8))

        return self._dedup(all_records)

    # ══════════════════════════════════════════════════════════════════════════
    # Backend 1：fast-flights
    # ══════════════════════════════════════════════════════════════════════════

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

        pax = Passengers(
            adults=adults,
            children=CHILDREN,
            infants_in_seat=INFANTS,
        )

        fd = [FlightData(date=date_str, from_airport=from_airport, to_airport=to_airport)]

        effective_max = max_stops if max_stops is not None else self.max_stops
        api_max_stops = effective_max if effective_max < 2 else None

        # Try fetch modes in order. "fallback" and "force-fallback" return full data
        # (airline name, times, duration). "common" sometimes returns empty fields.
        result = None
        result_has_times = False

        for mode in ("fallback", "force-fallback", "common"):
            try:
                candidate = get_flights(
                    flight_data=fd,
                    trip="one-way",
                    seat="economy",
                    passengers=pax,
                    max_stops=api_max_stops,
                    fetch_mode=mode,
                )

                flights_check = []
                for attr in ("flights", "best_flights", "other_flights"):
                    b = getattr(candidate, attr, None)
                    if b:
                        flights_check.extend(b)

                if not flights_check:
                    continue

                # Check if times are populated in this result
                has_times = any(
                    getattr(f, "departure", "") or getattr(f, "arrival", "")
                    for f in flights_check[:5]
                )

                logger.debug(f"  fetch_mode={mode} → {len(flights_check)} 筆, times={'✓' if has_times else '✗'}")

                # Prefer a result with times; accept timeless only if nothing better found
                if has_times or result is None:
                    result = candidate
                    result_has_times = has_times

                if has_times:
                    break  # Got full data, stop trying

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

        from airline_classifier import classify_airline

        for f in flights_raw:
            try:
                rec = _parse_flight_obj(
                    f, from_airport, to_airport, date_str,
                    fetched_at, classify_airline,
                )
                if rec:
                    records.append(rec)
            except Exception as e:
                logger.debug(f"  解析 flight 物件時出錯: {e}")
                continue

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
        Google Flights round-trip API call fails in this library version
        (returns a loading page instead of data).

        Strategy: run two independent one-way searches, then pair every
        outbound flight with every return flight to produce combined records.
        Combined price = outbound price + return price.

        If either leg has no results, return [] — we only emit round-trip
        records, never one-way fallbacks from this method.
        """
        if not _HAS_FAST_FLIGHTS:
            raise RuntimeError("fast-flights 未安裝")

        from airline_classifier import classify_airline

        # ── 去程 ──────────────────────────────────────────────────────────────
        out_recs = self._search_fast_flights(
            from_airport, to_airport, outbound_date, adults, max_stops
        )

        # ── 回程 ──────────────────────────────────────────────────────────────
        ret_recs = self._search_fast_flights(
            to_airport, from_airport, return_date, adults, max_stops
        )

        # Both legs must exist to form a valid round-trip. If either is empty,
        # return nothing — we never fall back to one-way records here.
        if not out_recs:
            logger.warning(
                f"  {from_airport}→{to_airport} {outbound_date}: 去程無班機，略過此路線"
            )
            return []

        if not ret_recs:
            logger.warning(
                f"  {to_airport}→{from_airport} {return_date}: 回程無班機，略過此路線"
            )
            return []

        fetched_at = datetime.now().isoformat()
        records: List[FlightRecord] = []

        MAX_PAIR = 15

        # Prefer candidates that contain outbound/return time strings.
        def has_time(r: FlightRecord) -> bool:
            return bool((r.departure_time or r.arrival_time))

        out_top = sorted(
            out_recs,
            key=lambda r: (0 if has_time(r) else 1, r.price),
        )[:MAX_PAIR]

        ret_top = sorted(
            ret_recs,
            key=lambda r: (0 if has_time(r) else 1, r.price),
        )[:MAX_PAIR]

        def merge_airline_type(t1: str, t2: str) -> str:
            if "LCC" in (t1, t2): return "LCC"
            if "traditional" in (t1, t2): return "traditional"
            return "unknown"

        def merge_airline(a1: str, a2: str) -> str:
            if a1 == a2: return a1
            if not a1: return a2
            if not a2: return a1
            return f"{a1} / {a2}"

        # Sort: pairs where both legs have times come first, then partial
        full_pairs: List[FlightRecord] = []
        partial_pairs: List[FlightRecord] = []

        for out in out_top:
            for ret in ret_top:
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
                )

                if has_time(out) and has_time(ret):
                    full_pairs.append(rec)
                elif has_time(out) or has_time(ret):
                    partial_pairs.append(rec)
                # Skip pairs where neither leg has times — they add no value

        # Use full pairs first; fall back to partial if no full pairs exist
        records = full_pairs if full_pairs else partial_pairs

        return records

    # ══════════════════════════════════════════════════════════════════════════
    # Backend 2：Playwright（備用）
    # ══════════════════════════════════════════════════════════════════════════

    async def _search_playwright(
        self,
        from_airport: str,
        to_airport: str,
        date_str: str,
    ) -> List[FlightRecord]:
        """
        使用 Playwright 瀏覽器爬取 Google Flights。
        需先執行: playwright install chromium
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright 未安裝。請執行:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )

        url = _build_google_flights_url(from_airport, to_airport, date_str)
        records: List[FlightRecord] = []
        fetched_at = datetime.now().isoformat()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="zh-TW",
                timezone_id="Asia/Taipei",
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="networkidle",
                                timeout=PLAYWRIGHT_TIMEOUT)
                await page.wait_for_timeout(3000)

                # 嘗試展開所有結果
                try:
                    show_more = page.locator('[aria-label*="更多航班"], [aria-label*="more flights"]')
                    if await show_more.count() > 0:
                        await show_more.first.click()
                        await page.wait_for_timeout(2000)
                except Exception:
                    pass

                # 抓取航班卡片
                flight_items = await page.locator('[data-testid="flight-card"], .pIav2d, li.Rk10dc').all()
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
# Playwright 解析輔助
# ══════════════════════════════════════════════════════════════════════════════

async def _parse_playwright_item(
    item, from_airport: str, to_airport: str,
    date_str: str, fetched_at: str
) -> Optional[FlightRecord]:
    """從 Playwright locator 解析單一航班資訊。"""
    text = await item.inner_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    price = 0.0
    for line in lines:
        p = _parse_price(line)
        if p > 0:
            price = p
            break

    if price <= 0:
        return None

    duration = 0
    for line in lines:
        d = _parse_duration(line)
        if d > 0:
            duration = d
            break

    if duration <= 0:
        return None

    stops = 0
    for line in lines:
        if "直飛" in line or "Nonstop" in line.lower():
            stops = 0
            break
        m = re.search(r"(\d)\s*次?轉機|(\d)\s*stop", line, re.I)
        if m:
            stops = int(m.group(1) or m.group(2))
            break

    airline = lines[0] if lines else ""

    dep_time = ""
    arr_time = ""
    time_pat = re.compile(r"\d{1,2}:\d{2}")
    times = time_pat.findall(text)
    if len(times) >= 2:
        dep_time, arr_time = times[0], times[1]

    return FlightRecord(
        departure_airport=from_airport.upper(),
        arrival_airport=to_airport.upper(),
        departure_date=date_str,
        price=price,
        currency="TWD",
        duration_minutes=duration,
        stops=stops,
        airline=airline,
        flight_numbers="",
        departure_time=dep_time,
        arrival_time=arr_time,
        fetched_at=fetched_at,
        source="playwright",
    )


# ══════════════════════════════════════════════════════════════════════════════
# 工具函式
# ══════════════════════════════════════════════════════════════════════════════

def _parse_flight_obj(
    f,
    from_airport: str,
    to_airport: str,
    date_str: str,
    fetched_at: str,
    classify_fn,
) -> Optional[FlightRecord]:
    """
    Parse a single Flight object from the fast-flights API into a FlightRecord.
    Returns None if price is missing or invalid.

    Currency note: fast-flights may return MYR currency metadata regardless of
    the user's IP or locale (library default). Since Flyaway is Taiwan-only and
    the price magnitudes confirm TWD values, we always store TWD.
    """
    price_raw = str(getattr(f, "price", None) or getattr(f, "min_price", None) or "")
    price, detected_currency = _parse_price_and_currency(price_raw)
    if price <= 0:
        return None

    # Convert to TWD if the API returned a foreign currency (e.g. MYR).
    # fast-flights may report MYR regardless of IP/locale.
    from config import TWD_FALLBACK_RATES
    if detected_currency and detected_currency.upper() != "TWD":
        rate = TWD_FALLBACK_RATES.get(detected_currency.upper(), 1.0)
        price = round(price * rate, 0)
    use_currency = "TWD"

    dur_raw = getattr(f, "duration", None) or getattr(f, "travel_duration", None) or ""
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

    airline = str(getattr(f, "name", "") or getattr(f, "airline", "") or "").strip()

    fn_raw = getattr(f, "flight_number", None) or getattr(f, "flight_numbers", None) or []
    fn_str = (
        ", ".join(str(x) for x in fn_raw)
        if isinstance(fn_raw, (list, tuple)) else str(fn_raw)
    )

    dep_time = str(getattr(f, "departure", "") or getattr(f, "departure_time", "") or "").strip()
    arr_time = str(getattr(f, "arrival", "") or getattr(f, "arrival_time", "") or "").strip()
    ahead = str(getattr(f, "arrival_time_ahead", "") or "").strip()
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
    )


def _combine_prices(
    price1: float, cur1: str,
    price2: float, cur2: str,
) -> tuple:
    """
    Add two prices. Both should be TWD after _parse_flight_obj normalization.
    Fallback conversion retained for safety (e.g. Playwright backend).
    """
    # Fast path: same currency (expected TWD + TWD after normalization)
    if cur1 == cur2:
        return round(price1 + price2, 2), cur1

    # Fallback: convert both to TWD using static rates
    from config import TWD_FALLBACK_RATES
    rate1 = TWD_FALLBACK_RATES.get(cur1.upper(), 1.0)
    rate2 = TWD_FALLBACK_RATES.get(cur2.upper(), 1.0)
    total_twd = round(price1 * rate1 + price2 * rate2, 0)
    return total_twd, "TWD"


def _parse_price_and_currency(text: str) -> tuple:
    """
    從 fast-flights 回傳的價格字串中解出金額（幣別標籤被丟棄，由呼叫方決定幣別）。

    範例輸入：
        'MYR\\xa0589'  → (589.0, 'MYR')   ← currency returned but not used
        'TWD 1,234'   → (1234.0, 'TWD')
        '$500'        → (500.0, '')
        '1234'        → (1234.0, '')
    """
    if not text:
        return 0.0, ""

    text = text.replace("\xa0", " ").strip()

    currency = ""
    m = re.match(r"^([A-Z]{3})\s*(.+)$", text)
    if m:
        currency = m.group(1)
        text = m.group(2)

    digits = re.sub(r"[^\d.]", "", text)
    parts = digits.split(".")
    if len(parts) > 2:
        digits = "".join(parts[:-1]) + "." + parts[-1]

    try:
        price = float(digits) if digits else 0.0
    except ValueError:
        price = 0.0

    return price, currency


def _parse_price(text: str) -> float:
    """向下相容包裝，只回傳金額。"""
    price, _ = _parse_price_and_currency(text)
    return price


def _parse_duration(text: str) -> int:
    """
    將時間字串轉換為分鐘數。
    支援：'13 hr 30 min', '13h30m', '13小時30分', '810 min', '13:30' 等格式
    """
    if not text:
        return 0

    text = str(text).strip()

    m = re.search(r"(\d+)\s*(?:hr|h|小時|時)[^\d]*(\d*)\s*(?:min|m|分)?", text, re.I)
    if m:
        hours = int(m.group(1))
        minutes = int(m.group(2)) if m.group(2) else 0
        return hours * 60 + minutes

    m = re.search(r"^(\d+)\s*(?:min|分)$", text, re.I)
    if m:
        return int(m.group(1))

    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))

    return 0


def _parse_stops_str(text: str) -> int:
    """從文字描述解析轉機次數。例：'Nonstop'→0, '1 stop'→1, '2 stops'→2"""
    if not text or text in ("None", "0", ""):
        return 0
    low = text.lower()
    if "nonstop" in low or "direct" in low or "直飛" in low:
        return 0
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else 0


def _debug_flight_object(f) -> str:
    """印出 flight 物件的所有屬性，用於診斷 API 結構變化。"""
    attrs = {}
    for attr in dir(f):
        if not attr.startswith("_"):
            try:
                attrs[attr] = getattr(f, attr)
            except Exception:
                pass
    return str(attrs)


def _build_google_flights_url(
    from_airport: str,
    to_airport: str,
    date_str: str,
    adults: int = 1,
) -> str:
    """產生 Google Flights 的直接搜尋 URL。"""
    base = "https://www.google.com/travel/flights"
    params = (
        f"?q=Flights+from+{from_airport}+to+{to_airport}"
        f"&hl=zh-TW"
        f"&curr=TWD"
    )
    return base + params


def build_date_range(
    center_date: date,
    flexibility_days: int = 3,
) -> List[date]:
    """
    圍繞某個日期產生一個日期範圍（用於假期前後彈性搜尋）。
    """
    return [
        center_date + timedelta(days=delta)
        for delta in range(-flexibility_days, flexibility_days + 1)
    ]