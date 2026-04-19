# ✈️ Flyaway — Cheapest Round-Trip Flight Finder from Taipei

An automated flight price monitoring system that scrapes Google Flights to find
the cheapest **round-trip** fares departing from Taipei (TPE / TSA) to 80+
destinations worldwide. It also analyzes Taiwan's public holidays to identify
optimal travel windows that maximize days off while minimizing annual leave.

> **Built as an AI-assisted coding project** — This entire system was designed,
> developed, and iterated with AI pair-programming, demonstrating how a single
> developer can rapidly build a production-quality, multi-module Python
> application using AI tools.

---

## Features

| Feature | Description |
|---|---|
| 🔍 Round-Trip Search | Search round-trip fares with outbound + return date pairs |
| 🌍 80+ Destinations | Japan, Korea, SE Asia, Europe, N America, Oceania — fully customizable |
| ✈️ Smart Stop Rules | Asia short-haul → nonstop only; intercontinental → up to 2 transfers |
| 📅 Holiday Planner | Finds the best travel windows around Taiwan public holidays |
| 🏖️ Vacation Mode | Three preset modes — short (5 days), long (9 days), happy (16 days) |
| 📐 Flexible Dates | Search ±N days around your preferred dates in one run |
| 🔗 Booking Links | Each result includes a Google Flights link + airline direct booking URL |
| 💰 TWD Pricing | Prices displayed in NT$ with automatic currency conversion |
| 🏷️ LCC / Traditional | Results split into legacy carrier and low-cost carrier tables |
| 📢 Notifications | Price alerts via LINE Notify, Telegram, or Email |
| 🤖 Daily Scheduler | Cron-style automation with APScheduler (Asia/Taipei timezone) |
| 💾 SQLite Database | Stores all search results locally for later querying |
| 📊 Reports | Rich color terminal tables + CSV export to `reports/` |

---

## Quick Start

### 1. Install

```bash
# Create a virtual environment (recommended)
python -m venv .venv

# Activate it
.venv\Scripts\activate             # Windows
source .venv/bin/activate          # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser (optional — fallback scraping backend)
playwright install chromium
```

### 2. Verify Setup

```bash
python setup_check.py
```

This checks all required packages and offers to install any that are missing.

### 3. Run

```bash
python main.py                      # Interactive mode — walks you through everything
```

---

## Usage Guide

### ① Interactive Search (Recommended for First-Time Users)

```bash
python main.py search
```

The program will interactively ask you to choose:
1. **Departure airport** — TPE (Taoyuan) or TSA (Songshan)
2. **Destination** — pick a region, enter airport codes, or search all
3. **Travel dates** — enter dates or use holiday windows
4. **Return date** — enter a date or just a number of trip days (e.g. `5`)
5. **Flexible dates** — optionally search ±1~3 days around your dates
6. **Currency** — display in TWD or original currency

---

### ② Command-Line Search (Scripting / Automation)

```bash
# Round-trip to Tokyo Narita, 5-day trip, in TWD, skip all prompts
python main.py search --dest NRT --outbound 2026-05-01 --return 5 --twd --yes

# Multiple destinations with flexible dates
python main.py search --dest NRT,KIX,ICN --outbound 2026-06-10 --return 5 --flex 2

# Search by region name (English or Chinese supported)
python main.py search --dest "SE Asia" --outbound 2026-07-01 --return 5
python main.py search --dest "歐洲" --outbound 2026-07-01 --flex 1

# Use composite regions (Japan + Korea = NE Asia)
python main.py search --dest "東北亞" --outbound 2026-05-01

# Auto-pick dates from Taiwan holiday windows
python main.py search --dest ALL --use-holidays --flex 2 --twd

# Search only your personal favourites (defined in config.py)
python main.py search --dest MY --use-holidays

# Export results to CSV
python main.py search --dest NRT --outbound 2026-05-01 --return 5 --export-csv
```

**Key `search` flags:**

| Flag | Description |
|---|---|
| `--dest` | IATA code(s), region name, `MY` (favourites), or `ALL` |
| `--outbound` | Departure date(s) — `YYYY-MM-DD`, comma-separated for multiple |
| `--return` | Return date(s) or trip length in days (e.g. `5`) |
| `--use-holidays` | Automatically select dates from Taiwan holiday windows |
| `--flex N` | Search ±N days around each outbound/return date |
| `--twd` | Display all prices in TWD |
| `--max-stops N` | Override max transfers for intercontinental routes |
| `--export-csv` | Save results to `reports/` as CSV |
| `-y / --yes` | Skip all confirmation prompts (useful for CI/scripts) |

---

### ③ Vacation Mode

Three pre-configured travel styles. Each mode automatically finds the best travel
windows and searches the most relevant destinations.

