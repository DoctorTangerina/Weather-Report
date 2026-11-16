"""Run the whole app with one command: the API on :8000 and the UI on :5173.

    python scripts/run_app.py            # check, then start both; Ctrl+C stops both
    python scripts/run_app.py --check    # only check that everything is in place

The API gets the repository-root `.env` (then `data/data_gathering/.env`) in its
environment, with exported variables taking precedence, so every setting in
`.env.example` can live in `.env`. Open http://localhost:5173 once both are up.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
API_PORT = 8000
UI_PORT = 5173
PYTHON_MODULES = ("fastapi", "uvicorn", "jsonschema", "numpy", "scipy", "netCDF4")

sys.path.insert(0, str(ROOT))
from data.data_gathering.config import settings  # noqa: E402


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def problems() -> tuple[list[str], list[str]]:
    """What stops the app from starting, and what only limits it."""
    errors, warnings = [], []
    missing = [name for name in PYTHON_MODULES if not importlib.util.find_spec(name)]
    if missing:
        errors.append(
            f"Missing Python packages ({', '.join(missing)}): "
            'run `pip install -e ".[api]"` from the repository root.'
        )
    if not shutil.which("npm"):
        errors.append("npm was not found: install Node 18 or newer.")
    if not (FRONTEND / "node_modules").is_dir():
        errors.append("Frontend packages are missing: run `npm install` in frontend/.")
    for port in (API_PORT, UI_PORT):
        if not port_free(port):
            errors.append(f"Port {port} is already in use; stop whatever holds it.")
    try:
        token = settings().get("EARTHDATA_TOKEN", "")
    except ValueError as error:
        errors.append(f".env could not be read: {error}")
        token = ""
    if not token:
        warnings.append(
            "EARTHDATA_TOKEN is not set (see .env.example): the app runs on the "
            "seed set, and live data requests fall back or report unavailable."
        )
    if not importlib.util.find_spec("pyhdf"):
        warnings.append(
            "pyhdf is not installed: live vegetation index (NDVI) cannot be read."
        )
    return errors, warnings


def stop(process: subprocess.Popen) -> None:
    """Stop a server and everything it started (npm leaves Vite behind otherwise)."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only run the checks")
    arguments = parser.parse_args()

    errors, warnings = problems()
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    if errors:
        return 1
    if arguments.check:
        print("Ready: `python scripts/run_app.py` starts the app.")
        return 0

    environment = settings()
    # src/ and the root on the path, so the API runs without an editable install.
    environment["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (str(ROOT / "src"), str(ROOT), environment.get("PYTHONPATH"))
        if part
    )
    environment["PYTHONUNBUFFERED"] = "1"
    group = {} if os.name == "nt" else {"start_new_session": True}
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--port", str(API_PORT)],
        cwd=ROOT,
        env=environment,
        **group,
    )
    ui = subprocess.Popen(
        f"npm run dev -- --port {UI_PORT} --strictPort",
        cwd=FRONTEND,
        shell=True,
        **group,
    )
    print(f"API on http://127.0.0.1:{API_PORT}, UI on http://localhost:{UI_PORT}")
    print("Ctrl+C stops both.")
    try:
        while api.poll() is None and ui.poll() is None:
            time.sleep(0.5)
        failed = "API" if api.poll() is not None else "UI"
        print(f"The {failed} server stopped; stopping the other one.")
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        stop(ui)
        stop(api)


if __name__ == "__main__":
    sys.exit(main())
