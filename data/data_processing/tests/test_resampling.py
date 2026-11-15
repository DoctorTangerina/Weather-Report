"""Calendar aggregation through the public processing boundary."""

import copy
import json

import pytest

from data.data_processing import ProcessingError, process_series


def request(timestamps, values, **options):
    return {
        "series": {
            "A": {
                "timestamps": timestamps,
                "values": values,
                "units": "mm/day",
                "quality": {"included": True, "missing_fraction": 0.1},
                "source": {"dataset": "acquired"},
            }
        },
        "operations": [
            {
                "id": "daily",
                "operation": "resample",
                "input": "A",
                "source_frequency": "hour",
                "frequency": "day",
                "aggregation": "mean",
                **options,
            }
        ],
    }


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("mean", 5),
        ("average", 5),
        ("sum", 15),
        ("min", 1),
        ("minimum", 1),
        ("max", 9),
        ("maximum", 9),
        ("median", 5),
    ],
)
def test_hourly_to_daily_uses_explicit_aggregation_and_preserves_units(
    method, expected
):
    payload = request(
        ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"],
        [1, 5, 9],
        aggregation=method,
    )
    original = copy.deepcopy(payload)
    result = process_series(payload)["series"]["daily"]
    assert result["timestamps"] == ["2024-01-01T00:00:00+00:00"]
    assert result["values"] == [expected]
    assert result["units"] == "mm/day"  # A sum does not invent accumulated units.
    assert result["resampling"]["sample_counts"] == [3]
    assert result["resampling"]["valid_counts"] == [3]
    assert result["provenance"]["A"]["quality"] == payload["series"]["A"]["quality"]
    assert payload == original
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("aggregation", ["mean", "sum", "min", "max", "median"])
def test_empty_and_all_missing_days_remain_null(aggregation):
    payload = request(
        ["2024-01-01T00:00:00", "2024-01-03T00:00:00", "2024-01-04T00:00:00"],
        [1, None, 4],
        aggregation=aggregation,
    )
    result = process_series(payload)["series"]["daily"]
    assert result["values"] == [1, None, None, 4]
    assert result["resampling"]["sample_counts"] == [1, 0, 1, 1]
    assert result["resampling"]["valid_counts"] == [1, 0, 0, 1]


def test_boundary_belongs_only_to_next_day():
    payload = request(["2024-01-01T23:00:00Z", "2024-01-02T00:00:00Z"], [2, 7])
    assert process_series(payload)["series"]["daily"]["values"] == [2, 7]


def test_monthly_buckets_handle_missing_month_and_leap_day():
    payload = request(
        ["2024-02-28", "2024-02-29", "2024-04-01"],
        [2, 4, 8],
        source_frequency="day",
        frequency="month",
        aggregation="sum",
    )
    result = process_series(payload)["series"]["daily"]
    assert result["values"] == [6, None, 8]
    assert result["timestamps"] == [
        "2024-02-01T00:00:00+00:00",
        "2024-03-01T00:00:00+00:00",
        "2024-04-01T00:00:00+00:00",
    ]


@pytest.mark.parametrize(
    ("source", "target", "timestamps", "expected"),
    [
        ("seconds", "minutes", ["2024-01-01T00:00:00Z", "2024-01-01T00:00:30Z"], [3]),
        ("minutes", "hours", ["2024-01-01T00:00:00Z", "2024-01-01T00:30:00Z"], [3]),
        ("months", "years", ["2023-12", "2024-01"], [2, 4]),
    ],
)
def test_supported_frequencies(source, target, timestamps, expected):
    payload = request(timestamps, [2, 4], source_frequency=source, frequency=target)
    assert process_series(payload)["series"]["daily"]["values"] == expected


def test_local_day_boundaries_use_requested_timezone():
    payload = request(
        ["2024-01-01T23:00:00Z", "2024-01-02T01:00:00Z"],
        [2, 4],
        timezone="America/Sao_Paulo",
    )
    result = process_series(payload)["series"]["daily"]
    assert result["values"] == [3]
    assert result["timestamps"] == ["2024-01-01T00:00:00-03:00"]


def test_repeated_dst_hour_preserves_distinct_hourly_buckets():
    payload = request(
        ["2024-11-03T05:30:00Z", "2024-11-03T06:30:00Z"],
        [2, 8],
        source_frequency="minute",
        frequency="hour",
        timezone="America/New_York",
    )
    result = process_series(payload)["series"]["daily"]
    assert result["values"] == [2, 8]
    assert result["timestamps"] == [
        "2024-11-03T01:00:00-04:00",
        "2024-11-03T01:00:00-05:00",
    ]


def test_daily_buckets_follow_dst_calendar_days():
    payload = request(
        ["2024-03-10T06:00:00Z", "2024-03-11T04:00:00Z"],
        [2, 8],
        timezone="America/New_York",
    )
    result = process_series(payload)["series"]["daily"]
    assert result["timestamps"] == [
        "2024-03-10T00:00:00-05:00",
        "2024-03-11T00:00:00-04:00",
    ]
    assert result["values"] == [2, 8]


