"""One monthly, schema-conformant series for a catalog Region and Variable (DS-001).

The Region catalog supplies the area, the Variable catalog supplies the field,
units and land-only flag, and the gathering config says which acquired dataset
holds a Variable. Native observations are reduced to one mean per calendar
month, then the quality gate (BS-003) decides whether the series may be used.

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

from .models import Bbox, Period
from .quality_gate import assess_quality, months_in
from .selection import SeriesSelectionError, TimeWindow
from .series import DEFAULT_CONFIG, ROOT, load_series_config, open_source

DEFAULT_CATALOG = ROOT / "data/catalog.json"
DEFAULT_PERIOD = Period("2000-01", "2024-12")

# A conversion turns the monthly means in the file's units into catalog units.
# It gets the values, the first month (YYYY-MM) and the file's units, and keeps
# missing months missing.
Conversion = Callable[[list[float | None], str, str], list[float | None]]


def _kelvin_to_celsius(values, start, units):
    return [None if value is None else value - 273.15 for value in values]


def _rate_to_monthly_total(values, start, units):
    """MERRA-2's mean rate (kg m-2 s-1) to mm per month, by the engine's own helper.

    The helper multiplies each month by its own length and refuses anything that
    cannot be a precipitation rate, so a wrong value never passes as a total.
    """
    from engine import precipitation_rate_to_monthly_total

    try:
        return precipitation_rate_to_monthly_total(values, start, units)
    except ValueError as error:
        raise SeriesSelectionError("implausible_values", str(error)) from None


CONVERSIONS: dict[str, Conversion] = {
    "identity": lambda values, start, units: values,
    "kelvin_to_celsius": _kelvin_to_celsius,
    "rate_per_second_to_per_month": _rate_to_monthly_total,
}


def get_catalog_series(region_id: str, variable_id: str,
                       period: Period | Mapping[str, str] = DEFAULT_PERIOD, *,
                       catalog_path: Path = DEFAULT_CATALOG,
                       config_path: Path = DEFAULT_CONFIG) -> dict:
    """The monthly series for a catalog Region and Variable, with its quality.

    period: inclusive start/end in YYYY-MM. Default 2000-01 to 2024-12.
    Raises SeriesSelectionError if the ids are not in the catalogs, the Variable
    is not offered for the Region, the data is not acquired, a land-only Variable
    has no land mask, or the file's units cannot be reported in catalog units.
    A series that is merely too incomplete is returned, flagged as excluded.
    """
    result = get_catalog_series_many([region_id], variable_id, period,
                                     catalog_path=catalog_path, config_path=config_path)[region_id]
    if isinstance(result, SeriesSelectionError):
        raise result
    return result


def get_catalog_series_many(region_ids: list[str], variable_id: str,
                            period: Period | Mapping[str, str] = DEFAULT_PERIOD, *,
                            catalog_path: Path = DEFAULT_CATALOG,
                            config_path: Path = DEFAULT_CONFIG, on_file=None) -> dict:
    """`get_catalog_series` for several Regions of one Variable, reading each file once.

    Each Region's value is its series, or the SeriesSelectionError that
    `get_catalog_series` would have raised for it. A problem with the Variable,
    the period or the data as a whole is raised, as it would be for one Region.
    `on_file(done, total, path)` is called after each file is read.
    """
    catalog = _load_catalog(catalog_path)
    variable = _find(catalog["variables"], "variable_id", variable_id)
    if variable is None:
        raise SeriesSelectionError("not_in_catalog", "Choose a Region and a Variable from the catalogs.")
    results: dict = {}
    regions = {}
    for region_id in region_ids:
        region = _find(catalog["regions"], "region_id", region_id)
        if region is None:
            results[region_id] = SeriesSelectionError("not_in_catalog", "Choose a Region and a Variable from the catalogs.")
        elif variable_id not in region["variable_ids"]:
            results[region_id] = SeriesSelectionError("variable_not_offered_for_region", "The catalog does not offer this Variable for this Region.")
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
        field, window, entry.get("dataset_id"), on_file)

    for region_id, native in natives.items():
        try:
            if isinstance(native, SeriesSelectionError):
                raise native
            results[region_id] = _series(region_id, variable, native, entry, selected, window,
                                         months, catalog["engine_version"])
        except SeriesSelectionError as error:
            results[region_id] = error
    return {region_id: results[region_id] for region_id in region_ids}


def _series(region_id, variable, native, entry, selected, window, months, engine_version) -> dict:
    land_only = bool(variable["land_only"] or native.land_only)
    if variable["land_only"] and not native.land_only:
        raise SeriesSelectionError("land_mask_unavailable", "This land-only Variable has no configured land mask in the acquired data.")
    convert = _conversion(entry, native.units, variable["units"])

    buckets: dict[str, list[float]] = {}
    for stamp, value in native.observations.items():
        if window.contains(stamp) and value is not None and math.isfinite(value):
            buckets.setdefault(stamp[:7], []).append(value)
    monthly = [sum(buckets[month]) / len(buckets[month]) if month in buckets else None
               for month in months]
    monthly = convert(monthly, selected.start, native.units)

    try:
        quality = assess_quality(monthly, land_only=land_only,
                                 valid_land_fraction=native.valid_land_fraction)
    except ValueError:
        raise SeriesSelectionError("land_mask_unavailable", "This Variable requires verified land-mask metadata before its series can be returned.") from None
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


def _load_catalog(path: Path) -> dict:
    try:
        catalog = json.loads(Path(path).read_text(encoding="utf-8"))
        catalog["regions"], catalog["variables"], catalog["engine_version"]
        return catalog
    except (OSError, ValueError, KeyError, TypeError):
        raise SeriesSelectionError("catalog_unavailable", "The Region and Variable catalogs cannot be read.") from None


def _find(entries: list[dict], key: str, identifier: str) -> dict | None:
    return next((entry for entry in entries if entry[key] == identifier), None)


def _period(value: Mapping[str, str]) -> Period:
    try:
        return Period(value["start"], value["end"])
    except (KeyError, TypeError):
        raise SeriesSelectionError("invalid_period", "Give a period with start and end months in YYYY-MM.") from None


def _months(period: Period) -> tuple[str, ...]:
    try:
        return months_in(period)
    except (ValueError, TypeError):
        raise SeriesSelectionError("invalid_period", "Use whole months in YYYY-MM, with start no later than end.") from None


def _conversion(entry: dict, native_units: str, catalog_units: str) -> Conversion:
    """Pick how the file's units become catalog units, or refuse.

    A conversion runs only when the config names the units it expects and the
    file really has them. Without a declaration the units must already match.
    """
    name = entry.get("conversion", "identity")
    if name not in CONVERSIONS:
        raise SeriesSelectionError("series_source_unavailable", f"Unknown unit conversion {name!r} in the gathering config.")
    declared = entry.get("native_units")
    if declared is None:
        if name != "identity" or _units(native_units) != _units(catalog_units):
            raise SeriesSelectionError("units_mismatch", f"The data is in {native_units!r}, not the catalog's {catalog_units!r}; declare native_units and a conversion.")
    elif _units(declared) != _units(native_units):
        raise SeriesSelectionError("units_mismatch", f"The config declares {declared!r} but the data is in {native_units!r}.")
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


def build_series_files(region_ids: list[str], variable_ids: list[str],
                       period: Period | Mapping[str, str], output_dir: Path, *,
                       catalog_path: Path = DEFAULT_CATALOG,
                       config_path: Path = DEFAULT_CONFIG,
                       progress: Callable[[str], None] | None = None) -> list[dict]:
    """Write one series file per Region and Variable and report each outcome.

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
                region_ids, variable_id, period, catalog_path=catalog_path,
                config_path=config_path,
                on_file=lambda done, total, path, v=variable_id: (
                    say(f"{v}: file {done}/{total}") if done in (1, total) or done % 25 == 0 else None))
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
                    json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
                quality = result["quality"]
                row.update(status="included" if quality["included"]
                           else "excluded: " + ", ".join(quality["exclusions"]),
                           missing_fraction=quality["missing_fraction"],
                           valid_land_fraction=quality["valid_land_fraction"])
            rows[region_id, variable_id] = row
            say(f"{region_id} {variable_id}: {row['status']}")
    return [rows[region_id, variable_id] for region_id in region_ids for variable_id in variable_ids]
