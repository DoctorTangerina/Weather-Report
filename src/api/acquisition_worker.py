"""Isolated #6 acquisition/NetCDF worker; stdout is reserved for the result."""

import json
import os
import sys
from pathlib import Path

from data.data_gathering import SeriesSelectionError, get_catalog_series
from data.data_gathering.catalog_series import DEFAULT_CATALOG

from .grid_source import MonthlyGridAcquisitionSource


def run(request: dict) -> dict:
    catalog = Path(os.environ.get("WEATHER_REPORT_CATALOG", str(DEFAULT_CATALOG)))
    source = MonthlyGridAcquisitionSource()
    config = (
        Path(request["config_path"])
        if "config_path" in request
        else source.prepare(request)
    )
    args = (request["region_id"], request["variable_id"], request["period"])
    try:
        return get_catalog_series(*args, catalog_path=catalog, config_path=config)
    except SeriesSelectionError as error:
        if error.code not in {
            "dataset_not_available",
            "series_source_unavailable",
            "variable_not_available",
        }:
            raise
    # Injected grids are already acquired; never fall through to NASA for them.
    if "config_path" in request:
        raise SeriesSelectionError(
            "series_source_unavailable", "Injected grids unavailable"
        )
    config = source.prepare(request, fetch=True)
    return get_catalog_series(*args, catalog_path=catalog, config_path=config)


def main() -> None:
    request = json.load(sys.stdin)
    try:
        result = run(request)
    except (SeriesSelectionError, OSError, ValueError, EOFError):
        sys.exit(2)
    json.dump(result, sys.stdout, allow_nan=False)


if __name__ == "__main__":
    main()
