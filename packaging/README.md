# Packaging Flyaway with PyInstaller

This folder contains everything needed to build a standalone Windows
executable of the Flyaway GUI. **Nothing in here has been executed yet** —
Phase 2 delivers the configuration only.

---

## Prerequisites

- Windows 10 / 11 (x64)
- Python 3.11 or newer
- `pip install -r ../requirements.txt`
- `pip install pyinstaller==6.7.0`

---

## Build

From the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build.ps1
```

This will:

1. Clean `build/` and `dist/`.
2. Install PyInstaller if missing.
3. Run `pyinstaller packaging/build.spec`.
4. Copy `README.md` and `LICENSE` into `dist/flyaway/`.

Output: **`dist/flyaway/flyaway.exe`** plus a directory of supporting files.
Zip the whole `dist/flyaway/` folder for distribution.

---

## Test Before Shipping

```powershell
cd dist\flyaway
.\flyaway.exe
```

Expected: a browser window opens at `http://localhost:8501` showing the
Flyaway Streamlit app within ~10 seconds.

Quick smoke-test checklist:

- [ ] App launches; sidebar shows three pages
- [ ] Search `TPE → NRT` returns results
- [ ] CSV download works
- [ ] Booking link opens Google Flights in browser
- [ ] Close window; `flyaway.exe` process terminates cleanly

---

## Known Issues

### Playwright is not bundled
The `fast_flights` backend is the primary scraper and does **not** need
Playwright. The Playwright fallback path in `flight_scraper.py` will raise
on a frozen build; you'll see a warning in the log but searches still work.

If you need Playwright in the bundle, see the "fat build" section in
[`PLAN.md`](./PLAN.md).

### `flights.db` location
When running the frozen build, the SQLite file is created next to
`flyaway.exe`. Delete it to reset history.

### First launch is slow
PyInstaller's onedir bundle needs to load ~175 MB into the OS page cache.
Subsequent launches are near-instant.

### Antivirus false positives
PyInstaller outputs frequently trip Windows Defender / SmartScreen. For
public distribution, code-sign the `.exe` with a trusted certificate.

---

## FAQ

**Q: Can I use `--onefile`?**
Edit `build.spec` and replace the `COLLECT` block with a single-file `EXE`
call. Note the cold-start will be 2–3× slower.

**Q: Can I cross-build for macOS / Linux?**
No — PyInstaller bundles the host Python runtime. Run `build.ps1`'s
equivalent on each target OS.

**Q: Where do notification tokens live?**
Not in the bundle. The app reads env vars / `.env` from the current working
directory. Ship a `.env.example` next to `flyaway.exe`.
