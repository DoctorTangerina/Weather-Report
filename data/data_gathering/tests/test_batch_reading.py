"""Many Regions are read from each file once, with the same answers as one at a time.

Building the seed set takes every catalog Region for each Variable. Opening
every monthly file once per Region made that take about eleven minutes, so the
batch readers open each file once and give each Region the series it would have
had on its own. Grids are tiny synthetic NetCDF files, so nothing is downloaded.
"""

import json

import numpy as np
import pytest
import test_catalog_series as shared
from netCDF4 import Dataset

from data.data_gathering import (
    SeriesSelectionError,
    get_catalog_series,
    netcdf,
    series_source,
)
from data.data_gathering.catalog_series import (
    build_series_files,
    get_catalog_series_many,
)
from data.data_gathering.models import Bbox
from data.data_gathering.netcdf import extract, extract_many
from data.data_gathering.selection import TimeWindow
from data.data_gathering.series import open_source

DAYS = [0, 31, 60]  # three monthly files: 2020-01, 2020-02, 2020-03
PERIOD = {"start": "2020-01", "end": "2020-03"}
ALL = Bbox(west=-0.5, east=1.5, south=-0.5, north=1.5)
LOWER_ROW = Bbox(west=-0.5, east=1.5, south=-0.5, north=0.5)
OUTSIDE = Bbox(west=50, east=60, south=50, north=60)


class Area:
    def __init__(self, box):
        self.bbox = (box.west, box.south, box.east, box.north)


class OpenCounter:
    """Stands in for `Dataset` and counts how often each path is opened."""

    def __init__(self, monkeypatch, *modules):
        self.opened = []
        for module in modules:
            monkeypatch.setattr(module, "Dataset", self)

    def __call__(self, path, *args, **kwargs):
        self.opened.append(str(path))
        return Dataset(path, *args, **kwargs)

    def count(self, name):
        return sum(1 for path in self.opened if path.endswith(name))


def monthly_files(tmp_path):
    """One file per month, in the shape of the real products: one time step each."""
    records = []
    for index, day in enumerate(DAYS):
        path = tmp_path / f"month-{index}.nc"
        shared.write_grid(path, times=[day])
        records.append({"file": str(path), "dataset": "grid", "collection_id": "TEST"})
    return records


def setup_catalog(tmp_path, *, mask_file=None):
    """The shared test setup over three monthly files and a third, southern Region."""
    records = monthly_files(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": records}))
    soil = {"land_only": True}
    if mask_file:
        soil["land_mask"] = {
            "file": str(mask_file),
            "variable": "land_classes",
            "land_values": [1],
        }
    else:
        soil["land_mask"] = {"variable": "land_classes", "land_values": [1]}
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "SERIES_MANIFEST": str(manifest),
                "VARIABLE_RULES": {"TEST": {"soil": soil}},
                "CATALOG_SERIES": {},
            }
        )
    )
    catalog = json.loads(json.dumps(shared.CATALOG))
    catalog["regions"].append(
        {
            "region_id": "south-row",
            "name": "South",
            "description": "d",
            "bbox": {"west": -0.5, "east": 1.5, "south": -0.5, "north": 0.5},
            "variable_ids": ["temperature", "soil-moisture"],
        }
    )
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog))
    return {"catalog_path": catalog_path, "config_path": config}


def test_each_region_gets_what_it_would_have_had_alone_from_one_open_per_file(
    tmp_path, monkeypatch
):
    records = monthly_files(tmp_path)
    alone = {
        name: extract(records, Area(box), variables=["soil"])
        for name, box in (("all", ALL), ("lower", LOWER_ROW))
    }
    opens = OpenCounter(monkeypatch, netcdf)

    together = extract_many(
        records, {"all": Area(ALL), "lower": Area(LOWER_ROW)}, variables=["soil"]
    )

    assert together == alone
    assert {
        name: len(fields["soil"]["observations"])
        for name, result in together.items()
        for fields in result["datasets"].values()
    } == {"all": 3, "lower": 3}
    assert [opens.count(f"month-{index}.nc") for index in range(3)] == [1, 1, 1]


def test_a_region_the_files_do_not_cover_fails_alone(tmp_path):
    records = monthly_files(tmp_path)

    result = extract_many(
        records, {"all": Area(ALL), "away": Area(OUTSIDE)}, variables=["soil"]
    )

    assert isinstance(result["away"], ValueError)
    assert "No readable numeric time series" in str(result["away"])
    assert result["all"]["datasets"]


def test_a_region_that_fails_while_reading_does_not_take_the_others_with_it(tmp_path):
    records = monthly_files(tmp_path)

    # Per cell, the whole grid is four series and over the limit; one row is two.
    result = extract_many(
        records,
        {"all": Area(ALL), "lower": Area(LOWER_ROW)},
        variables=["soil"],
        aggregation="none",
        max_series=2,
    )

    assert "Series limit" in str(result["all"])
    assert len(result["lower"]["datasets"]["grid"]) == 2


