"""
database.py — SQLite 資料庫操作層
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional

from config import DB_PATH


@dataclass
class FlightRecord:
    departure_airport: str
    arrival_airport:   str
<<<<<<< Updated upstream
    departure_date:    str
=======
    departure_date:    str          # YYYY-MM-DD
>>>>>>> Stashed changes
    price:             float
    currency:          str
    duration_minutes:  int          # 0 = unknown
    stops:             int          # -1 = unknown
    airline:           str
    flight_numbers:    str
    departure_time:    str
    arrival_time:      str
    fetched_at:        str
<<<<<<< Updated upstream
    source:            str  = "google_flights"
    is_roundtrip:      bool = False
    return_date:       str  = ""
    return_duration:   int  = 0
    return_dep_time:   str  = ""
    return_arr_time:   str  = ""
    airline_type:      str  = ""   # "LCC" | "traditional" | "unknown"
    google_search_url: str  = ""   # Google Flights TFS search URL for this route/date
    id:                Optional[int] = None
=======
    source:            str = "google_flights"

    # ── 新增欄位（migration-safe） ───────────────────────────────────────
    is_roundtrip:   bool = False
    return_date:    str  = ""       # YYYY-MM-DD (round-trip 回程日)
    return_duration: int = 0        # 回程飛行分鐘
    return_dep_time: str = ""
    return_arr_time: str = ""
    airline_type:   str  = ""       # "LCC" | "traditional" | ""
    booking_url:    str  = ""       # 預留：Playwright 擷取的直售連結（未來功能）

    id: Optional[int] = None
>>>>>>> Stashed changes

    @property
    def duration_str(self) -> str:
        if self.duration_minutes <= 0:
            return "—"
        h, m = divmod(self.duration_minutes, 60)
        return f"{h}h {m:02d}m"

    @property
    def stops_str(self) -> str:
        if self.stops == -1:
            return "直達*"
        if self.stops == 0:
            return "直達"
        return f"{self.stops}轉"


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS flights (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    departure_airport TEXT    NOT NULL,
                    arrival_airport   TEXT    NOT NULL,
                    departure_date    TEXT    NOT NULL,
                    price             REAL    NOT NULL,
                    currency          TEXT    NOT NULL DEFAULT '',
                    duration_minutes  INTEGER NOT NULL DEFAULT 0,
                    stops             INTEGER NOT NULL DEFAULT 0,
                    airline           TEXT,
                    flight_numbers    TEXT,
                    departure_time    TEXT,
                    arrival_time      TEXT,
                    fetched_at        TEXT    NOT NULL,
                    source            TEXT    NOT NULL DEFAULT 'google_flights'
                );

                CREATE INDEX IF NOT EXISTS idx_flights_date
                    ON flights(departure_date);
                CREATE INDEX IF NOT EXISTS idx_flights_price
                    ON flights(price);
                CREATE INDEX IF NOT EXISTS idx_flights_route
                    ON flights(departure_airport, arrival_airport);

                CREATE TABLE IF NOT EXISTS search_log (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    searched_at   TEXT    NOT NULL,
                    from_airport  TEXT    NOT NULL,
                    to_airport    TEXT,
                    date_range    TEXT,
                    results_count INTEGER DEFAULT 0,
                    error_msg     TEXT
                );
            """)
