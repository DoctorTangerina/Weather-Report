"""Serve selected fields from a trusted acquisition manifest, without fetching."""

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

from .models import Bbox, SelectedArea, Source
from .netcdf import coordinate, extract_many, groups, inherited_variables, load_manifest
from .selection import NativeSeries, SeriesSelectionError, TimeWindow

# The underlying NetCDF/HDF libraries are not safe for simultaneous thread access.
_READ_LOCK = threading.RLock()


@dataclass(frozen=True)
class _Area:
    bbox: tuple[float, float, float, float]
    boxes: tuple[tuple[float, float, float, float], ...] = ()


def _area(area: Bbox | SelectedArea) -> _Area:
    if isinstance(area, SelectedArea):
        return _Area(area.rectangles[0], area.rectangles)
    return _Area((area.west, area.south, area.east, area.north))


def _flag(value) -> bool:
    if value in (True, 1, "1", "true", "True"):
        return True
    if value in (False, 0, "0", "false", "False", None):
        return False
    raise SeriesSelectionError(
        "series_source_unavailable", "The Variable's land-only metadata is invalid."
    )


class NetCDFSeriesSource:
    def __init__(
        self, manifest: Path, *, rules: dict | None = None, root: Path | None = None
    ):
        self.manifest = Path(manifest)
        self.rules = rules or {}
        self.root = root or self.manifest.parent
        self._masks: dict = {}

    def _datasets(self) -> dict[str, list[dict]]:
        try:
            records = load_manifest(self.manifest)["files"]
            result = {}
            for item in records:
                record = dict(item)
                path = Path(record["file"])
                record["file"] = str(
                    path if path.is_absolute() else self.manifest.parent / path
                )
                identifier = record.get("collection_id") or record["dataset"]
                result.setdefault(identifier, []).append(record)
            return result
        except (OSError, ValueError, KeyError, TypeError):
            raise SeriesSelectionError(
                "series_source_unavailable",
                "Acquired series data is not configured or available.",
            ) from None

    def _rule(self, identifier: str, record: dict, variable: str) -> dict:
        configured = self.rules.get(
            identifier, self.rules.get(record.get("dataset"), {})
        )
        return configured.get(variable, {})

    def _land_only(self, identifier: str, record: dict, name: str, variable) -> bool:
        rule = self._rule(identifier, record, name)
        declared = _flag(rule.get("land_only")) or _flag(
            getattr(variable, "land_only", None)
        )
        return declared

    def _describe(self, identifier: str, records: list[dict]) -> list[dict]:
        fields = []
        try:
            with Dataset(records[0]["file"]) as dataset:
                for prefix, group in groups(dataset):
                    available = inherited_variables(group)
                    _, time = coordinate(available, "time")
                    if time is None or time.ndim != 1:
                        continue
                    for name, variable in group.variables.items():
                        full_name = prefix + name
                        if (
                            name in variable.dimensions
                            or np.dtype(variable.dtype).kind not in "iuf"
                            or time.dimensions[0] not in variable.dimensions
                        ):
                            continue
                        if name in {
                            getattr(item, "bounds", "") for item in available.values()
                        }:
                            continue
                        fields.append(
                            {
                                "variable": full_name,
                                "description": getattr(
                                    variable, "long_name", name
                                ).replace("_", " "),
                                "units": getattr(variable, "units", "unknown"),
                                "land_only": self._land_only(
                                    identifier, records[0], full_name, variable
                                ),
                            }
                        )
        except OSError:
            raise SeriesSelectionError(
                "series_source_unavailable", "An acquired dataset cannot be read."
            ) from None
        return fields

    def available(self) -> list[dict]:
        with _READ_LOCK:
            return [
                {
                    "dataset_id": identifier,
                    "name": records[0].get("dataset", identifier),
                    "variables": self._describe(identifier, records),
                }
                for identifier, records in self._datasets().items()
            ]

    def select(
        self,
        area: Bbox,
        variable: str,
        window: TimeWindow,
        dataset_id: str | None = None,
    ) -> NativeSeries:
        result = self.select_many({"": area}, variable, window, dataset_id)[""]
        if isinstance(result, Exception):
            raise result
        return result

    def select_many(
        self,
        areas: Mapping[str, Bbox],
        variable: str,
        window: TimeWindow,
        dataset_id: str | None = None,
        on_file=None,
        *,
        aggregation: str = "mean",
        cell_conversion=None,
    ) -> dict:
        """Each named area's series, reading every file once.

        A problem with the Variable or dataset itself is raised. A problem with
        one area (nothing readable there, a mask that does not align) is that
        area's value in the result, as the SeriesSelectionError `select` raises.
        `aggregation` combines each area's cells at every timestamp, after
        `cell_conversion` (see `netcdf.extract_many`).
        """
        with _READ_LOCK:
            return self._select_many(
                areas,
                variable,
                window,
                dataset_id,
                on_file,
                aggregation,
                cell_conversion,
            )

    def select_cells(
        self, area, variable, window, dataset_id, cell_conversion, land_only=False
    ):
        """Native cell observations and bounds, with the same masks as Series."""
        with _READ_LOCK:
            result = self._select_many(
                {"field": area},
                variable,
                window,
                dataset_id,
                None,
                cell_conversion=cell_conversion,
                per_cell=True,
                require_land_mask=land_only,
            )["field"]
        if isinstance(result, Exception):
            raise result
        if result["skipped"]:
            raise SeriesSelectionError(
                "series_source_unavailable", "Incomplete grid data."
            )
        return result["datasets"]

    def _select_many(
        self,
        areas,
        variable,
        window,
        dataset_id,
        on_file,
        aggregation="mean",
        cell_conversion=None,
        per_cell=False,
        require_land_mask=False,
    ):
        datasets = self._datasets()
        if dataset_id is not None:
            datasets = {
                identifier: records
                for identifier, records in datasets.items()
                if dataset_id in (identifier, records[0].get("dataset"))
            }
            if not datasets:
                raise SeriesSelectionError(
                    "dataset_not_available",
                    "The selected dataset has not been acquired.",
                )
        raw_name = variable.partition("[")[0]
        candidates = [
            (identifier, records, field)
            for identifier, records in datasets.items()
            for field in self._describe(identifier, records)
            if field["variable"] == raw_name
        ]
        if not candidates:
            raise SeriesSelectionError(
                "variable_not_available",
                "The selected Variable is not available in the acquired data.",
            )
        if len(candidates) != 1:
            raise SeriesSelectionError(
                "series_selection_ambiguous",
                "This Variable occurs in multiple datasets; choose a dataset_id.",
            )
        identifier, records, description = candidates[0]
        rule = self._rule(identifier, records[0], raw_name)
        if require_land_mask and not description["land_only"]:
            raise SeriesSelectionError(
                "land_mask_unavailable", "This land-only Variable requires a land mask."
            )
        mask_provider: Callable[..., np.ndarray] | None = None
        if description["land_only"]:
            mask_rule = rule.get("land_mask")
            if not isinstance(mask_rule, dict) or "variable" not in mask_rule:
                raise SeriesSelectionError(
                    "land_mask_unavailable",
                    "This land-only Variable needs a configured land mask before it can be returned.",
                )

            def provide_land_mask(record, available, geo):
                return self._land_mask(mask_rule, available, geo)

            mask_provider = provide_land_mask

        normalized = [{**record, "dataset": identifier} for record in records]
        try:
            extracted = extract_many(
                normalized,
                {name: _area(area) for name, area in areas.items()},
                variables=[raw_name],
                time_window=(window.lower, window.upper),
                land_mask_provider=mask_provider,
                on_file=on_file,
                aggregation="none" if per_cell else "area-mean",
                with_cell_bounds=per_cell,
                max_series=float("inf") if per_cell else 10000,
                statistic=aggregation,
                cell_conversion=cell_conversion,
            )
        except SeriesSelectionError:
            raise
        except (OSError, ValueError, KeyError):
            raise SeriesSelectionError(
                "series_source_unavailable",
                "The selected data cannot be prepared for this area and time period.",
            ) from None
        if per_cell:
            return extracted
        results = {}
        for name, result in extracted.items():
            try:
                results[name] = self._native_series(
                    result, variable, raw_name, identifier, records, description
                )
            except SeriesSelectionError as error:
                results[name] = error
        return results

    @staticmethod
    def _native_series(extracted, variable, raw_name, identifier, records, description):
        if isinstance(extracted, SeriesSelectionError):
            raise extracted
        if isinstance(extracted, Exception):
            raise SeriesSelectionError(
                "series_source_unavailable",
                "The selected data cannot be prepared for this area and time period.",
            ) from None
        if extracted["skipped"]:
            raise SeriesSelectionError(
                "series_source_unavailable",
                "Some selected source files or fields could not be read; no partial series was returned.",
            )
        fields = extracted["datasets"][identifier]
        if variable in fields:
            key, field = variable, fields[variable]
        elif len(fields) == 1 and raw_name == variable:
            key, field = next(iter(fields.items()))
        else:
            choices = ", ".join(list(fields)[:10])
            raise SeriesSelectionError(
                "series_selection_ambiguous",
                "Choose a specific field/layer: " + choices,
            )
        if field["spatial_aggregation"] == "none":
            raise SeriesSelectionError(
                "series_source_unavailable",
                "This field has no geographic axes for the requested area.",
            )
        return NativeSeries(
            identifier,
            key,
            field["units"],
            field["calendar"],
            field["observations"],
            Source(
                provider=records[0].get("provider", "Earthdata"),
                dataset=records[0].get("dataset", identifier),
                variable=raw_name,
                url=f"https://cmr.earthdata.nasa.gov/search/concepts/{identifier}.html"
                if identifier.startswith("C")
                else records[0].get("url"),
            ),
            land_only=description["land_only"],
            valid_land_fraction=field.get("valid_land_fraction"),
        )

    def _land_mask(self, rule: dict, available: dict, geo: dict) -> np.ndarray:
        if geo is None:
            raise SeriesSelectionError(
                "land_mask_unavailable",
                "A land mask cannot be aligned without geographic coordinates.",
            )
        try:
            if rule.get("file"):
                path = Path(rule["file"])
                path = path if path.is_absolute() else self.root / path
                # The mask is static and the cells are the same in every file of
                # a product, so it is read once per set of cells.
                key = (
                    str(path),
                    rule["variable"],
                    tuple(rule.get("land_values", [1])),
                    geo["dims"],
                    tuple(
                        np.asarray(geo["indices"][dim]).tobytes() for dim in geo["dims"]
                    ),
                )
                if key not in self._masks:
                    with Dataset(path) as mask_file:
                        self._masks[key] = self._external_mask(mask_file, rule, geo)
                return self._masks[key]
            return self._mask_values(
                available[rule["variable"]], geo["dims"], geo["indices"], rule
            )
        except (OSError, KeyError, ValueError, IndexError):
            raise SeriesSelectionError(
                "land_mask_unavailable",
                "The configured land mask is missing or cannot be aligned with the selected cells.",
            ) from None

    @staticmethod
    def _mask_values(variable, dims, indices, rule):
        selectors, remaining = [], []
        for dim, size in zip(variable.dimensions, variable.shape):
            if dim in dims:
                selectors.append(indices[dim])
                remaining.append(dim)
            elif size == 1:
                selectors.append(0)
            else:
                raise ValueError("Land mask must be static on the source grid.")
        if set(remaining) != set(dims):
            raise ValueError("Land mask has different geographic axes.")
        raw = variable[tuple(selectors)]
        raw = np.transpose(raw, [remaining.index(dim) for dim in dims])
        land = np.isin(
            np.ma.getdata(raw), rule.get("land_values", [1])
        ) & ~np.ma.getmaskarray(raw)
        return land

    def _external_mask(self, dataset, rule, geo):
        available = dataset.variables
        _, lat = coordinate(available, "latitude")
        _, lon = coordinate(available, "longitude")
        if (
            lat is None
            or lon is None
            or lat.ndim != 1
            or lon.ndim != 1
            or len(geo["coords"]) != 2
        ):
            raise ValueError("External masks require aligned rectilinear coordinates.")
        target = [geo["coords"][dim][geo["indices"][dim]] for dim in geo["dims"]]
        indices = {}
        for variable, values, is_lon in (
            (lat, target[0], False),
            (lon, target[1], True),
        ):
            coordinates = np.asarray(variable[:], dtype=float)
            if is_lon:
                coordinates = (coordinates + 180) % 360 - 180
            order = np.argsort(coordinates)
            sorted_values = coordinates[order]
            right = np.clip(
                np.searchsorted(sorted_values, values), 0, len(coordinates) - 1
            )
            left = np.clip(right - 1, 0, len(coordinates) - 1)
            nearest = np.where(
                abs(sorted_values[left] - values) < abs(sorted_values[right] - values),
                left,
                right,
            )
            if not np.allclose(sorted_values[nearest], values, rtol=0, atol=1e-5):
                raise ValueError("Mask grid resolution or coordinates do not match.")
            indices[variable.dimensions[0]] = order[nearest]
        return self._mask_values(
            available[rule["variable"]],
            (lat.dimensions[0], lon.dimensions[0]),
            indices,
            rule,
        )
