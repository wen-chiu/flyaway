# Flyaway — PyInstaller Packaging Plan

This document captures the **plan only** for producing a standalone Windows
executable. No `pyinstaller` invocation has been run yet.

---

## Goal

Ship a single-directory (or single-file) Windows build that a non-technical
user can unzip and launch by double-clicking, with no Python install required.
The bundle must launch `app.py` via `run_gui.py` and open the user's default
browser automatically.

---

## Known Challenges & Strategies

### 1. Streamlit runtime assets
Streamlit ships a lot of data files (static HTML/JS, component manifests,
config defaults). PyInstaller's static analysis misses most of them.

**Strategy**: `collect_all("streamlit")` in the spec file. Also collect
`streamlit.runtime`, `streamlit.web`, and `importlib_metadata` hooks. Use
`--copy-metadata streamlit` to keep `pkg_resources` lookups working.

### 2. `fast_flights` + `primp` / `protobuf`
`fast_flights` depends on `primp` (Rust-compiled HTTP client) and uses
`protobuf` generated modules loaded dynamically.

**Strategy**:
- `collect_all("fast_flights")` + `collect_submodules("fast_flights")`.
- `collect_dynamic_libs("primp")` to bundle the Rust `.pyd`.
- `copy_metadata("fast_flights")` if needed for version checks.

### 3. Playwright browsers (fallback backend)
Playwright downloads Chromium/Firefox/WebKit to
`%USERPROFILE%\AppData\Local\ms-playwright\` at install time. These
binaries are **huge (~500 MB per browser)** and are not Python packages.

**Strategy** — two options:
- **Recommended (lean build)**: *Do not bundle Playwright browsers.* The
  project's primary backend is `fast_flights`; Playwright is a fallback that
  rarely fires in practice. Document that advanced users can `pip install
  playwright && playwright install chromium` separately.
- Alternative (fat build): use the `PLAYWRIGHT_BROWSERS_PATH=0` trick to
  install browsers into the package folder, then add that folder to the spec
  `datas` list. Expect the final zip to balloon to ~700 MB.

Decision: **lean build** for Phase 2. Leave a note in `packaging/README.md`.

### 4. SSL certificates (`certifi`)
Both `requests` and `httpx` (via `primp`) need the CA bundle. PyInstaller
usually handles `certifi` automatically, but frozen apps sometimes fail on
Windows if the bundle isn't found on the temp-extract path.

**Strategy**: `collect_data_files("certifi")` in the spec as a safety net.

### 5. SQLite (`database.py`)
`sqlite3` is a stdlib module with a compiled `_sqlite3.pyd` that PyInstaller
bundles automatically. The DB file (`flights.db`) must live **next to the
executable**, not inside the PyInstaller bundle (which is read-only after
extraction).

**Strategy**: `config.DB_PATH` already uses `BASE_DIR = Path(__file__).parent`.
When frozen, `__file__` resolves to the PyInstaller staging dir — but we need
it next to the `.exe` for user persistence.

> **TODO for actual build**: patch `config.py` (or override via env var
> `FLYAWAY_DB_PATH`) before running `pyinstaller`. Simplest: detect
> `getattr(sys, "frozen", False)` in `run_gui.py` and set an env var that
> `config.py` reads. (Deferred — Phase 2 ships the plan only.)

### 6. Holidays package data
The `holidays` library uses year-parameterised data generated at runtime,
no extra data files needed.

### 7. Rich terminal rendering
Not needed in GUI mode, but `reporter.py` still imports `rich`. Keep it —
small footprint.

---

## Entry Point

`run_gui.py` (sibling to `app.py`). It:

1. Locates `app.py` using `sys._MEIPASS` when frozen.
2. Picks a free TCP port (default 8501, fallback random).
3. Starts Streamlit via `streamlit.web.cli.main()`.
4. Opens the default browser after 3 s.

---

## Estimated Output Size

| Component | Approx. size |
|---|---|
| Python runtime | 15 MB |
| Streamlit + deps (tornado, altair, pyarrow, pandas, numpy) | 120 MB |
| fast_flights + primp | 20 MB |
| rich, holidays, requests, python-dateutil | 10 MB |
| SQLite, stdlib | 10 MB |
| **Total (lean, no Playwright)** | **~175 MB** |
| With Playwright Chromium bundled | ~700 MB |

---

## Known Risks & Limitations

1. **First launch is slow** — PyInstaller single-file mode extracts to `%TEMP%`;
   cold-start can take 5–10 s. Prefer `--onedir` for responsiveness.
2. **Streamlit auto-reload hot paths** may look for missing source files; we
   disable via `STREAMLIT_SERVER_HEADLESS=true`.
3. **Antivirus false positives** on PyInstaller outputs are common on Windows.
   Consider code-signing before distribution.
4. **fast_flights API drift**: Google Flights can break overnight. A frozen
   binary can't be patched without a rebuild. Communicate this to end users.
5. **Config secrets**: `.env` / `LINE_NOTIFY_TOKEN` etc. must be loaded from
   the user's working directory, **not** embedded in the bundle.

---

## Build Workflow (Future)

```powershell
# From repo root
pip install -r requirements.txt
pip install pyinstaller==6.7.0
powershell -ExecutionPolicy Bypass -File .\packaging\build.ps1
```

Output goes to `dist/flyaway/` (onedir) — zip that folder and ship.

---

## Open Questions

- Distribute as `--onefile` or `--onedir`? (onedir recommended for startup
  speed and easier diagnosis.)
- Bundle Playwright? (No for v1.)
- Auto-update channel? (Deferred; user downloads each release manually.)