<<<<<<< Updated upstream
            # Add new columns gracefully (migration-safe)
            new_cols = [
                ("is_roundtrip",      "INTEGER NOT NULL DEFAULT 0"),
                ("return_date",       "TEXT    NOT NULL DEFAULT ''"),
                ("return_duration",   "INTEGER NOT NULL DEFAULT 0"),
                ("return_dep_time",   "TEXT    NOT NULL DEFAULT ''"),
                ("return_arr_time",   "TEXT    NOT NULL DEFAULT ''"),
                ("airline_type",      "TEXT    NOT NULL DEFAULT ''"),
                ("google_search_url", "TEXT    NOT NULL DEFAULT ''"),
=======

            # ── Migrate: add new columns if they don't exist yet ────────────
            new_columns = [
                ("is_roundtrip",    "INTEGER NOT NULL DEFAULT 0"),
                ("return_date",     "TEXT    NOT NULL DEFAULT ''"),
                ("return_duration", "INTEGER NOT NULL DEFAULT 0"),
                ("return_dep_time", "TEXT    NOT NULL DEFAULT ''"),
                ("return_arr_time", "TEXT    NOT NULL DEFAULT ''"),
                ("airline_type",    "TEXT    NOT NULL DEFAULT ''"),
                ("booking_url",     "TEXT    NOT NULL DEFAULT ''"),   # 預留 Playwright 直售連結
>>>>>>> Stashed changes
            ]
            for col, defn in new_cols:
                try:
                    conn.execute(f"ALTER TABLE flights ADD COLUMN {col} {defn}")
                    conn.commit()
                except Exception:
                    pass  # column already exists
<<<<<<< Updated upstream
            # Indexes for migrated columns
=======

            # ── Indexes that depend on migrated columns ──────────────────────
>>>>>>> Stashed changes
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_flights_type ON flights(airline_type)",
                "CREATE INDEX IF NOT EXISTS idx_flights_rt   ON flights(is_roundtrip)",
            ]:
                try:
                    conn.execute(idx_sql)
                except Exception:
                    pass

    def bulk_insert_flights(self, records: List[FlightRecord]) -> int:
        if not records:
            return 0
        with self._conn() as conn:
            conn.executemany(
                """INSERT INTO flights
<<<<<<< Updated upstream
                   (departure_airport, arrival_airport, departure_date,
                    price, currency, duration_minutes, stops, airline,
                    flight_numbers, departure_time, arrival_time,
                    fetched_at, source, is_roundtrip, return_date,
                    return_duration, return_dep_time, return_arr_time,
                    airline_type, google_search_url)
=======
                    (departure_airport, arrival_airport, departure_date,
                     price, currency, duration_minutes, stops, airline,
                     flight_numbers, departure_time, arrival_time,
                     fetched_at, source, is_roundtrip, return_date,
                     return_duration, return_dep_time, return_arr_time,
                     airline_type, booking_url)
>>>>>>> Stashed changes
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(r.departure_airport, r.arrival_airport, r.departure_date,
                  r.price, r.currency, r.duration_minutes, r.stops,
                  r.airline, r.flight_numbers, r.departure_time,
                  r.arrival_time, r.fetched_at, r.source,
                  int(r.is_roundtrip), r.return_date, r.return_duration,
                  r.return_dep_time, r.return_arr_time, r.airline_type,
<<<<<<< Updated upstream
                  r.google_search_url)
=======
                  getattr(r, "booking_url", ""))
>>>>>>> Stashed changes
                 for r in records]
            )
        return len(records)

    def insert_flight(self, record: FlightRecord) -> int:
        return self.bulk_insert_flights([record])

    def get_cheapest(
        self,
        from_airport:       Optional[str] = None,
        to_airport:         Optional[str] = None,
        departure_date:     Optional[str] = None,
        max_stops:          int = 2,
        max_duration_hours: int = 26,
        limit:              int = 20,
        airline_type:       Optional[str] = None,
    ) -> List[FlightRecord]:
        conditions = ["(stops = -1 OR stops <= ?)", "duration_minutes <= ?"]
        params: list = [max_stops, max_duration_hours * 60]
        if from_airport:
            conditions.append("departure_airport = ?"); params.append(from_airport.upper())
        if to_airport:
            conditions.append("arrival_airport = ?");   params.append(to_airport.upper())
        if departure_date:
            conditions.append("departure_date = ?");    params.append(departure_date)
        if airline_type:
            conditions.append("airline_type = ?");      params.append(airline_type)
        where = "WHERE " + " AND ".join(conditions)
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM flights {where} ORDER BY price ASC LIMIT ?", params
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def get_cheapest_per_destination(
        self,
        from_airport:       str = "TPE",
        departure_date:     Optional[str] = None,
        max_stops:          int = 2,
        max_duration_hours: int = 26,
        fetched_today:      bool = True,
    ) -> List[FlightRecord]:
        today_filter = ""
        params: list = [max_stops, max_duration_hours * 60, from_airport.upper()]
        if fetched_today:
            today_filter = "AND date(fetched_at) = ?"
            params.append(datetime.now().strftime("%Y-%m-%d"))
        date_filter = ""
        if departure_date:
            date_filter = "AND departure_date = ?"
            params.append(departure_date)
        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT f.* FROM flights f
                    INNER JOIN (
                        SELECT arrival_airport, MIN(price) AS min_price
                        FROM flights
                        WHERE (stops = -1 OR stops <= ?)
                          AND duration_minutes <= ?
                          AND departure_airport = ?
                          {today_filter} {date_filter}
                        GROUP BY arrival_airport
                    ) best ON f.arrival_airport = best.arrival_airport
                           AND f.price = best.min_price
                           AND f.departure_airport = ?
                    ORDER BY f.price ASC""",
                params + [from_airport.upper()]
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def get_price_history(
        self, from_airport: str, to_airport: str, days: int = 30
    ) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT date(fetched_at) AS day, MIN(price) AS min_price,
                          AVG(price) AS avg_price, currency
                   FROM flights
                   WHERE departure_airport = ? AND arrival_airport = ?
                     AND date(fetched_at) >= date('now', ?)
                   GROUP BY day ORDER BY day""",
                (from_airport.upper(), to_airport.upper(), f"-{days} days")
            ).fetchall()
        return [dict(r) for r in rows]

    def log_search(
        self, from_airport, to_airport, date_range, results_count, error_msg=""
    ):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO search_log "
                "(searched_at,from_airport,to_airport,date_range,results_count,error_msg) "
                "VALUES (?,?,?,?,?,?)",
                (datetime.now().isoformat(), from_airport, to_airport,
                 date_range, results_count, error_msg)
            )


def _row_to_record(row: sqlite3.Row) -> FlightRecord:
    d = dict(row)
    fields = FlightRecord.__dataclass_fields__
    kwargs = {k: d[k] for k in fields if k in d}
    if "is_roundtrip" in kwargs:
        kwargs["is_roundtrip"] = bool(kwargs["is_roundtrip"])
    return FlightRecord(**kwargs)