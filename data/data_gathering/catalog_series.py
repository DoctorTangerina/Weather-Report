"""One schema-conformant series for a catalog Region and Variable (DS-001).

The Region catalog supplies the area, the Variable catalog supplies the field,
units and land-only flag, and the gathering config says which acquired dataset
holds a Variable. Each native time step's cells are converted to catalog units
and combined with the requested Aggregation (area-weighted mean by default),
then each Time step's values (a calendar month by default, or a UTC day or
3-hour interval) are combined with the same Aggregation (spec #72), and the
quality gate (BS-003, BS-010) decides whether the series may be used.

The result is a plain dict in the shape of `schemas/series.schema.json`. It
carries no engine import, so the engine can read it with `Series.from_dict`.
A series that fails the gate is returned with `quality.included` false and its
values withheld, so no Discovery can rest on them.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from ..time_steps import utc_instant
from .aggregation import AGGREGATIONS, combine
from .models import Bbox, Period, SelectedArea
from .quality_gate import assess_quality, months_in
from .selection import SeriesSelectionError, TimeWindow
from .series import DEFAULT_CONFIG, ROOT, load_series_config, open_source

DEFAULT_CATALOG = ROOT / "data/catalog.json"
DEFAULT_PERIOD = Period("2000-01", "2024-12")
# Spec #72's Time steps. Days and 3-hour intervals follow UTC.
TIME_STEPS = ("3-hourly", "daily", "monthly")
_STEP_SECONDS = {"daily": 86400, "3-hourly": 10800}
_STEP_UNITS = {"daily": "/day", "3-hourly": "/3h"}

# A conversion turns grid-cell values in the file's units into catalog units.
# It gets one native time step's cells (a masked array, missing cells masked),
# that step's timestamp and the requested Time step. Converting cells before
# they are combined keeps Aggregations such as root mean square right for
# offset units (K to °C).
Conversion = Callable[[np.ndarray, str, str], np.ndarray]


def _rate_to_total(cells, timestamp, time_step):
    """MERRA-2's mean rate (kg m-2 s-1) to the total that falls in a Time step.

    1 kg m-2 is 1 mm deep. Each value is multiplied by the seconds in its Time
    step: its own month (28 to 31 days), a day, or 3 hours (spec #72, Q25). The
    Time step's values are then combined, so their mean is the total that fell.
    """
    from engine.units import seconds_in_month

    seconds = _STEP_SECONDS.get(time_step)
    if seconds is None:
        seconds = seconds_in_month(int(timestamp[:4]), int(timestamp[5:7]))
    return cells * seconds


def _check_monthly_precipitation(values, months):
    """Refuse totals that cannot be precipitation, so they never pass as data.

    No Time step can hold more than the wettest month ever recorded.
    """
    from engine.units import MONTHLY_PRECIPITATION_CEILING

    for value, month in zip(values, months):
        if value is None:
            continue
        if value < 0:
            raise SeriesSelectionError(
                "implausible_values", f"negative precipitation in {month}"
            )
        if value > MONTHLY_PRECIPITATION_CEILING:
            raise SeriesSelectionError(
                "implausible_values",
                f"{value:.0f} mm in {month} is wetter than any month ever recorded; "
                "the input is probably not a rate in kg m-2 s-1",
            )


# "rate_per_second_to_per_month" keeps the name the gathering configs use; it
# gives the total per Time step, which is per month for monthly Series.
CONVERSIONS: dict[str, Conversion] = {
    "identity": lambda cells, timestamp, time_step: cells,
    "kelvin_to_celsius": lambda cells, timestamp, time_step: cells - 273.15,
    "rate_per_second_to_per_month": _rate_to_total,
}
# Checks on the finished values, for conversions that can expose bad input.
PLAUSIBILITY = {"rate_per_second_to_per_month": _check_monthly_precipitation}


def get_catalog_series(
    region_id: str,
    variable_id: str,
    period: Period | Mapping[str, str] = DEFAULT_PERIOD,
    *,
    catalog_path: Path = DEFAULT_CATALOG,
    config_path: Path = DEFAULT_CONFIG,
    aggregation: str = "mean",
    withhold_excluded: bool = True,
    time_step: str = "monthly",
) -> dict:
    """The series for a catalog Region and Variable, with its quality.

    period: inclusive start/end in YYYY-MM. Default 2000-01 to 2024-12.
    aggregation: one of `aggregation.AGGREGATIONS`; it combines the Region's
    cells (area-weighted, except minimum and maximum), then each Time step's.
    time_step: one of TIME_STEPS. The series holds one value per Time step from
    the start of `period`, days and 3-hour intervals in UTC.
    withhold_excluded: False keeps the values of a series the gate excluded,
    for a caller that joins it to other months and gates the whole again.
    Raises SeriesSelectionError if the ids are not in the catalogs, the Variable
    is not offered for the Region, the data is not acquired, a land-only Variable
    has no land mask, or the file's units cannot be reported in catalog units.
    A series that is merely too incomplete is returned, flagged as excluded.
    """
    result = get_catalog_series_many(
        [region_id],
        variable_id,
        period,
        catalog_path=catalog_path,
        config_path=config_path,
        aggregation=aggregation,
        withhold_excluded=withhold_excluded,
        time_step=time_step,
    )[region_id]
    if isinstance(result, SeriesSelectionError):
        raise result
    return result


def get_catalog_series_many(
    region_ids: list[str],
    variable_id: str,
    period: Period | Mapping[str, str] = DEFAULT_PERIOD,
    *,
    catalog_path: Path = DEFAULT_CATALOG,
    config_path: Path = DEFAULT_CONFIG,
    on_file=None,
    aggregation: str = "mean",
    withhold_excluded: bool = True,
    time_step: str = "monthly",
) -> dict:
    """`get_catalog_series` for several Regions of one Variable, reading each file once.

    Each Region's value is its series, or the SeriesSelectionError that
    `get_catalog_series` would have raised for it. A problem with the Variable,
    the period or the data as a whole is raised, as it would be for one Region.
    `on_file(done, total, path)` is called after each file is read.
    """
    _check_aggregation(aggregation)
    _check_time_step(time_step)
    catalog = _load_catalog(catalog_path)
    variable = _find(catalog["variables"], "variable_id", variable_id)
    if variable is None:
        raise SeriesSelectionError(
            "not_in_catalog", "Choose a Region and a Variable from the catalogs."
        )
    results: dict = {}
    regions = {}
    for region_id in region_ids:
        region = _find(catalog["regions"], "region_id", region_id)
        if region is None:
            results[region_id] = SeriesSelectionError(
                "not_in_catalog", "Choose a Region and a Variable from the catalogs."
            )
        elif variable_id not in region["variable_ids"]:
            results[region_id] = SeriesSelectionError(
                "variable_not_offered_for_region",
                "The catalog does not offer this Variable for this Region.",
            )
        else:
            regions[region_id] = region
    if not regions:
        return results
    selected = period if isinstance(period, Period) else _period(period)
    months = _months(selected)

    configuration = load_series_config(config_path)
    entry = (configuration.get("CATALOG_SERIES") or {}).get(variable_id, {})
    field = entry.get("variable", variable["source"]["variable"])
    window = TimeWindow.create(selected.start, selected.end)
    natives = open_source(config_path).select_many(
        {region_id: Bbox(**region["bbox"]) for region_id, region in regions.items()},
        field,
        window,
        entry.get("dataset_id"),
        on_file,
        aggregation=aggregation,
        cell_conversion=_cell_conversion(entry, variable["units"], time_step),
    )

    for region_id, native in natives.items():
        try:
            if isinstance(native, SeriesSelectionError):
                raise native
            results[region_id] = _series(
                {"region_id": region_id},
                variable,
                native,
                entry,
                selected,
                window,
                months,
                catalog["engine_version"],
                aggregation,
                withhold_excluded,
                time_step,
            )
        except SeriesSelectionError as error:
            results[region_id] = error
    return {region_id: results[region_id] for region_id in region_ids}


def get_area_series(
    rectangles: list[tuple[float, float, float, float]],
    variable_id: str,
    period: Period | Mapping[str, str],
    *,
    catalog_path: Path = DEFAULT_CATALOG,
    config_path: Path = DEFAULT_CONFIG,
    aggregation: str = "mean",
    withhold_excluded: bool = True,
    time_step: str = "monthly",
) -> dict:
    """The Series for a Selected area, built like a catalog Region's.

    The area replaces the Region: `area` stands where `region_id` would, so the
    result can never be mistaken for a Region's Series. `aggregation`,
    `withhold_excluded` and `time_step` mean what they do for
    `get_catalog_series`.
    """
    _check_aggregation(aggregation)
    _check_time_step(time_step)
    catalog = _load_catalog(catalog_path)
    variable = _find(catalog["variables"], "variable_id", variable_id)
    if variable is None:
        raise SeriesSelectionError(
            "not_in_catalog", "Choose a Variable from the catalog."
        )
    selected = period if isinstance(period, Period) else _period(period)
    configuration = load_series_config(config_path)
    entry = (configuration.get("CATALOG_SERIES") or {}).get(variable_id, {})
    window = TimeWindow.create(selected.start, selected.end)
    area = SelectedArea(tuple(tuple(box) for box in rectangles))
    native = open_source(config_path).select_many(
        {"area": area},
        entry.get("variable", variable["source"]["variable"]),
        window,
        entry.get("dataset_id"),
        aggregation=aggregation,
        cell_conversion=_cell_conversion(entry, variable["units"], time_step),
    )["area"]
    if isinstance(native, SeriesSelectionError):
        raise native
    return _series(
        {"area": {"rectangles": [list(box) for box in rectangles]}},
        variable,
        native,
        entry,
        selected,
        window,
        _months(selected),
        catalog["engine_version"],
        aggregation,
        withhold_excluded,
        time_step,
    )


def _check_time_step(time_step: str) -> None:
    if time_step not in TIME_STEPS:
        raise SeriesSelectionError(
            "invalid_time_step",
            "Choose a Time step from " + ", ".join(TIME_STEPS) + ".",
        )


def _check_aggregation(aggregation: str) -> None:
    if aggregation not in AGGREGATIONS:
        raise SeriesSelectionError(
            "invalid_aggregation",
            "Choose an Aggregation from " + ", ".join(AGGREGATIONS) + ".",
        )


def _cell_conversion(entry: dict, catalog_units: str, time_step: str = "monthly"):
    """Convert one native time step's cells to catalog units, by the file's units."""
    conversions: dict[str, Conversion] = {}

    def convert_cells(cells, timestamp, units):
        if units not in conversions:
            conversions[units] = _conversion(entry, units, catalog_units)
        return conversions[units](cells, timestamp, time_step)

    return convert_cells


def _step_key(stamp: str, time_step: str) -> str:
    """The Time step a native timestamp falls in: its month, UTC day or 3 hours."""
    if time_step == "monthly":
        return stamp[:7]
    instant = utc_instant(stamp)
    if time_step == "daily":
        return instant.strftime("%Y-%m-%d")
    return instant.replace(hour=instant.hour // 3 * 3).strftime("%Y-%m-%dT%H")


def _steps(months: tuple[str, ...], time_step: str) -> list[str]:
    """Every Time step in whole `months`, in order, keyed as `_step_key` keys them."""
    if time_step == "monthly":
        return list(months)
    cursor = datetime.strptime(months[0], "%Y-%m")
    year, month = map(int, months[-1].split("-"))
    end = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1)
    step, pattern = (
        (timedelta(days=1), "%Y-%m-%d")
        if time_step == "daily"
        else (timedelta(hours=3), "%Y-%m-%dT%H")
    )
    steps = []
    while cursor < end:
        steps.append(cursor.strftime(pattern))
        cursor += step
    return steps


def units_at(units: str, time_step: str) -> str:
    """Catalog units for a Time step: a total per month becomes per day or per 3h."""
    if time_step in _STEP_UNITS and units.endswith("/month"):
        return units.removesuffix("/month") + _STEP_UNITS[time_step]
    return units


def _series(
    identity,
    variable,
    native,
    entry,
    selected,
    window,
    months,
    engine_version,
    aggregation="mean",
    withhold_excluded=True,
    time_step="monthly",
) -> dict:
    land_only = bool(variable["land_only"] or native.land_only)
    if variable["land_only"] and not native.land_only:
        raise SeriesSelectionError(
            "land_mask_unavailable",
            "This land-only Variable has no configured land mask in the acquired data.",
        )
    # The cells are already in catalog units (see `_cell_conversion`).
    buckets: dict[str, list[float]] = {}
    for stamp, value in native.observations.items():
        if window.contains(stamp) and value is not None and math.isfinite(value):
            buckets.setdefault(_step_key(stamp, time_step), []).append(value)
    steps = _steps(months, time_step)
    values = [_step_value(buckets.get(step), aggregation) for step in steps]
    check = PLAUSIBILITY.get(entry.get("conversion", "identity"))
    if check is not None:
        check(values, steps)

    try:
        quality = assess_quality(
            values,
            land_only=land_only,
            valid_land_fraction=native.valid_land_fraction,
            # Monthly Series keep the reason the seed set and Discoveries use.
            time_step=None if time_step == "monthly" else time_step,
        )
    except ValueError:
        raise SeriesSelectionError(
            "land_mask_unavailable",
            "This Variable requires verified land-mask metadata before its series can be returned.",
        ) from None
    return {
        **identity,
        "variable_id": variable["variable_id"],
        "period": {"start": selected.start, "end": selected.end},
        "units": units_at(variable["units"], time_step),
        "values": values
        if quality.included or not withhold_excluded
        else [None] * len(values),
        "quality": {**asdict(quality), "exclusions": list(quality.exclusions)},
        "source": dict(variable["source"]),
        "engine_version": engine_version,
    }


def _step_value(values: list[float] | None, aggregation: str) -> float | None:
    """A Time step's value from its native time steps' values (spec #72).

    Values are combined over time only when the Time step holds several native
    time steps. One value is the Time step's value as it is: combining a single
    value would turn a standard deviation into 0.
    """
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return combine(values, aggregation=aggregation)


def _load_catalog(path: Path) -> dict:
    try:
        catalog = json.loads(Path(path).read_text(encoding="utf-8"))
        catalog["regions"], catalog["variables"], catalog["engine_version"]
        return catalog
    except (OSError, ValueError, KeyError, TypeError):
        raise SeriesSelectionError(
            "catalog_unavailable", "The Region and Variable catalogs cannot be read."
        ) from None


def _find(entries: list[dict], key: str, identifier: str) -> dict | None:
    return next((entry for entry in entries if entry[key] == identifier), None)


def _period(value: Mapping[str, str]) -> Period:
    try:
        return Period(value["start"], value["end"])
    except (KeyError, TypeError):
        raise SeriesSelectionError(
            "invalid_period", "Give a period with start and end months in YYYY-MM."
        ) from None


def _months(period: Period) -> tuple[str, ...]:
    try:
        return months_in(period)
    except (ValueError, TypeError):
        raise SeriesSelectionError(
            "invalid_period",
            "Use whole months in YYYY-MM, with start no later than end.",
        ) from None


def _conversion(entry: dict, native_units: str, catalog_units: str) -> Conversion:
    """Pick how the file's units become catalog units, or refuse.

    A conversion runs only when the config names the units it expects and the
    file really has them. Without a declaration the units must already match.
    """
    name = entry.get("conversion", "identity")
    if name not in CONVERSIONS:
        raise SeriesSelectionError(
            "series_source_unavailable",
            f"Unknown unit conversion {name!r} in the gathering config.",
        )
    declared = entry.get("native_units")
    if declared is None:
        if name != "identity" or _units(native_units) != _units(catalog_units):
            raise SeriesSelectionError(
                "units_mismatch",
                f"The data is in {native_units!r}, not the catalog's {catalog_units!r}; declare native_units and a conversion.",
            )
    elif _units(declared) != _units(native_units):
        raise SeriesSelectionError(
            "units_mismatch",
            f"The config declares {declared!r} but the data is in {native_units!r}.",
        )
    return CONVERSIONS[name]


def _units(text: str) -> object:
    """A comparable form of a unit string: 'kg m-2' equals 'kg/m²'."""
    exponents: dict[str, int] = {}
    numerator, _, denominator = text.lower().replace("²", "2").partition("/")
    for part, sign in ((numerator, 1), (denominator, -1)):
        for token in part.split():
            match = re.fullmatch(r"([a-z]+)(-?\d+)?", token)
            if match is None:
                return text.lower().strip()
            name, power = match.group(1), int(match.group(2) or 1)
            exponents[name] = exponents.get(name, 0) + sign * power
    return {name: power for name, power in exponents.items() if power}


def build_series_files(
    region_ids: list[str],
    variable_ids: list[str],
    period: Period | Mapping[str, str],
    output_dir: Path,
    *,
    catalog_path: Path = DEFAULT_CATALOG,
    config_path: Path = DEFAULT_CONFIG,
    progress: Callable[[str], None] | None = None,
    aggregation: str = "mean",
) -> list[dict]:
    """Write one series file per Region and Variable and report each outcome.

    Every series is built with `aggregation` (see `get_catalog_series`).

    Files are named `<region>__<variable>.json`, like the committed stub set.
    A series the data cannot provide is reported and skipped, not fatal. Each
    Variable's files are read once for all its Regions. `progress`, if given, is
    called with a line of text as each file is read and as each series is
    finished. The report is ordered by Region, then Variable.
    """
    output_dir = Path(output_dir)
    say = progress or (lambda text: None)
    rows: dict[tuple[str, str], dict] = {}
    for variable_id in variable_ids:
        say(f"{variable_id}: reading the files for {len(region_ids)} Regions")
        try:
            results = get_catalog_series_many(
                region_ids,
                variable_id,
                period,
                catalog_path=catalog_path,
                config_path=config_path,
                aggregation=aggregation,
                on_file=lambda done, total, path, v=variable_id: (
                    say(f"{v}: file {done}/{total}")
                    if done in (1, total) or done % 25 == 0
                    else None
                ),
            )
        except SeriesSelectionError as error:
            results = dict.fromkeys(region_ids, error)
        for region_id in region_ids:
            row = {"region_id": region_id, "variable_id": variable_id}
            result = results[region_id]
            if isinstance(result, SeriesSelectionError):
                row["status"] = result.code
            else:
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / f"{region_id}__{variable_id}.json").write_text(
                    json.dumps(result, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
                quality = result["quality"]
                row.update(
                    status="included"
                    if quality["included"]
                    else "excluded: " + ", ".join(quality["exclusions"]),
                    missing_fraction=quality["missing_fraction"],
                    valid_land_fraction=quality["valid_land_fraction"],
                )
            rows[region_id, variable_id] = row
            say(f"{region_id} {variable_id}: {row['status']}")
    return [
        rows[region_id, variable_id]
        for region_id in region_ids
        for variable_id in variable_ids
    ]
