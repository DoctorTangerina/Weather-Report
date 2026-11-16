"""NasaGridAcquisitionSource with the real reduction; only CMR/OPeNDAP are faked.

Selected areas crossing the antimeridian or joined from several rectangles used
to produce one file per box and granule, so the same timestamps appeared twice
and every such request failed with real NASA data.
"""

import pytest

from api.nasa_source import NasaGridAcquisitionSource
from data.data_gathering.catalog_series import (
    DEFAULT_CATALOG,
    get_area_series,
    get_catalog_series,
)
from tests.fake_opendap import FakeOpendap

PERIOD = {"start": "2010-01", "end": "2010-03"}


def inside(boxes):
    """1 at cells whose centre is in any box, 5 elsewhere (temperature in K)."""

    def value(lat, lon):
        for west, south, east, north in boxes:
            in_lon = west <= lon <= east if west <= east else lon >= west or lon <= east
            if in_lon and south <= lat <= north:
                return 274.15  # 1 °C
        return 278.15  # 5 °C

    return value


def area_series(fake, tmp_path, rectangles):
    request = {
        "variable_id": "temperature",
        "period": PERIOD,
        "time_step": "monthly",
        "workspace": str(tmp_path),
        "rectangles": rectangles,
        "bbox": rectangles[0],
    }
    config = NasaGridAcquisitionSource().prepare(request)
    return get_area_series(
        rectangles,
        "temperature",
        PERIOD,
        catalog_path=DEFAULT_CATALOG,
        config_path=config,
    )


@pytest.mark.parametrize(
    "rectangles",
    [
        [[0, 10, 20, 20]],
        [[170, -10, -170, 10]],
        [[0, 10, 10, 20], [10, 10, 20, 20]],
        [[0, 10, 12, 20], [8, 10, 20, 20]],
        [[0, 0, 20, 10], [0, 10, 10, 30]],
        [[160, -10, -175, 0], [-175, -10, -160, 10]],
    ],
    ids=[
        "one box",
        "antimeridian",
        "joined",
        "overlapping",
        "L-shape",
        "joined across 180",
    ],
)
def test_an_area_series_is_built_from_exactly_its_cells(
    tmp_path, monkeypatch, rectangles
):
    fake = FakeOpendap(inside(rectangles)).install(monkeypatch)
    series = area_series(fake, tmp_path, rectangles)
    assert series["values"] == pytest.approx([1.0, 1.0, 1.0], abs=1e-4)
    assert series["quality"]["included"] is True


def test_each_granule_becomes_one_file_with_no_repeated_timestamps(
    tmp_path, monkeypatch
):
    rectangles = [[170, -10, -170, 10]]
    FakeOpendap(inside(rectangles)).install(monkeypatch)
    request = {
        "variable_id": "temperature",
        "period": PERIOD,
        "time_step": "monthly",
        "workspace": str(tmp_path),
        "rectangles": rectangles,
        "bbox": rectangles[0],
    }
    NasaGridAcquisitionSource().prepare(request)
    import json

    files = json.loads((tmp_path / "manifest.json").read_text())["files"]
    assert [record["granule_id"] for record in files] == [
        "G201001",
        "G201002",
        "G201003",
    ]


def test_a_granule_found_for_several_boxes_is_fetched_once(tmp_path, monkeypatch):
    rectangles = [[0, 10, 10, 20], [10, 10, 20, 20]]
    fake = FakeOpendap(inside(rectangles)).install(monkeypatch)
    area_series(fake, tmp_path, rectangles)
    coordinate_requests = [url for url in fake.downloads if "%2Ftime%3B%2Flat" in url]
    assert len(coordinate_requests) == 3


def test_a_region_series_is_unchanged(tmp_path, monkeypatch):
    sahel = [-15, 12, 25, 18]
    FakeOpendap(inside([sahel])).install(monkeypatch)
    request = {
        "region_id": "sahel",
        "variable_id": "temperature",
        "period": PERIOD,
        "time_step": "monthly",
        "workspace": str(tmp_path),
        "bbox": sahel,
    }
    config = NasaGridAcquisitionSource().prepare(request)
    series = get_catalog_series(
        "sahel", "temperature", PERIOD, catalog_path=DEFAULT_CATALOG, config_path=config
    )
    assert series["values"] == pytest.approx([1.0, 1.0, 1.0], abs=1e-4)


def test_downloads_overlap(tmp_path, monkeypatch):
    fake = FakeOpendap(inside([[0, 10, 20, 20]]), delay=0.05).install(monkeypatch)
    area_series(fake, tmp_path, [[0, 10, 20, 20]])
    assert fake.most_active > 1


def test_every_rectangle_of_an_l_shaped_area_contributes(tmp_path, monkeypatch):
    # 1 °C in the lower bar, 3 °C in the upright only: both must count.
    lower, upright = [0, 0, 20, 10], [0, 10, 10, 30]

    def value(lat, lon):
        if 0 <= lon <= 20 and 0 <= lat <= 10:
            return 274.15
        if 0 <= lon <= 10 and 10 < lat <= 30:
            return 276.15
        return 300.0

    fake = FakeOpendap(value).install(monkeypatch)
    first = area_series(fake, tmp_path, [lower, upright])["values"][0]
    assert 1.5 < first < 2.5
