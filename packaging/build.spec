# -*- mode: python ; coding: utf-8 -*-
"""
build.spec — PyInstaller spec for flyaway (DRAFT, not executed yet).

Run from repo root:  pyinstaller packaging/build.spec

Output: dist/flyaway/  (onedir build — recommended for faster cold-start)
"""
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

# ── Repo layout ──────────────────────────────────────────────────────────────
ROOT = Path(SPECPATH).parent          # noqa: F821 - SPECPATH injected by PyInstaller
ENTRY = str(ROOT / "run_gui.py")
APP_PY = str(ROOT / "app.py")

# ── Collect Streamlit (lots of runtime data: static assets, config schema) ──
st_datas, st_binaries, st_hidden = collect_all("streamlit")
st_datas += copy_metadata("streamlit")

# ── Collect fast_flights (protobuf-generated modules + primp Rust .pyd) ─────
ff_datas, ff_binaries, ff_hidden = collect_all("fast_flights")
primp_binaries = collect_dynamic_libs("primp")

# ── Certifi CA bundle (belt-and-braces for SSL under PyInstaller) ───────────
cert_datas = collect_data_files("certifi")

# ── App-level data: app.py and the ui/ package must travel with the bundle.
#    All other project modules (config.py, flight_scraper.py, …) are picked up
#    as hidden imports because run_gui.py → app.py → ui.* imports them.
app_datas = [
    (APP_PY, "."),
    (str(ROOT / "ui"), "ui"),
]

# ── Hidden imports: project modules that get imported indirectly ────────────
project_hidden = [
    "config", "database", "flight_scraper", "booking_links",
    "airline_classifier", "taiwan_holidays", "vacation_windows",
    "reporter", "notifier", "scheduler",
    "ui", "ui.components", "ui.search_view",
    "ui.vacation_view", "ui.holidays_view",
]

hidden = (
    st_hidden
    + ff_hidden
    + project_hidden
    + collect_submodules("holidays")
    + collect_submodules("rich")
)

a = Analysis(
    [ENTRY],
    pathex=[str(ROOT)],
    binaries=st_binaries + ff_binaries + primp_binaries,
    datas=st_datas + ff_datas + cert_datas + app_datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Keep bundle lean: we don't ship Playwright browsers in v1.
        # The Python package itself stays — only binaries excluded.
        "matplotlib", "tkinter", "PIL.ImageQt",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="flyaway",
    console=False,              # --windowed: no terminal window on Windows
    icon=None,                  # TODO: add packaging/flyaway.ico once designed
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,                  # UPX often triggers AV false-positives
    name="flyaway",
)
