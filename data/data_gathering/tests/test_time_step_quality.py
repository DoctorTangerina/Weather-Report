"""#49 amendment / #72 BS-010 through the existing data Quality-gate seam."""

import pytest

from data.data_gathering.quality_gate import assess_quality


@pytest.mark.parametrize(("missing", "included"), [(20, True), (21, False)])
def test_quality_gate_counts_missing_time_steps_at_the_same_limit(missing, included):
    quality = assess_quality(
        [None] * missing + [1.0] * (100 - missing),
        land_only=False,
        time_step="daily",
    )
    assert quality.included is included
    assert quality.missing_fraction == missing / 100
    assert ("too_many_missing_time_steps" in quality.exclusions) is (not included)


@pytest.mark.parametrize("missing", [20, 21, 25])
def test_selection_uses_the_requested_daily_grid_not_monthly_coverage(
    tmp_path, missing
):
    # #49 amendment: one observed day does not make a whole month complete.
    import json

    import numpy as np
    from netCDF4 import Dataset

    from data.data_gathering import SeriesSelectionError, get_time_series

    path = tmp_path / "daily.nc"
    with Dataset(path, "w") as dataset:
        for name, size in (("time", 100), ("lat", 2), ("lon", 2)):
            dataset.createDimension(name, size)
        time = dataset.createVariable("time", "f8", ("time",))
        time.units = "days since 2024-01-01"
        time[:] = np.arange(100)
        dataset.createVariable("lat", "f8", ("lat",))[:] = [0, 1]
        dataset.createVariable("lon", "f8", ("lon",))[:] = [0, 1]
        field = dataset.createVariable(
            "temperature", "f8", ("time", "lat", "lon"), fill_value=-9999
        )
        field.units = "K"
        field[:] = 10
        field[:missing] = np.ma.masked  # Every month still has some data.
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "files": [
                    {"file": str(path), "dataset": "daily", "collection_id": "test"}
                ]
            }
        )
    )
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"SERIES_MANIFEST": str(manifest)}))
    arguments = (
        {"west": -0.5, "east": 1.5, "south": -0.5, "north": 1.5},
        "temperature",
        {"start": "2024-01-01", "end": "2024-04-09"},
    )
    if missing == 20:
        from data.data_processing import process_series

        selected = get_time_series(*arguments, time_step="daily", config_path=config)
        assert selected["quality"]["missing_fraction"] == 0.2
        assert selected["time_step"] == "daily"
        assert selected["aggregation"] == "mean"
        restored = process_series(
            {
                "series": {"A": selected},
                "operations": [
                    {
                        "id": "restored",
                        "operation": "missing",
                        "input": "A",
                        "policy": "zero",
                    },
                ],
            }
        )["series"]["restored"]
        assert sum(restored["filled"]) == 20
        assert restored["provenance"]["A"]["quality"]["missing_fraction"] == 0.2
        assert restored["time_step"] == "daily"
    else:
        with pytest.raises(SeriesSelectionError) as error:
            get_time_series(*arguments, time_step="daily", config_path=config)
        assert error.value.code == "series_quality_excluded"
        assert error.value.quality.missing_fraction == missing / 100
        assert error.value.quality.exclusions == ("too_many_missing_time_steps",)


@pytest.mark.parametrize(("missing", "expected"), [(1, 1 / 8), (2, 2 / 8)])
def test_three_hourly_selection_counts_absent_timestamps_including_period_edges(
    missing, expected
):
    from data.data_gathering.models import Bbox, Period, Source
    from data.data_gathering.selection import (
        NativeSeries,
        SeriesSelectionError,
        select_series,
    )

    class AcquiredFixture:
        def select(self, area, variable, window, dataset_id=None):
            return NativeSeries(
                "fixture",
                "temperature",
                "K",
                "standard",
                {
                    f"2024-01-01T{hour:02}:00:00": 2.0
                    for hour in range(3 * missing, 24, 3)
                },
                Source("fixture", "fixture", "temperature"),
            )

    args = (
        AcquiredFixture(),
        Bbox(-1, 1, -1, 1),
        "temperature",
        Period("2024-01-01", "2024-01-01"),
    )
    if missing == 1:
        result = select_series(*args, time_step="3-hourly")
        assert result.quality.included
        assert result.quality.missing_fraction == expected
    else:
        with pytest.raises(SeriesSelectionError) as error:
            select_series(*args, time_step="3-hourly")
        assert error.value.quality.missing_fraction == expected
        assert "Time steps" in str(error.value)


def test_native_observations_must_match_the_declared_time_step():
    from data.data_gathering.models import Bbox, Period, Source
    from data.data_gathering.selection import (
        NativeSeries,
        SeriesSelectionError,
        select_series,
    )

    class AcquiredFixture:
        def select(self, area, variable, window, dataset_id=None):
            return NativeSeries(
                "fixture",
                "temperature",
                "K",
                "standard",
                {"2024-01-01T00:00:00": 2.0, "2024-01-01T01:00:00": 4.0},
                Source("fixture", "fixture", "temperature"),
            )

    with pytest.raises(SeriesSelectionError) as error:
        select_series(
            AcquiredFixture(),
            Bbox(-1, 1, -1, 1),
            "temperature",
            Period("2024-01-01", "2024-01-01"),
            time_step="daily",
        )
    assert error.value.code == "invalid_time_step"


def test_land_fraction_rule_is_unchanged_with_time_step_quality():
    quality = assess_quality(
        [1.0] * 100, land_only=True, valid_land_fraction=0.49, time_step="daily"
    )
    assert quality.exclusions == ("insufficient_land_fraction",)


def test_declared_utc_time_steps_use_instants_at_requested_period_edges():
    from data.data_gathering.models import Bbox, Period, Source
    from data.data_gathering.selection import NativeSeries, select_series

    class AcquiredFixture:
        def select(self, area, variable, window, dataset_id=None):
            observations = {
                f"2024-01-01T{hour:02}:00:00Z": 1.0 for hour in range(3, 21, 3)
            }
            observations["2023-12-31T21:00:00-03:00"] = 1.0  # Jan 1, 00:00 UTC
            observations["2024-01-02T00:00:00+03:00"] = 1.0  # Jan 1, 21:00 UTC
            return NativeSeries(
                "fixture",
                "temperature",
                "K",
                "standard",
                observations,
                Source("fixture", "fixture", "temperature"),
            )

    result = select_series(
        AcquiredFixture(),
        Bbox(-1, 1, -1, 1),
        "temperature",
        Period("2024-01-01", "2024-01-01"),
        time_step="3-hourly",
    )
    assert result.quality.missing_fraction == 0
    assert len(result.values) == 8
