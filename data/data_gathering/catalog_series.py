"""One monthly, schema-conformant series for a catalog Region and Variable (DS-001).

The Region catalog supplies the area, the Variable catalog supplies the field,
units and land-only flag, and the gathering config says which acquired dataset
holds a Variable. Each native time step's cells are converted to catalog units
and combined with the requested Aggregation (area-weighted mean by default),
then each calendar month's values are combined with the same Aggregation (spec
#72), and the quality gate (BS-003) decides whether the series may be used.

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
from pathlib import Path

import numpy as np

from .aggregation import AGGREGATIONS, combine
from .models import Bbox, Period
from .quality_gate import assess_quality, months_in
from .selection import SeriesSelectionError, TimeWindow
from .series import DEFAULT_CONFIG, ROOT, load_series_config, open_source

DEFAULT_CATALOG = ROOT / "data/catalog.json"
DEFAULT_PERIOD = Period("2000-01", "2024-12")

# A conversion turns grid-cell values in the file's units into catalog units.
# It gets one native time step's cells (a masked array, missing cells masked)
# and that step's month (YYYY-MM). Converting cells before they are combined
# keeps Aggregations such as root mean square right for offset units (K to °C).
Conversion = Callable[[np.ndarray, str], np.ndarray]


def _rate_to_monthly_total(cells, month):
    """MERRA-2's mean rate (kg m-2 s-1) to mm per month: 1 kg m-2 is 1 mm deep.

    Each value is multiplied by the seconds in its own month (28 to 31 days).
    """
    from engine.units import seconds_in_month

    return cells * seconds_in_month(int(month[:4]), int(month[5:]))


def _check_monthly_precipitation(values, months):
    """Refuse totals that cannot be precipitation, so they never pass as data."""
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


CONVERSIONS: dict[str, Conversion] = {
    "identity": lambda cells, month: cells,
    "kelvin_to_celsius": lambda cells, month: cells - 273.15,
    "rate_per_second_to_per_month": _rate_to_monthly_total,
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
) -> dict:
    """The monthly series for a catalog Region and Variable, with its quality.

    period: inclusive start/end in YYYY-MM. Default 2000-01 to 2024-12.
    aggregation: one of `aggregation.AGGREGATIONS`; it combines the Region's
    cells (area-weighted, except minimum and maximum), then each month's values.
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
) -> dict:
    """`get_catalog_series` for several Regions of one Variable, reading each file once.

    Each Region's value is its series, or the SeriesSelectionError that
    `get_catalog_series` would have raised for it. A problem with the Variable,
    the period or the data as a whole is raised, as it would be for one Region.
    `on_file(done, total, path)` is called after each file is read.
    """
    if aggregation not in AGGREGATIONS:
        raise SeriesSelectionError(
            "invalid_aggregation",
            "Choose an Aggregation from " + ", ".join(AGGREGATIONS) + ".",
        )
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
    conversions: dict[str, Conversion] = {}

    def convert_cells(cells, timestamp, units):
        if units not in conversions:
            conversions[units] = _conversion(entry, units, variable["units"])
        return conversions[units](cells, timestamp[:7])

    natives = open_source(config_path).select_many(
        {region_id: Bbox(**region["bbox"]) for region_id, region in regions.items()},
        field,
        window,
        entry.get("dataset_id"),
        on_file,
        aggregation=aggregation,
        cell_conversion=convert_cells,
    )

    for region_id, native in natives.items():
        try:
            if isinstance(native, SeriesSelectionError):
                raise native
            results[region_id] = _series(
                region_id,
                variable,
                native,
                entry,
                selected,
                window,
                months,
                catalog["engine_version"],
                aggregation,
            )
        except SeriesSelectionError as error:
            results[region_id] = error
    return {region_id: results[region_id] for region_id in region_ids}


def _series(
    region_id,
    variable,
    native,
    entry,
    selected,
    window,
    months,
    engine_version,
    aggregation="mean",
) -> dict:
    land_only = bool(variable["land_only"] or native.land_only)
    if variable["land_only"] and not native.land_only:
        raise SeriesSelectionError(
            "land_mask_unavailable",
            "This land-only Variable has no configured land mask in the acquired data.",
        )
    # The cells are already in catalog units (see `convert_cells`).
    buckets: dict[str, list[float]] = {}
    for stamp, value in native.observations.items():
        if window.contains(stamp) and value is not None and math.isfinite(value):
            buckets.setdefault(stamp[:7], []).append(value)
    monthly = [_month_value(buckets.get(month), aggregation) for month in months]
    check = PLAUSIBILITY.get(entry.get("conversion", "identity"))
    if check is not None:
        check(monthly, months)

    try:
        quality = assess_quality(
            monthly, land_only=land_only, valid_land_fraction=native.valid_land_fraction
        )
    except ValueError:
        raise SeriesSelectionError(
            "land_mask_unavailable",
            "This Variable requires verified land-mask metadata before its series can be returned.",
        ) from None
    return {
        "region_id": region_id,
        "variable_id": variable["variable_id"],
        "period": {"start": selected.start, "end": selected.end},
        "units": variable["units"],
        "values": monthly if quality.included else [None] * len(monthly),
        "quality": {**asdict(quality), "exclusions": list(quality.exclusions)},
        "source": dict(variable["source"]),
        "engine_version": engine_version,
    }


def _month_value(values: list[float] | None, aggregation: str) -> float | None:
    """A month's value from its native time steps' values (spec #72).

    Values are combined over time only when the month holds several native time
    steps. One value is the month's value as it is: combining a single value
    would turn a standard deviation into 0.
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
