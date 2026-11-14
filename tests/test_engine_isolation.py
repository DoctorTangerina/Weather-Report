"""The engine package must stay runnable with no web framework installed.

Checked in a subprocess with the web packages blocked at import time, because
the test session itself imports FastAPI to exercise the API.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = """
import importlib
import pkgutil
import sys

BLOCKED = {"fastapi", "starlette", "uvicorn", "pydantic", "pydantic_core", "httpx"}


class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError(name + " is a web dependency; the engine must not need it")
        return None


sys.meta_path.insert(0, Blocker())

import engine

for module in pkgutil.iter_modules(engine.__path__):
    importlib.import_module("engine." + module.name)

print("ok")
"""


def test_engine_imports_with_every_web_dependency_blocked():
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
