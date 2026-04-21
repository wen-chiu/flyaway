"""
run_gui.py — PyInstaller-friendly launcher for the Streamlit GUI.

Behaviour
---------
1. Pick a free TCP port (fall back to 8501).
2. Start the Streamlit server in a worker thread using its public bootstrap API.
3. Open the user's default browser to the app URL after a short delay.
4. Handle both normal execution and a PyInstaller frozen bundle: when frozen,
   `sys._MEIPASS` holds the extraction root; `app.py` is bundled alongside.

This module is intentionally small so it doubles as the PyInstaller entry
point *and* as a developer-facing "one-click launch" script (works unfrozen).
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _app_path() -> Path:
    """Locate app.py in both frozen (PyInstaller) and source modes."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidate = base / "app.py"
    if not candidate.exists():
        # Fallback: source checkout where run_gui.py sits next to app.py.
        candidate = Path(__file__).resolve().parent / "app.py"
    if not candidate.exists():
        raise FileNotFoundError(f"Cannot locate app.py (looked in {base}).")
    return candidate


def _pick_free_port(preferred: int = 8501) -> int:
    """Return a free TCP port, preferring 8501."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    # Let the OS assign any free port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _open_browser(url: str, delay: float = 3.0) -> None:
    def _worker() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url, new=2)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def main() -> None:
    app = _app_path()
    port = _pick_free_port()

    # Streamlit reads most runtime settings from env vars or CLI args. Using env
    # vars means we don't have to munge sys.argv in a way that breaks tests.
    os.environ.setdefault("STREAMLIT_SERVER_PORT", str(port))
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    _open_browser(f"http://localhost:{port}", delay=3.0)

    # Delegate to Streamlit's CLI (same as `streamlit run app.py`). This is the
    # officially supported programmatic entry point and handles signal/cleanup.
    from streamlit.web import cli as stcli  # type: ignore[import-not-found]

    sys.argv = [
        "streamlit",
        "run",
        str(app),
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
