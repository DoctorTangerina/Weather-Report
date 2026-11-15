from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
SCHEMA_BASE = "https://weather-report.local/schemas/"

# The API serves the committed seed set by default. Its contract tests assert on
# the stub fixtures (which Regions have no result, which Candidates may headline),
# so they are pinned to the stub before `api.main` is first imported.
os.environ.setdefault("WEATHER_REPORT_DATA_DIR", str(ROOT / "data" / "stub"))


@pytest.fixture(scope="session")
def registry() -> Registry:
    """Every schema in `schemas/`, keyed by $id so cross-file $refs resolve."""
    resources = []
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


@pytest.fixture(scope="session")
def validator_for(registry: Registry) -> Callable[..., Draft202012Validator]:
    """Build a validator for one schema, or for a $def inside it."""

    def build(schema_file: str, pointer: str = "") -> Draft202012Validator:
        return Draft202012Validator(
            {"$ref": f"{SCHEMA_BASE}{schema_file}{pointer}"},
            registry=registry,
        )

    return build


@pytest.fixture(scope="session")
def schema_paths() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("*.schema.json"))


@pytest.fixture(scope="session")
def stub_dir() -> Path:
    return ROOT / "data" / "stub"


@pytest.fixture(scope="session")
def catalog_path() -> Path:
    return ROOT / "data" / "catalog.json"
