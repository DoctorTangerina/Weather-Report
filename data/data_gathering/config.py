"""Public gathering configuration and separate local credential settings."""

import json
import os
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config(path: Path = CONFIG_PATH) -> dict:
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise TypeError("Gathering config must be a JSON object.")
    return values


def settings(env_path: Path = ENV_PATH) -> dict[str, str]:
    """Read credentials; exported environment variables override .env."""
    values = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.strip().removeprefix("export ").partition("=")
            if not separator or key.startswith("#"):
                continue
            parts = shlex.split(value, comments=True)
            if len(parts) > 1:
                raise ValueError(f"Quote values containing spaces in .env ({key.strip()}).")
            values[key.strip()] = parts[0] if parts else ""
    return {**values, **os.environ}


def configured_bbox() -> tuple[float, float, float, float]:
    value = load_config().get("BBOX", [])
    try:
        if not isinstance(value, list):
            raise TypeError
        bounds = tuple(float(part) for part in value)
    except (ValueError, TypeError):
        raise ValueError("Set BBOX to [WEST,SOUTH,EAST,NORTH] in config.json, or pass --bbox.") from None
    if len(bounds) != 4:
        raise ValueError("BBOX must contain WEST,SOUTH,EAST,NORTH.")
    return bounds


def configured_path(key: str, default: Path) -> Path:
    path = Path(load_config().get(key) or default)
    return path if path.is_absolute() else ROOT / path
