"""The API-facing Python method validates real grids without an HTTP layer."""

import json

import numpy as np
import pytest
from netCDF4 import Dataset

from data.data_gathering import (
    SeriesSelectionError,
    get_time_series,
    list_available_series,
)

AREA = {"west": -0.5, "east": 1.5, "south": -0.5, "north": 1.5}
PERIOD = {"start": "2024-01", "end": "2024-05"}


def make_config(tmp_path, *, land_count=2, missing=0, configure_mask=True):
    path = tmp_path / "arbitrary.nc"
    with Dataset(path, "w") as data:
        for name, size in (("time", 5), ("lat", 2), ("lon", 2)):
            data.createDimension(name, size)
        time = data.createVariable("time", "f8", ("time",))
        time.units = "days since 2024-01-01"
        time[:] = [0, 31, 60, 91, 121]
        lat = data.createVariable("lat", "f8", ("lat",))
        lat.units = "degrees_north"
        lat[:] = [0, 1]
        lon = data.createVariable("lon", "f8", ("lon",))
        lon.units = "degrees_east"
        lon[:] = [0, 1]
        field = data.createVariable(
            "any_field", "f8", ("time", "lat", "lon"), fill_value=-9999
        )
        field.units = "kg m-2"
        field[:] = np.broadcast_to(np.array([[2, 2], [999, 999]]), (5, 2, 2))
        for index in range(missing):
            field[index] = np.ma.masked
        data.createVariable("land_classes", "i2", ("lat", "lon"))[:] = np.array(
            [1] * land_count + [0] * (4 - land_count)
        ).reshape(2, 2)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "files": [
                    {"file": str(path), "dataset": "arbitrary", "collection_id": "test"}
                ]
            }
        )
    )
    rule = {"land_only": True}
    if configure_mask:
        rule["land_mask"] = {"variable": "land_classes", "land_values": [1]}
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "SERIES_MANIFEST": str(manifest),
                "VARIABLE_RULES": {"test": {"any_field": rule}},
            }
        )
    )
    return config


def test_method_returns_json_ready_data_and_masks_water_before_averaging(tmp_path):
    config = make_config(tmp_path)
    result = get_time_series(AREA, "any_field", PERIOD, config_path=config)
    json.dumps(result, allow_nan=False)
    assert result["values"] == [2.0] * 5
    assert len(result["timestamps"]) == 5
    assert result["units"] == "kg m-2"
    assert result["quality"]["included"] is True
    assert result["quality"]["valid_land_fraction"] == 0.5
    inventory = list_available_series(config_path=config)
    assert inventory[0]["dataset_id"] == "test"
    assert inventory[0]["variables"][0]["land_only"] is True


def test_relative_manifest_survives_moving_data_and_changing_working_directory(
    tmp_path, monkeypatch
):
    from data.data_gathering.models import Bbox, Period
    from data.data_gathering.selection import select_series
    from data.data_gathering.series_source import NetCDFSeriesSource

    original = tmp_path / "original"
    original.mkdir()
    config = make_config(original)
    configuration = json.loads(config.read_text())
    manifest = original / "manifest.json"
    contents = json.loads(manifest.read_text())
    contents["files"][0]["file"] = "arbitrary.nc"
    manifest.write_text(json.dumps(contents))
    moved = tmp_path / "another-computer"
    original.rename(moved)
    monkeypatch.chdir(tmp_path)
    source = NetCDFSeriesSource(
        moved / "manifest.json", rules=configuration["VARIABLE_RULES"]
    )
    result = select_series(source, Bbox(**AREA), "any_field", Period(**PERIOD))
    assert result.values == (2.0,) * 5


@pytest.mark.parametrize("missing,passes", [(1, True), (2, False)])
def test_missing_threshold_is_checked_before_return(tmp_path, missing, passes):
    config = make_config(tmp_path, missing=missing)
    if passes:
        assert (
            get_time_series(AREA, "any_field", PERIOD, config_path=config)["quality"][
                "missing_fraction"
            ]
            == 0.2
        )
    else:
        with pytest.raises(SeriesSelectionError) as rejected:
            get_time_series(AREA, "any_field", PERIOD, config_path=config)
        assert rejected.value.code == "series_quality_excluded"
        assert rejected.value.quality.exclusions == ("too_many_missing_months",)
        assert not hasattr(rejected.value, "values")