@pytest.mark.parametrize(
    "options",
    [
        {"frequency": "minute"},
        {"frequency": "week"},
        {"frequency": None},
        {"aggregation": None},
        {"aggregation": "not-an-aggregation"},
        {"source_frequency": None},
        {"timezone": "invalid/zone"},
    ],
)
def test_invalid_or_finer_requests_raise_structured_error(options):
    payload = request(
        ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"], [1, 2], **options
    )
    with pytest.raises(ProcessingError):
        process_series(payload)


def test_explicit_aggregation_is_required():
    payload = request(["2024-01-01T00:00:00Z"], [2])
    del payload["operations"][0]["aggregation"]
    with pytest.raises(ProcessingError) as error:
        process_series(payload)
    assert error.value.code == "invalid_resampling_parameters"


def test_declared_source_frequency_cannot_hide_finer_observations():
    payload = request(["2024-01-01T00:00:00Z", "2024-01-01T00:30:00Z"], [1, 2])
    with pytest.raises(ProcessingError) as error:
        process_series(payload)
    assert error.value.code == "source_frequency_mismatch"


def test_non_gregorian_calendar_is_explicitly_unsupported():
    payload = request(["2024-01-01", "2024-01-02"], [1, 2], source_frequency="day")
    payload["series"]["A"]["calendar"] = "360_day"
    with pytest.raises(ProcessingError) as error:
        process_series(payload)
    assert error.value.code == "unsupported_calendar"


def test_resampling_chains_with_arithmetic_scaling_and_replays():
    payload = request(
        ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z", "2024-01-02T00:00:00Z"],
        [2, 4, 9],
    )
    payload["operations"] += [
        {"id": "scaled", "operation": "minmax", "input": "daily"},
        {"id": "result", "expression": "scaled * 2"},
    ]
    response = process_series(payload)
    assert response["series"]["result"]["values"] == [0, 2]
    replay = process_series({"series": payload["series"], **response["recipe"]})
    assert replay == response


def test_two_inputs_can_be_explicitly_resampled_then_combined():
    payload = request(["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"], [2, 4])
    payload["series"]["B"] = copy.deepcopy(payload["series"]["A"])
    payload["series"]["B"]["values"] = [6, 8]
    payload["operations"] += [
        {
            "id": "other",
            "operation": "resample",
            "input": "B",
            "source_frequency": "hour",
            "frequency": "day",
            "aggregation": "max",
        },
        {"id": "combined", "expression": "daily + other"},
    ]
    assert process_series(payload)["series"]["combined"]["values"] == [11]


def test_resampling_output_frequency_can_supply_next_source_frequency():
    payload = request(["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"], [2, 4])
    payload["operations"].append(
        {
            "id": "monthly",
            "operation": "resample",
            "input": "daily",
            "frequency": "month",
            "aggregation": "sum",
        }
    )
    result = process_series(payload)["series"]["monthly"]
    assert result["values"] == [6]
    assert result["resampling"]["source_frequency"] == "day"


@pytest.mark.parametrize("aggregation", ["mean", "median"])
def test_large_finite_bucket_does_not_overflow(aggregation):
    payload = request(
        ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
        [1e308, 1e308],
        aggregation=aggregation,
    )
    result = process_series(payload)["series"]["daily"]
    assert result["values"] == [1e308]


def test_overflowing_sum_raises_explanation_instead_of_nonfinite_payload():
    payload = request(
        ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
        [1e308, 1e308],
        aggregation="sum",
    )
    with pytest.raises(ProcessingError) as error:
        process_series(payload)
    assert error.value.code == "nonfinite_result"


def test_partial_bucket_averages_only_valid_values():
    payload = request(
        ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"],
        [1, None, 5],
    )
    result = process_series(payload)["series"]["daily"]
    assert result["values"] == [3]
    assert result["resampling"]["sample_counts"] == [3]
    assert result["resampling"]["valid_counts"] == [2]


def test_existing_frequency_cannot_be_overridden_with_a_false_declaration():
    payload = request(["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"], [1, 2])
    payload["series"]["A"]["frequency"] = "minute"
    with pytest.raises(ProcessingError) as error:
        process_series(payload)
    assert error.value.code == "source_frequency_mismatch"


# #48: summing rate samples must not silently claim an accumulated total.
HOURS = ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"]


@pytest.mark.parametrize("units", ["mm/day", "kg m-2 s-1", "mm per hour", "m/s"])
def test_summing_a_rate_warns_that_the_result_is_a_total(units):
    payload = request(HOURS, [1, 5, 9], aggregation="sum")
    payload["series"]["A"]["units"] = units
    result = process_series(payload)
    warning = next(w for w in result["series"]["daily"]["warnings"])
    assert warning["code"] == "sum_of_rate"
    assert warning["units"] == units
    assert result["warnings"] == [{"operation": "daily", **warning}]


@pytest.mark.parametrize("aggregation", ["mean", "min", "max", "median"])
def test_other_aggregations_of_a_rate_do_not_warn(aggregation):
    result = process_series(request(HOURS, [1, 5, 9], aggregation=aggregation))
    assert result["warnings"] == []


@pytest.mark.parametrize("units", ["mm", "kg m-2", "K", "°C", "1", "m-1"])
def test_summing_a_quantity_that_is_not_a_rate_does_not_warn(units):
    # Precipitation given as the total for each Time step is summed legitimately.
    payload = request(HOURS, [1, 5, 9], aggregation="sum")
    payload["series"]["A"]["units"] = units
    assert process_series(payload)["warnings"] == []
