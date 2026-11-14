"""Extraction follows coordinates, dimensions, calendars, scaling and masks."""

import json

import numpy as np
import pytest
from netCDF4 import Dataset

from data.data_gathering.config import load_config, settings
from data.data_gathering.datasets import SearchArea, load_themes, search
from data.data_gathering.extract_series import extract

BOX = SearchArea("box", (-75, -5, -55, 65))


def make_grid(path, *, calendar="standard"):
    with Dataset(path, "w") as data:
        for name, size in (("clock", 3), ("height", 2), ("x", 2), ("y", 2)):
            data.createDimension(name, size)
        time = data.createVariable("clock", "f8", ("clock",))
        time.standard_name = "time"
        time.units = "hours since 2024-01-01 00:00:00"
        time.calendar = calendar
        time[:] = [0, 1, 6]
        lat = data.createVariable("phi", "f8", ("y",))
        lat.units = "degrees_north"
        lat[:] = [0, 60]
        lon = data.createVariable("lambda", "f8", ("x",))
        lon.standard_name = "longitude"
        lon[:] = [290, 300]
        heights = data.createVariable("height", "f8", ("height",))
        heights[:] = [1000, 500]
        rainfall = data.createVariable("arbitrary_field", "f8", ("clock", "height", "x", "y"), fill_value=-9999)
        rainfall.units = "mm/day"
        rainfall.long_name = "An arbitrary field"
        rainfall[:] = np.broadcast_to(np.array([[10, 30], [20, 40]]), (3, 2, 2, 2))
        rainfall[1, 0, :, :] = np.ma.masked
        rainfall[2, 0, :, :] = np.nan
        data.createVariable("static_field", "f8", ("x", "y"))[:] = 1
    return [{"file": str(path), "dataset": "arbitrary-dataset"}]


def test_custom_names_ordered_axes_layers_and_hourly_timestamps(tmp_path):
    records = make_grid(tmp_path / "grid.nc")
    result = extract(records, BOX)
    fields = result["datasets"]["arbitrary-dataset"]
    assert set(fields) == {"arbitrary_field[height=1000.0]", "arbitrary_field[height=500.0]"}
    field = fields["arbitrary_field[height=1000.0]"]
    assert field["units"] == "mm/day"
    assert list(field["observations"]) == ["2024-01-01T00:00:00", "2024-01-01T01:00:00", "2024-01-01T06:00:00"]
    assert field["observations"]["2024-01-01T00:00:00"] == pytest.approx(65 / 3)
    assert field["observations"]["2024-01-01T01:00:00"] is None
    assert field["observations"]["2024-01-01T06:00:00"] is None


def test_mean_is_explicitly_different_from_area_mean(tmp_path):
    result = extract(make_grid(tmp_path / "grid.nc"), BOX, aggregation="mean")
    field = result["datasets"]["arbitrary-dataset"]["arbitrary_field[height=500.0]"]
    assert field["observations"]["2024-01-01T00:00:00"] == 25


def test_per_cell_mode_preserves_spatial_coordinates_and_enforces_limit(tmp_path):
    records = make_grid(tmp_path / "grid.nc")
    result = extract(records, BOX, aggregation="none")
    fields = result["datasets"]["arbitrary-dataset"]
    assert len(fields) == 8
    assert any(field["coordinates"].get("x") == "-70.0" for field in fields.values())
    with pytest.raises(ValueError, match="Series limit"):
        extract(records, BOX, aggregation="none", max_series=4)


def test_scale_offset_and_fill_values_are_decoded_without_changing_units(tmp_path):
    path = tmp_path / "packed.nc"
    with Dataset(path, "w") as data:
        data.createDimension("time", 3)
        time = data.createVariable("time", "f8", ("time",))
        time.units = "days since 2024-01-01"
        time[:] = [0, 1, 2]
        value = data.createVariable("whatever", "i2", ("time",), fill_value=-9999)
        value.units = "K"
        value.scale_factor = 0.1
        value.add_offset = 10.0
        value.set_auto_maskandscale(False)
        value[:] = [1, 2, -9999]
    result = extract([{"file": str(path)}], BOX)
    field = result["datasets"]["data"]["whatever"]
    assert field["units"] == "K"
    assert list(field["observations"].values()) == [10.1, 10.2, None]


def test_conflicting_timestamps_are_not_silently_overwritten(tmp_path):
    records = make_grid(tmp_path / "grid.nc")
    with pytest.raises(ValueError, match="Duplicate/overlapping"):
        extract(records * 2, BOX)


def test_nongregorian_calendar_is_preserved(tmp_path):
    records = make_grid(tmp_path / "grid.nc", calendar="360_day")
    result = extract(records, BOX)
    assert all(field["calendar"] == "360_day" for field in result["datasets"]["arbitrary-dataset"].values())




def test_missing_time_metadata_is_reported(tmp_path):
    path = tmp_path / "static.nc"
    with Dataset(path, "w") as data:
        data.createDimension("x", 3)
        data.createVariable("values", "f8", ("x",))[:] = [1, 2, 3]
    with pytest.raises(ValueError, match="time coordinate"):
        extract([{"file": str(path)}], BOX)


def test_environment_overrides_dotenv_without_replacing_existing_secrets(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text('EARTHDATA_TOKEN="private-token"\n')
    monkeypatch.setenv("EARTHDATA_TOKEN", "environment-token")
    assert settings(path)["EARTHDATA_TOKEN"] == "environment-token"
    assert path.read_text() == 'EARTHDATA_TOKEN="private-token"\n'
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"BBOX": [0, 0, 10, 10]}))
    assert load_config(config_path)["BBOX"] == [0, 0, 10, 10]


def test_theme_search_can_be_customized_in_a_json_file(tmp_path, monkeypatch):
    path = tmp_path / "themes.json"
    path.write_text(json.dumps({"my-new-theme": {"keyword": "snow depth"}}))
    themes = load_themes(path)
    calls = []
    monkeypatch.setattr("data.data_gathering.datasets.cmr_entries", lambda resource, params: calls.append(params) or iter([]))
    assert search("my-new-theme", [BOX], "2024-01", "2024-12", themes=themes) == []
    assert calls[0]["keyword"] == "snow depth"