```bash
python main.py vacation --mode short        # 5-day Asia nonstop (1 weekend)
python main.py vacation --mode long         # 9-day intercontinental (2 weekends)
python main.py vacation --mode happy        # 16-day long holiday (3 weekends)

# With CSV export
python main.py vacation --mode happy --export-csv

# Override flexible days
python main.py vacation --mode short --flex 2
```

| Mode | Days | Weekends | Destinations | Max Stops |
|---|---|---|---|---|
| `short` | 5 | 1 | Asia (nonstop only) | 0 |
| `long` | 9 | 2 | Europe, N America, Oceania | 2 |
| `happy` | 16 | 3 | Europe, N America, Oceania | 2 |

---

### ④ Taiwan Holiday Travel Windows

View upcoming holidays and the most efficient travel windows (fewest leave days
for the most trip days).

```bash
python main.py holidays                     # Next 12 months
python main.py holidays --days 180          # Next 6 months
python main.py holidays --min-days 5        # Only windows ≥ 5 days
python main.py holidays --intercontinental  # 9–18 day windows for long-haul
```

**Sample output:**

```
┌─────────────────────────────────────────────────────────────────────┐
│              Best Travel Windows (Minimum Leave Required)           │
├────────────────┬────────────────┬───────┬───────┬───────┬──────────┤
│ Departure      │ Return         │ Total │ Leave │ Score │ Holidays │
├────────────────┼────────────────┼───────┼───────┼───────┼──────────┤
│ 2026-10-09 Fri │ 2026-10-13 Tue │  5    │   1   │  5.0  │ National Day │
│ 2026-02-14 Sat │ 2026-02-22 Sun │  9    │   0   │  9.0  │ Lunar New Year │
│ 2026-02-27 Fri │ 2026-03-02 Mon │  4    │   1   │  2.0  │ Peace Memorial │
└────────────────┴────────────────┴───────┴───────┴───────┴──────────┘
```

> **Tip:** Run `python main.py search --use-holidays` to directly search flights
> for these dates.

---

### ⑤ Daily Automated Scheduler

Set up a recurring cron job to automatically search and report every day.

```bash
python main.py schedule                     # Default: 07:00 Taiwan time
python main.py schedule --time 08:30 --run-now   # Custom time + run immediately
python main.py schedule --dest NRT,SIN,BKK       # Only specific destinations
```

The scheduler:
1. Clears old data (prices change daily — stale data is not useful)
2. Computes travel date pairs from upcoming Taiwan holidays
3. Runs round-trip searches across all configured destinations
4. Stores results in SQLite
5. Outputs a grouped terminal report + CSV export

Press `Ctrl+C` to stop the scheduler.

---

### ⑥ API Debug Tool

Diagnose the `fast-flights` API response structure for troubleshooting.

```bash
python main.py debug-api --dest NRT
python main.py debug-api --dest SIN --date 2026-06-01 --ret-date 2026-06-06
```

---

## Configuration

All settings are in [`config.py`](config.py). Key options:

```python
# ── Destinations ──────────────────────────────────────
WORLD_DESTINATIONS    # 80+ airports grouped by region
MY_DESTINATIONS       # Your personal favourite airports
USER_DESTINATIONS     # Extra airports not in any region

# ── Flight constraints ────────────────────────────────
MAX_STOPS          = 2      # Max transfers (intercontinental)
MAX_DURATION_HOURS = 26     # Max one-way flight hours
# Note: Asia short-haul is forced to 0 stops automatically

# ── Trip length defaults ──────────────────────────────
ASIA_DEFAULT_TRIP_DAYS  = 5
INTER_DEFAULT_TRIP_DAYS = 9

# ── Scheduler ─────────────────────────────────────────
SCHEDULE_TIME = "07:00"     # Daily run time (Asia/Taipei)

# ── Reports ───────────────────────────────────────────
TOP_N_RESULTS = 20          # Max results per table

# ── Rate limiting ─────────────────────────────────────
REQUEST_DELAY_SEC = 2.5     # Delay between API requests
MAX_RETRIES       = 3       # Retry failed requests
```

### Notifications (Optional)

Set environment variables or edit `config.py` to enable price alerts:

