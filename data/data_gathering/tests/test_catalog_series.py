"""A catalog Region and Variable become one schema-conformant monthly series (DS-001).

The gate scenarios are BS-003, driven through the public method an API or seed
script calls. Grids are tiny synthetic NetCDF files, so nothing is downloaded.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from netCDF4 import Dataset
from referencing import Registry, Resource

from data.data_gathering import SeriesSelectionError, get_catalog_series
from data.data_gathering.catalog_series import build_series_files

SCHEMAS = Path(__file__).resolve().parents[3] / "schemas"
MONTH_STARTS = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274]  # 2020-01 .. 2020-10
PERIOD = {"start": "2020-01", "end": "2020-10"}


def series_validator() -> Draft202012Validator:
    schemas = [json.loads(path.read_text()) for path in SCHEMAS.glob("*.schema.json")]
    registry = Registry().with_resources(
        [(schema["$id"], Resource.from_contents(schema)) for schema in schemas]
    )
    series = next(s for s in schemas if s["title"] == "Series")
    return Draft202012Validator(series, registry=registry)


def write_grid(
    path,
    *,
    times,
    missing=(),
    land_cells=2,
    rate_level=1e-5,
    time_units="days since 2020-01-01",
):
    """Fields on a 2x2 grid. Land is the first row; the second row is water (999)."""
    with Dataset(path, "w") as data:
        for name, size in (("time", len(times)), ("lat", 2), ("lon", 2)):
            data.createDimension(name, size)
        time = data.createVariable("time", "f8", ("time",))
        time.units = time_units
        time[:] = times
        lat = data.createVariable("lat", "f8", ("lat",))
        lat.units = "degrees_north"
        lat[:] = [0, 1]
        lon = data.createVariable("lon", "f8", ("lon",))
        lon.units = "degrees_east"
        lon[:] = [0, 1]
        for name, units in (("t2m", "K"), ("soil", "kg m-2"), ("rate", "kg m-2 s-1")):
            field = data.createVariable(
                name, "f8", ("time", "lat", "lon"), fill_value=-9999
            )
            field.units = units
            for index in range(len(times)):
                level = {"rate": rate_level}.get(name, index + 1.0)
                field[index] = (
                    np.array([[level, level], [999.0, 999.0]])
                    if name == "soil"
                    else level
                )
        for index in missing:
            for name in ("t2m", "soil", "rate"):
                data.variables[name][index] = np.ma.masked
        data.createVariable("land_classes", "i2", ("lat", "lon"))[:] = np.array(
            [1] * land_cells + [0] * (4 - land_cells)
        ).reshape(2, 2)


CATALOG = {
    "regions": [
        {
            "region_id": "test-region",
            "name": "Test",
            "description": "d",
            "bbox": {"west": -0.5, "east": 1.5, "south": -0.5, "north": 1.5},
            "variable_ids": [
                "temperature",
                "soil-moisture",
                "precipitation",
                "temperature-c",
                "soil-mm",
            ],
        },
        {
            "region_id": "ocean-region",
            "name": "Ocean",
            "description": "d",
            "bbox": {"west": -0.5, "east": 1.5, "south": -0.5, "north": 1.5},
            "variable_ids": ["temperature"],
        },
    ],
    "variables": [
        {
            "variable_id": "temperature",
            "name": "Air temperature",
            "units": "K",
            "definition": "d",
            "land_only": False,
            "possible_causes": [{"text": "c", "kind": "context"}],
            "source": {
                "provider": "GES DISC",
                "dataset": "TEST-T",
                "variable": "t2m",
                "url": "https://example.org/t",
            },
        },
        {
            "variable_id": "soil-moisture",
            "name": "Soil moisture",
            "units": "kg/m²",
            "definition": "d",
            "land_only": True,
            "possible_causes": [{"text": "c", "kind": "context"}],
            "source": {
                "provider": "GES DISC",
                "dataset": "TEST-S",
                "variable": "soil",
                "url": "https://example.org/s",
            },
        },
        {
            "variable_id": "precipitation",
            "name": "Precipitation",
            "units": "mm/month",
            "definition": "d",
            "land_only": False,
            "possible_causes": [{"text": "c", "kind": "context"}],
            "source": {
                "provider": "GES DISC",
                "dataset": "TEST-P",
                "variable": "rate",
                "url": "https://example.org/p",
            },
        },
        {
            "variable_id": "temperature-c",
            "name": "Air temperature",
            "units": "°C",
            "definition": "d",
            "land_only": False,
            "possible_causes": [{"text": "c", "kind": "context"}],
            "source": {
                "provider": "GES DISC",
                "dataset": "TEST-T",
                "variable": "t2m",
                "url": "https://example.org/t",
            },
        },
        {
            "variable_id": "soil-mm",
            "name": "Soil moisture",
            "units": "mm",
            "definition": "d",
            "land_only": True,
            "possible_causes": [{"text": "c", "kind": "context"}],
            "source": {
                "provider": "GES DISC",
                "dataset": "TEST-S",
                "variable": "soil",
                "url": "https://example.org/s",
            },
        },
    ],
    "method_citation": "m",
    "engine_version": "9.9.9",
}


def make_setup(tmp_path, *, series_config=None, mask=True, **grid):
    path = tmp_path / "grid.nc"
    write_grid(path, times=grid.pop("times", MONTH_STARTS), **grid)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"files": [{"file": str(path), "dataset": "grid", "collection_id": "TEST"}]}
        )
    )
    rules = {"soil": {"land_only": True}}
    if mask:
        rules["soil"]["land_mask"] = {"variable": "land_classes", "land_values": [1]}
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "SERIES_MANIFEST": str(manifest),
                "VARIABLE_RULES": {"TEST": rules},
                "CATALOG_SERIES": series_config or {},
            }
        )
    )
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps(CATALOG))
    return {"catalog_path": catalog, "config_path": config}


def series(
    tmp_path, region="test-region", variable="temperature", period=PERIOD, **options
):
    paths = make_setup(tmp_path, **options)
    return get_catalog_series(region, variable, period, **paths)


def test_series_conforms_to_the_series_schema_with_catalog_identity(tmp_path):
    result = series(tmp_path)
    assert list(series_validator().iter_errors(result)) == []
    assert (result["region_id"], result["variable_id"]) == (
        "test-region",
        "temperature",
    )
    assert result["period"] == PERIOD
    assert result["units"] == "K"
    assert result["engine_version"] == "9.9.9"
    assert result["source"] == CATALOG["variables"][0]["source"]
    assert result["values"] == pytest.approx(list(range(1, 11)))
    assert result["quality"] == {
        "included": True,
        "missing_fraction": 0.0,
        "valid_land_fraction": None,
        "exclusions": [],
    }


def test_daily_observations_become_one_mean_per_calendar_month(tmp_path):
    days = list(range(31 + 29))  # every day of 2020-01 and 2020-02
    result = series(tmp_path, period={"start": "2020-01", "end": "2020-02"}, times=days)
    # t2m holds the index of the day, so each month's mean is its mean day index.
    assert result["values"] == [
        pytest.approx(np.mean(range(1, 32))),
        pytest.approx(np.mean(range(32, 61))),
    ]


def test_a_missing_month_is_null_at_its_calendar_position(tmp_path):
    result = series(tmp_path, missing=[3])
    assert result["values"][3] is None
    assert result["values"][2:5] == pytest.approx([3.0, None, 5.0])
    assert result["quality"]["missing_fraction"] == pytest.approx(0.1)


def test_bs003_series_with_more_than_20_percent_missing_months_is_excluded(tmp_path):
    result = series(tmp_path, missing=[0, 1, 2])
    assert list(series_validator().iter_errors(result)) == []
    assert result["quality"]["included"] is False
    assert result["quality"]["exclusions"] == ["too_many_missing_months"]
    assert result["quality"]["missing_fraction"] == pytest.approx(0.3)
    assert result["values"] == [None] * 10, "values of a failed series are withheld"


def test_exactly_20_percent_missing_months_is_kept(tmp_path):
    result = series(tmp_path, missing=[0, 1])
    assert result["quality"]["included"] is True
    assert result["values"][2] == pytest.approx(3.0)


def test_bs003_land_only_variable_with_less_than_half_land_is_excluded(tmp_path):
    result = series(tmp_path, variable="soil-moisture", land_cells=1)
    assert list(series_validator().iter_errors(result)) == []
    assert result["quality"]["included"] is False
    assert result["quality"]["exclusions"] == ["insufficient_land_fraction"]
    assert result["quality"]["valid_land_fraction"] == 0.25
    assert result["values"] == [None] * 10


def test_half_land_is_kept_and_water_is_masked_before_averaging(tmp_path):
    result = series(tmp_path, variable="soil-moisture", land_cells=2)
    assert result["quality"]["included"] is True
    assert result["quality"]["valid_land_fraction"] == 0.5
    assert result["values"] == pytest.approx(list(range(1, 11)))
    assert result["units"] == "kg/m²"


def test_both_exclusion_reasons_are_reported_together(tmp_path):
    result = series(tmp_path, variable="soil-moisture", land_cells=1, missing=[0, 1, 2])
    assert result["quality"]["exclusions"] == [
        "too_many_missing_months",
        "insufficient_land_fraction",
    ]


def test_a_catalog_land_only_variable_without_a_land_mask_fails_closed(tmp_path):
    with pytest.raises(SeriesSelectionError) as error:
        series(tmp_path, variable="soil-moisture", mask=False)
    assert error.value.code == "land_mask_unavailable"


def test_a_variable_the_catalog_does_not_offer_for_the_region_is_refused(tmp_path):
    with pytest.raises(SeriesSelectionError) as error:
        series(tmp_path, region="ocean-region", variable="soil-moisture")
    assert error.value.code == "variable_not_offered_for_region"


@pytest.mark.parametrize(
    "region,variable", [("nowhere", "temperature"), ("test-region", "wind")]
)
def test_ids_outside_the_catalogs_are_refused(tmp_path, region, variable):
    with pytest.raises(SeriesSelectionError) as error:
        series(tmp_path, region=region, variable=variable)
    assert error.value.code == "not_in_catalog"


def test_a_rate_per_second_is_converted_to_the_catalog_units_when_configured(tmp_path):
    configured = {
        "precipitation": {
            "native_units": "kg m-2 s-1",
            "conversion": "rate_per_second_to_per_month",
        }
    }
    result = series(tmp_path, variable="precipitation", series_config=configured)
    january, february = 31 * 86400 * 1e-5, 29 * 86400 * 1e-5
    assert result["units"] == "mm/month"
    assert result["values"][0] == pytest.approx(january)
    assert result["values"][1] == pytest.approx(february)


def test_kelvin_is_shown_as_celsius_when_the_catalog_says_celsius(tmp_path):
    configured = {
        "temperature-c": {"native_units": "K", "conversion": "kelvin_to_celsius"}
    }
    result = series(tmp_path, variable="temperature-c", series_config=configured)
    assert result["units"] == "°C"
    assert result["values"] == pytest.approx([month - 273.15 for month in range(1, 11)])


def test_kelvin_is_never_relabelled_as_celsius(tmp_path):
    with pytest.raises(SeriesSelectionError) as error:
        series(tmp_path, variable="temperature-c")
    assert error.value.code == "units_mismatch"


def test_kg_per_square_metre_is_shown_as_mm_only_when_declared(tmp_path):
    declared = {"soil-mm": {"native_units": "kg m-2", "conversion": "identity"}}
    result = series(tmp_path, variable="soil-mm", series_config=declared)
    assert result["units"] == "mm"
    assert result["values"] == pytest.approx(list(range(1, 11)))
    (tmp_path / "undeclared").mkdir()
    with pytest.raises(SeriesSelectionError) as error:
        series(tmp_path / "undeclared", variable="soil-mm")
    assert error.value.code == "units_mismatch"


def test_a_missing_precipitation_month_stays_missing_after_conversion(tmp_path):
    configured = {
        "precipitation": {
            "native_units": "kg m-2 s-1",
            "conversion": "rate_per_second_to_per_month",
        }
    }
    result = series(
        tmp_path, variable="precipitation", series_config=configured, missing=[3]
    )
    assert result["values"][3] is None
    assert result["values"][2] == pytest.approx(31 * 86400 * 1e-5)  # March 2020


def test_a_precipitation_value_that_cannot_be_a_rate_is_refused_not_converted(tmp_path):
    configured = {
        "precipitation": {
            "native_units": "kg m-2 s-1",
            "conversion": "rate_per_second_to_per_month",
        }
    }
    with pytest.raises(SeriesSelectionError) as error:
        series(
            tmp_path, variable="precipitation", series_config=configured, rate_level=1.0
        )
    assert error.value.code == "implausible_values"


def test_units_that_differ_from_the_catalog_are_never_passed_off_as_catalog_units(
    tmp_path,
):
    with pytest.raises(SeriesSelectionError) as error:
        series(tmp_path, variable="precipitation")
    assert error.value.code == "units_mismatch"


def test_a_declared_conversion_must_match_the_units_actually_in_the_file(tmp_path):
    wrong = {
        "precipitation": {
            "native_units": "mm/day",
            "conversion": "rate_per_second_to_per_month",
        }
    }
    with pytest.raises(SeriesSelectionError) as error:
        series(tmp_path, variable="precipitation", series_config=wrong)
    assert error.value.code == "units_mismatch"


def test_a_period_outside_the_acquired_data_is_all_missing_and_excluded(tmp_path):
    result = series(tmp_path, period={"start": "2021-01", "end": "2021-10"})
    assert result["quality"]["included"] is False
    assert result["quality"]["missing_fraction"] == 1.0


@pytest.mark.parametrize(
    "period",
    [
        {"start": "2020-05", "end": "2020-01"},
        {"start": "2020-01-15", "end": "2020-02"},
        {"start": "bad", "end": "2020-02"},
    ],
)
def test_the_period_must_be_whole_months_in_order(tmp_path, period):
    with pytest.raises(SeriesSelectionError) as error:
        series(tmp_path, period=period)
    assert error.value.code == "invalid_period"


def test_series_files_are_written_per_region_and_variable_named_like_the_stub_set(
    tmp_path,
):
    paths = make_setup(tmp_path)
    out = tmp_path / "out"
    report = build_series_files(
        ["test-region"], ["temperature", "soil-moisture"], PERIOD, out, **paths
    )
    assert sorted(path.name for path in out.iterdir()) == [
        "test-region__soil-moisture.json",
        "test-region__temperature.json",
    ]
    written = json.loads((out / "test-region__temperature.json").read_text())
    assert written == get_catalog_series("test-region", "temperature", PERIOD, **paths)
    assert [
        (row["region_id"], row["variable_id"], row["status"]) for row in report
    ] == [
        ("test-region", "temperature", "included"),
        ("test-region", "soil-moisture", "included"),
    ]


def test_one_unavailable_series_does_not_stop_the_others_and_is_reported(tmp_path):
    paths = make_setup(tmp_path, mask=False)  # soil moisture has no land mask
    report = build_series_files(
        ["test-region"],
        ["soil-moisture", "temperature"],
        PERIOD,
        tmp_path / "out",
        **paths,
    )
    assert [(row["variable_id"], row["status"]) for row in report] == [
        ("soil-moisture", "land_mask_unavailable"),
        ("temperature", "included"),
    ]
    assert not (tmp_path / "out" / "test-region__soil-moisture.json").exists()


def test_an_excluded_series_is_written_flagged_and_reported_as_excluded(tmp_path):
    paths = make_setup(tmp_path, missing=[0, 1, 2])
    report = build_series_files(
        ["test-region"], ["temperature"], PERIOD, tmp_path / "out", **paths
    )
    assert report[0]["status"] == "excluded: too_many_missing_months"
    written = json.loads(
        (tmp_path / "out" / "test-region__temperature.json").read_text()
    )
    assert written["quality"]["included"] is False
