"""Acquisition boundary: sources supply raw NetCDF grids via a gathering config.

A config identifies the manifest, native field, units conversion and land-mask
rules. Reduction stays in the shared data layer. The initial preparation may
reuse configured files; fetch=True requests acquisition after those prove
unavailable. Sources must put newly created files in request['workspace'].
"""

import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Protocol


class GridAcquisitionSource(Protocol):
    def prepare(self, request: dict, *, fetch: bool = False) -> Path:
        """Return the gathering config for grids covering the requested area/period."""
        ...


class MonthlyGridAcquisitionSource:
    """Today's configured monthly files, followed by the existing NASA download."""

    def prepare(self, request: dict, *, fetch: bool = False) -> Path:
        from data.data_gathering.datasets import SearchArea, acquire
        from data.data_gathering.selection import SeriesSelectionError
        from data.data_gathering.series import DEFAULT_CONFIG

        config = Path(
            os.environ.get("WEATHER_REPORT_ACQUISITION_CONFIG", str(DEFAULT_CONFIG))
        )
        if not fetch:
            return config
        configuration = json.loads(config.read_text())
        entry = configuration.get("CATALOG_SERIES", {}).get(request["variable_id"], {})
        if not entry.get("dataset_id"):
            raise SeriesSelectionError(
                "dataset_not_available", "No configured collection"
            )
        area = SearchArea(request["region_id"], tuple(request["bbox"]))
        directory = Path(request["workspace"])
        with contextlib.redirect_stdout(sys.stderr):
            manifest = acquire(
                [
                    {
                        "collection_id": entry["dataset_id"],
                        "short_name": request["dataset"],
                    }
                ],
                [area],
                request["period"]["start"],
                request["period"]["end"],
                directory,
            )
        configuration["SERIES_MANIFEST"] = str(manifest)
        local_config = directory / "config.json"
        local_config.write_text(json.dumps(configuration))
        return local_config