def test_the_batch_reports_each_file_as_it_is_read(tmp_path):
    seen = []

    extract_many(
        monthly_files(tmp_path),
        {"all": Area(ALL)},
        variables=["soil"],
        on_file=lambda done, total, path: seen.append((done, total)),
    )

    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_the_source_gives_each_region_its_series_from_one_open_per_file(
    tmp_path, monkeypatch
):
    paths = setup_catalog(tmp_path)
    source = open_source(paths["config_path"])
    window = TimeWindow.create("2020-01", "2020-03")
    alone = {
        name: source.select(box, "soil", window, "TEST")
        for name, box in (("all", ALL), ("lower", LOWER_ROW))
    }
    opens = OpenCounter(monkeypatch, netcdf, series_source)

    together = source.select_many(
        {"all": ALL, "lower": LOWER_ROW}, "soil", window, "TEST"
    )

    assert together == alone
    # The first file is also opened once to describe the field, however many Regions.
    assert [opens.count(f"month-{index}.nc") for index in range(3)] == [2, 1, 1]


def test_catalog_series_for_many_regions_match_one_at_a_time_and_read_each_file_once(
    tmp_path, monkeypatch
):
    paths = setup_catalog(tmp_path)
    regions = ["test-region", "south-row", "ocean-region"]
    alone = {
        region: get_catalog_series(
            region,
            "soil-moisture" if region != "ocean-region" else "temperature",
            PERIOD,
            **paths,
        )
        for region in regions
    }
    opens = OpenCounter(monkeypatch, netcdf, series_source)

    soil = get_catalog_series_many(
        ["test-region", "south-row"], "soil-moisture", PERIOD, **paths
    )
    temperature = get_catalog_series_many(
        ["ocean-region"], "temperature", PERIOD, **paths
    )

    assert {**soil, **temperature} == alone
    assert soil["test-region"] != soil["south-row"]  # the two boxes really differ
    # One read of each file per Variable, plus one description of the first file.
    assert [opens.count(f"month-{index}.nc") for index in range(3)] == [4, 2, 2]


def test_a_region_that_cannot_be_served_does_not_stop_the_others(tmp_path):
    paths = setup_catalog(tmp_path)

    result = get_catalog_series_many(
        ["south-row", "nowhere", "ocean-region"], "soil-moisture", PERIOD, **paths
    )

    assert result["south-row"]["quality"]["included"]
    assert result["nowhere"].code == "not_in_catalog"
    assert result["ocean-region"].code == "variable_not_offered_for_region"


def test_a_problem_with_the_variable_itself_is_raised_for_the_whole_batch(tmp_path):
    paths = setup_catalog(tmp_path)

    with pytest.raises(SeriesSelectionError) as error:
        get_catalog_series_many(["south-row"], "nonsense", PERIOD, **paths)

    assert error.value.code == "not_in_catalog"


def test_the_external_land_mask_is_read_once_not_once_per_file(tmp_path, monkeypatch):
    mask = tmp_path / "mask.nc"
    with Dataset(mask, "w") as data:
        data.createDimension("lat", 2)
        data.createDimension("lon", 2)
        data.createVariable("lat", "f8", ("lat",))[:] = [0, 1]
        data.variables["lat"].units = "degrees_north"
        data.createVariable("lon", "f8", ("lon",))[:] = [0, 1]
        data.variables["lon"].units = "degrees_east"
        data.createVariable("land_classes", "i2", ("lat", "lon"))[:] = np.array(
            [[1, 1], [0, 0]]
        )
    paths = setup_catalog(tmp_path, mask_file=mask)
    opens = OpenCounter(monkeypatch, netcdf, series_source)

    series = get_catalog_series_many(["test-region"], "soil-moisture", PERIOD, **paths)

    assert series["test-region"]["quality"]["valid_land_fraction"] == 0.5
    assert opens.count("mask.nc") == 1


def test_building_files_reports_progress_and_keeps_the_report_order(tmp_path):
    paths = setup_catalog(tmp_path)
    messages = []

    report = build_series_files(
        ["test-region", "south-row"],
        ["temperature", "soil-moisture"],
        PERIOD,
        tmp_path / "out",
        progress=messages.append,
        **paths,
    )

    assert [
        (row["region_id"], row["variable_id"], row["status"]) for row in report
    ] == [
        ("test-region", "temperature", "included"),
        ("test-region", "soil-moisture", "included"),
        ("south-row", "temperature", "included"),
        ("south-row", "soil-moisture", "included"),
    ]
    assert any("temperature" in text and "1/3" in text for text in messages)
    assert any(
        "south-row" in text and "soil-moisture" in text and "included" in text
        for text in messages
    )
    assert len(list((tmp_path / "out").iterdir())) == 4