| Channel | Required Environment Variables |
|---|---|
| LINE Notify | `LINE_NOTIFY_TOKEN` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Email (SMTP) | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO` |

Alerts trigger when a fare drops below `PRICE_ALERT_THRESHOLD_TWD` (default: 15,000 TWD).

---

## Destination Regions

Destinations support **English names**, **Chinese names**, and **composite groups**.

| Region | Chinese | Airport Count | Stop Rule |
|---|---|---|---|
| `Japan` | 日本 | 30 | Nonstop only |
| `Korea` | 韓國 | 7 | Nonstop only |
| `SE Asia` | 東南亞 | 25 | Nonstop only |
| `Europe` | 歐洲 | 20 | Up to 2 stops |
| `N America` | 北美 | 14 | Up to 2 stops |
| `Oceania` | 大洋洲 | 5 | Up to 2 stops |

**Composite regions** (span multiple atomic regions):

| Group | Chinese | Includes |
|---|---|---|
| `NE Asia` | 東北亞 | Japan + Korea |
| `East Asia` | 東亞 | Japan + Korea + SE Asia |

Use `ALL` to search every destination, or `MY` for your personal favourites.

---

## Project Architecture

```
flyaway/
│
├── main.py                # CLI entry point — subcommands: search, vacation,
│                          #   schedule, holidays, debug-api
├── config.py              # All tunable settings — destinations, constraints,
│                          #   vacation modes, notification tokens
│
├── flight_scraper.py      # Google Flights scraping engine
│                          #   Primary: fast-flights (protobuf API)
│                          #   Fallback: Playwright (headless browser)
│
├── database.py            # SQLite ORM — FlightRecord dataclass, CRUD, queries
├── reporter.py            # Rich terminal tables + CSV export with booking links
├── booking_links.py       # URL builder for Google Flights & airline direct sites
├── airline_classifier.py  # Classifies airlines as LCC or traditional carrier
│
├── vacation_windows.py    # Vacation Mode engine — find optimal travel windows
│                          #   by mode (short / long / happy)
├── taiwan_holidays.py     # Taiwan public holiday parser + bridge-holiday calculator
│                          #   Supports the `holidays` package + hardcoded fallback
│
├── notifier.py            # Price alert dispatcher — LINE, Telegram, Email
├── scheduler.py           # APScheduler cron job for daily automated searches
├── setup_check.py         # Dependency checker + one-click installer
│
├── requirements.txt       # Pinned Python dependencies
├── flights.db             # SQLite database (auto-created on first run)
└── reports/               # CSV report output directory
```

### Data Flow

```
User CLI / Scheduler
        │
        ▼
   ┌─────────┐     ┌──────────────────────┐
   │ main.py │────▶│ taiwan_holidays.py   │  ← holiday window calculation
   └────┬────┘     └──────────────────────┘
        │
        ▼
┌───────────────────┐    ┌────────────────────────┐
│ flight_scraper.py │───▶│ airline_classifier.py  │  ← LCC / traditional tagging
└───────┬───────────┘    └────────────────────────┘
        │
        ▼
  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
  │ database.py │   │ reporter.py  │   │ notifier.py  │
  │ (SQLite)    │   │ (tables/CSV) │   │ (alerts)     │
  └─────────────┘   └──────┬───────┘   └──────────────┘
                           │
                           ▼
                    ┌──────────────────┐
                    │ booking_links.py │  ← Google Flights & airline URLs
                    └──────────────────┘
```

---

## ⚠️ Important Notes

> **Google Flights Scraping Limitations**
>
> Google Flights does not provide a public API. This system uses
> [`fast-flights`](https://github.com/AWeirdDev/flights), which communicates via
> Google's internal protobuf protocol, with Playwright as a headless browser
> fallback. A minimum delay of 2.5 seconds between requests is enforced. Please
> respect Google's Terms of Service and avoid excessive automated requests.

---

## FAQ

**Q: `fast-flights` returns no results?**
The upstream protobuf API format changes occasionally. Try setting
`self._backend = "playwright"` in `FlightScraper.__init__()` inside
[flight_scraper.py](flight_scraper.py), or run `python main.py debug-api --dest NRT`
to diagnose.

**Q: How do I add a new destination?**
Add the IATA airport code to the appropriate region list in `WORLD_DESTINATIONS`
inside [config.py](config.py). The system will automatically pick up the right
stop rules based on its region.

**Q: How do I set up notifications?**
Set environment variables for your preferred channel (see the
[Notifications](#notifications-optional) section). You can enable one, two, or all
three channels simultaneously — they work independently.

**Q: Can I run this as a system service?**
- **Windows:** Task Scheduler
- **Linux:** `systemd` service unit
- **macOS:** `launchd`
- **Docker:** Containerize for platform-independent deployment

**Q: What Python version do I need?**
Python 3.10 or later (uses `match` syntax and `dict[str, ...]` type hints).

---

## Tech Stack

| Component | Library | Purpose |
|---|---|---|
| Flight Data | [`fast-flights`](https://github.com/AWeirdDev/flights) | Protobuf-based Google Flights client |
| Browser Fallback | [`Playwright`](https://playwright.dev/python/) | Headless Chromium scraping |
| Scheduling | [`APScheduler`](https://apscheduler.readthedocs.io/) | Cron-style daily job runner |
| Terminal UI | [`Rich`](https://rich.readthedocs.io/) | Color tables, panels, progress bars |
| Holiday Data | [`holidays`](https://github.com/vacanza/python-holidays) | Taiwan public holiday calendar |
| Database | `SQLite` (stdlib) | Lightweight local data persistence |
| Notifications | `requests` + `smtplib` | LINE Notify, Telegram Bot, Email |

---

## License

MIT