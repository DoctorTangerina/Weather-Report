"""Public methods for an API or another Python caller; no HTTP dependencies."""

import json
import math
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

from ..time_steps import normalize_time_step, time_step_label
from .models import Bbox, Period
from .selection import SeriesSelectionError, TimeWindow, select_series

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "data/data_gathering/config.json"


def load_series_config(
    config_path: Path = DEFAULT_CONFIG, time_step: str | None = None
) -> dict:
    """The gathering config as a dict, or SeriesSelectionError if unreadable."""
    try:
        configuration = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if not isinstance(configuration, dict):
            raise TypeError
        return configuration
    except (OSError, ValueError, TypeError):
        raise SeriesSelectionError(
            "series_source_unavailable",
            "Configure SERIES_MANIFEST and VARIABLE_RULES in the gathering config.",
        ) from None


def open_source(config_path: Path = DEFAULT_CONFIG):
    from .series_source import NetCDFSeriesSource

    configuration = load_series_config(config_path)
    try:
        manifest = Path(configuration["SERIES_MANIFEST"])
        rules = configuration.get("VARIABLE_RULES", {})
        if not isinstance(rules, dict):
            raise TypeError
    except (KeyError, TypeError):
        raise SeriesSelectionError(
            "series_source_unavailable",
            "Configure SERIES_MANIFEST and VARIABLE_RULES in the gathering config.",
        ) from None
    return NetCDFSeriesSource(
        manifest if manifest.is_absolute() else ROOT / manifest, rules=rules, root=ROOT
    )


def get_time_series(
    area: Bbox | Mapping[str, float],
    variable: str,
    period: Period | Mapping[str, str],
    *,
    dataset_id: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    time_step: str | None = None,
) -> dict:
    """Return a JSON-ready, quality-approved selection or raise SeriesSelectionError.

    area: west/east/south/north in degrees, or a Bbox.
    period: inclusive start/end in YYYY-MM or YYYY-MM-DD, or a Period.
    variable: a native field name (including a layer suffix when necessary).
    dataset_id: optional, required if the field occurs in multiple datasets.
    time_step: optional 3-hourly/daily/monthly declaration for already sampled data;
        validates each requested UTC slot instead of legacy calendar-month coverage.

    No data is downloaded. No failed series values are returned. HTTP response
    formatting and status-code decisions belong to the calling API.
    """
    try:
        box = area if isinstance(area, Bbox) else Bbox(**dict(area))
        selected_period = (
            period if isinstance(period, Period) else Period(**dict(period))
        )
        if (
            not isinstance(variable, str)
            or not variable.strip()
            or not all(
                isinstance(value, str)
                for value in (selected_period.start, selected_period.end)
            )
            or not all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in (box.west, box.east, box.south, box.north)
            )
        ):
            raise ValueError
        if not (
            -180 <= box.west < box.east <= 180 and -90 <= box.south < box.north <= 90
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise SeriesSelectionError(
            "invalid_request",
            "Provide an area with west/east/south/north, a Variable name, and a start/end period.",
        ) from None
    if time_step is not None:
        try:
            frequency = normalize_time_step(time_step)
            if frequency not in ("3-hour", "day", "month"):
                raise ValueError("Select 3-hourly, daily or monthly.")
            time_step = time_step_label(frequency)
        except ValueError as error:
            raise SeriesSelectionError("invalid_time_step", str(error)) from None
    # Reject invalid dates before opening any source file.
    TimeWindow.create(selected_period.start, selected_period.end)
    result = select_series(
        open_source(config_path),
        box,
        variable,
        selected_period,
        dataset_id,
        time_step=time_step,
    )
    payload = asdict(result)
    payload["timestamps"] = list(result.timestamps)
    payload["values"] = list(result.values)
    payload["quality"]["exclusions"] = list(result.quality.exclusions)
    if time_step is not None:
        payload["time_step"] = time_step
        payload["aggregation"] = "mean"
    return payload


def list_available_series(*, config_path: Path = DEFAULT_CONFIG) -> list[dict]:
    """Dataset ids and field metadata for a caller's dataset/Variable selector."""
    return open_source(config_path).available()