def test_gate_is_recomputed_for_the_requested_period(tmp_path):
    config = make_config(tmp_path, missing=1)
    assert get_time_series(AREA, "any_field", PERIOD, config_path=config)["quality"][
        "included"
    ]
    with pytest.raises(SeriesSelectionError) as rejected:
        get_time_series(
            AREA,
            "any_field",
            {"start": "2024-01", "end": "2024-02"},
            config_path=config,
        )
    assert rejected.value.quality.missing_fraction == 0.5


@pytest.mark.parametrize("land_count,passes", [(1, False), (2, True)])
def test_half_land_boundary(tmp_path, land_count, passes):
    config = make_config(tmp_path, land_count=land_count)
    if passes:
        assert (
            get_time_series(AREA, "any_field", PERIOD, config_path=config)["quality"][
                "valid_land_fraction"
            ]
            == 0.5
        )
    else:
        with pytest.raises(SeriesSelectionError) as rejected:
            get_time_series(AREA, "any_field", PERIOD, config_path=config)
        assert rejected.value.quality.exclusions == ("insufficient_land_fraction",)


def test_land_only_without_a_mask_fails_closed(tmp_path):
    config = make_config(tmp_path, configure_mask=False)
    with pytest.raises(SeriesSelectionError) as rejected:
        get_time_series(AREA, "any_field", PERIOD, config_path=config)
    assert rejected.value.code == "land_mask_unavailable"


def test_unknown_dataset_or_variable_is_explicit(tmp_path):
    config = make_config(tmp_path)
    with pytest.raises(SeriesSelectionError) as missing_dataset:
        get_time_series(
            AREA, "any_field", PERIOD, dataset_id="missing", config_path=config
        )
    assert missing_dataset.value.code == "dataset_not_available"
    with pytest.raises(SeriesSelectionError) as missing_variable:
        get_time_series(AREA, "missing", PERIOD, config_path=config)
    assert missing_variable.value.code == "variable_not_available"


def test_ambiguous_field_requires_dataset_selection(tmp_path):
    config = make_config(tmp_path)
    configuration = json.loads(config.read_text())
    manifest = tmp_path / "manifest.json"
    record = json.loads(manifest.read_text())["files"][0]
    manifest.write_text(
        json.dumps(
            {
                "files": [
                    {**record, "collection_id": name, "dataset": name}
                    for name in ("first", "second")
                ]
            }
        )
    )
    rule = configuration["VARIABLE_RULES"]["test"]
    configuration["VARIABLE_RULES"] = {"first": rule, "second": rule}
    config.write_text(json.dumps(configuration))
    with pytest.raises(SeriesSelectionError) as ambiguous:
        get_time_series(AREA, "any_field", PERIOD, config_path=config)
    assert ambiguous.value.code == "series_selection_ambiguous"
    assert (
        get_time_series(
            AREA, "any_field", PERIOD, dataset_id="second", config_path=config
        )["dataset_id"]
        == "second"
    )


@pytest.mark.parametrize("aligned", [True, False])
def test_external_land_mask_is_aligned_by_coordinates(tmp_path, aligned):
    config = make_config(tmp_path)
    path = tmp_path / "mask.nc"
    with Dataset(path, "w") as data:
        for name in ("latitude", "longitude"):
            data.createDimension(name, 2)
        lat = data.createVariable("latitude", "f8", ("latitude",))
        lat.units = "degrees_north"
        lat[:] = [1, 0] if aligned else [3, 2]
        lon = data.createVariable("longitude", "f8", ("longitude",))
        lon.units = "degrees_east"
        lon[:] = [1, 0]
        data.createVariable("mask", "i2", ("latitude", "longitude"))[:] = [
            [0, 0],
            [1, 1],
        ]
    configuration = json.loads(config.read_text())
    configuration["VARIABLE_RULES"]["test"]["any_field"]["land_mask"] = {
        "file": str(path),
        "variable": "mask",
        "land_values": [1],
    }
    config.write_text(json.dumps(configuration))
    if aligned:
        assert (
            get_time_series(AREA, "any_field", PERIOD, config_path=config)["values"]
            == [2.0] * 5
        )
    else:
        with pytest.raises(SeriesSelectionError) as rejected:
            get_time_series(AREA, "any_field", PERIOD, config_path=config)
        assert rejected.value.code == "land_mask_unavailable"


@pytest.mark.parametrize(
    "area,period",
    [
        ({"west": 2, "east": 1, "south": 0, "north": 1}, PERIOD),
        (AREA, {"start": "2025-01", "end": "2024-01"}),
    ],
)
def test_bad_inputs_fail_before_accessing_files(tmp_path, area, period):
    with pytest.raises(SeriesSelectionError):
        get_time_series(
            area, "field", period, config_path=tmp_path / "does-not-exist.json"
        )
