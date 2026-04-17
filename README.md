# ✈️ Flyaway — Cheapest Flight Finder from Taipei

An automated flight price monitoring system that scrapes Google Flights daily
to find the cheapest fares departing from Taipei (TPE/TSA).
It also analyzes Taiwan's public holidays to identify travel windows that
maximize days off while minimizing leave taken.

---

## Features

| Feature | Description |
|---|---|
| 🌍 Global Price Comparison | Taipei (TPE/TSA) → 80+ cities worldwide, fully customizable |
| ⏱️ Flight Constraints | Max 2 stopovers, max 26-hour one-way duration (configurable) |
| 📅 Holiday Planning | Automatically finds the best travel windows around Taiwan's public holidays |
| 🤖 Daily Scheduling | APScheduler cron job runs searches at a fixed time every day |
| 💾 Price History | SQLite database stores all results for historical price queries |
| 📊 Reports | Rich terminal color tables + CSV export |

---

## Installation

```bash
# 1. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
.venv\Scripts\activate             # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright browser (fallback backend)
playwright install chromium
```

---

## Usage

### ① Interactive Search (Easiest)

```bash
python main.py
# or
python main.py search
```

The program will walk you through: departure airport, destination region, travel dates, etc.

---

### ② Search with Parameters

```bash
# Search flights to Tokyo, departing in the next two days
python main.py search --dest NRT,KIX --date 2025-10-10,2025-10-11

# Search all destinations using optimal holiday dates
python main.py search --dest ALL --use-holidays

# Search Southeast Asia with max 1 stopover
python main.py search --dest "SE Asia" --use-holidays --max-stops 1

# Search and export results to CSV
python main.py search --dest NRT --date 2025-12-20 --export-csv
```

---

### ③ View Taiwan Holiday Travel Windows

```bash
python main.py holidays                # Next 12 months
python main.py holidays --days 180     # Next 6 months
python main.py holidays --min-days 5   # Windows of at least 5 days
```

**Sample output:**

```
┌─────────────────────────────────────────────────────────────────────┐
│              Best Travel Windows (Minimum Leave Required)           │
├────────────────┬────────────────┬───────┬───────┬───────┬──────────┤
│ Departure      │ Return         │ Total │ Leave │ Score │ Holidays │
├────────────────┼────────────────┼───────┼───────┼───────┼──────────┤
│ 2025-10-09 Thu │ 2025-10-13 Mon │  5    │   0   │  5.0  │ National Day │
│ 2025-01-25 Sat │ 2025-02-02 Sun │  9    │   0   │  9.0  │ Lunar New Year │
│ 2025-02-27 Thu │ 2025-03-02 Sun │  4    │   1   │  2.0  │ Peace Memorial Day │
└────────────────┴────────────────┴───────┴───────┴───────┴──────────┘
```

---

### ④ Start the Daily Automated Scheduler

```bash
# Run every day at 07:00 (Taiwan time)
python main.py schedule

# Custom time, with an immediate first run
python main.py schedule --time 08:30 --run-now

# Only search specific destinations
python main.py schedule --time 06:00 --dest NRT,SIN,BKK,CDG,LAX
```

---

### ⑤ Query Historical Lowest Prices

```bash
# All-time lowest prices across all destinations in the database
python main.py history

# Price trend for a specific route over the last 30 days
python main.py history --to NRT --days 30
python main.py history --to LAX --days 60
```

---

## Configuration

All settings are centralized in `config.py`:

```python
# Daily schedule time (Taiwan time)
SCHEDULE_TIME = "07:00"

# Flight constraints
MAX_STOPS          = 2    # Maximum number of stopovers
MAX_DURATION_HOURS = 26   # Maximum one-way flight duration in hours

# Holiday search range
HOLIDAY_LOOKAHEAD_DAYS = 180
MIN_TRIP_DAYS = 3
MAX_TRIP_DAYS = 14

# Number of results to display
TOP_N_RESULTS = 20
```

---

## Destination Region Codes

| Region Code | Cities Included |
|---|---|
| `NE Asia` | Tokyo, Osaka, Seoul, Hong Kong… |
| `SE Asia` | Bangkok, Singapore, Kuala Lumpur, Bali… |
| `Europe` | London, Paris, Frankfurt, Rome… |
| `N America` | New York, Los Angeles, San Francisco… |
| `Oceania` | Sydney, Melbourne, Auckland… |
| `ALL` | All 80+ destinations |

---

## Architecture

```
flyaway/
├── main.py              # Entry point; CLI command definitions
├── config.py            # Global settings (airports, destinations, constraints)
├── taiwan_holidays.py   # Taiwan holiday parsing & minimum-leave planning algorithm
├── flight_scraper.py    # Google Flights scraping engine
│                        #   Backend 1: fast-flights (protobuf API)
│                        #   Backend 2: Playwright (browser fallback)
├── airline_classifier.py# Airline categorization utilities
├── currency.py          # Currency conversion helpers
├── database.py          # SQLite storage and queries
├── scheduler.py         # APScheduler daily cron task
├── reporter.py          # Rich terminal tables & CSV export
├── setup_check.py       # Dependency and environment validation
├── requirements.txt
├── flights.db           # Auto-created SQLite database
└── reports/             # CSV report output directory
```

---

## ⚠️ Important Notes

> **Google Flights Scraping Limitations**
>
> Google Flights does not provide a public API. This system uses the `fast-flights`
> package, which communicates via the protobuf protocol, with Playwright as a
> browser-based fallback. Please respect Google's Terms of Service and avoid
> excessively frequent requests.
> A minimum delay of 2–3 seconds between requests is enforced
> (`REQUEST_DELAY_SEC = 2.5` in `config.py`).

---

## FAQ

**Q: `fast-flights` returns no results?**
Google Flights' protobuf API format occasionally changes. Switch to the Playwright
backend by setting `self._backend = "playwright"` in `FlightScraper.__init__`
inside `flight_scraper.py`.

**Q: How do I add more destinations?**
Edit the `WORLD_DESTINATIONS` dictionary in `config.py` and add the IATA airport
code for the city you want.

**Q: How do I run this as a system service (start on boot)?**
- **Linux:** Create a `systemd` service unit
- **macOS:** Use `launchd`
- **Windows:** Use Task Scheduler
- You can also containerize with **Docker** for platform-independent deployment.

---

## Tech Stack

- **Python 3.10+**
- [`fast-flights`](https://github.com/AWeirdDev/flights) — protobuf-based Google Flights client
- [`playwright`](https://playwright.dev/python/) — browser automation fallback
- [`APScheduler`](https://apscheduler.readthedocs.io/) — cron-style job scheduling
- [`Rich`](https://rich.readthedocs.io/) — beautiful terminal output
- `SQLite` — lightweight local data persistence

---

## License

MIT