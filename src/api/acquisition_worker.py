"""Isolated #6 acquisition/NetCDF worker; stdout is reserved for the result."""

import contextlib
import json
import os
import sys
from pathlib import Path

from data.data_gathering import SeriesSelectionError, get_catalog_series
from data.data_gathering.catalog_series import DEFAULT_CATALOG
from data.data_gathering.datasets import SearchArea, acquire
from data.data_gathering.series import DEFAULT_CONFIG


def run(request: dict) -> dict:
    catalog = Path(os.environ.get("WEATHER_REPORT_CATALOG", str(DEFAULT_CATALOG)))
    config = Path(
        os.environ.get("WEATHER_REPORT_ACQUISITION_CONFIG", str(DEFAULT_CONFIG))
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
    configuration = json.loads(config.read_text())
    entry = configuration.get("CATALOG_SERIES", {}).get(request["variable_id"], {})
    if not entry.get("dataset_id"):
        raise SeriesSelectionError("dataset_not_available", "No configured collection")
    area = SearchArea(request["region_id"], tuple(request["bbox"]))
    # Owned by the parent so cancellation removes partial downloads as well.
    directory = Path(request["workspace"])
    with contextlib.redirect_stdout(sys.stderr):
        manifest = acquire(
            [{"collection_id": entry["dataset_id"], "short_name": request["dataset"]}],
            [area],
            request["period"]["start"],
            request["period"]["end"],
            directory,
        )
    configuration["SERIES_MANIFEST"] = str(manifest)
    local_config = directory / "config.json"
    local_config.write_text(json.dumps(configuration))
    return get_catalog_series(*args, catalog_path=catalog, config_path=local_config)


def main() -> None:
    request = json.load(sys.stdin)
    try:
        result = run(request)
    except (SeriesSelectionError, OSError, ValueError, EOFError):
        sys.exit(2)
    json.dump(result, sys.stdout, allow_nan=False)


if __name__ == "__main__":
    main()
