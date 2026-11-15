"""#47 amendment / #46 BS-001, BS-006: common declared Time step at S1."""

import pytest

from data.data_processing import ProcessingError, process_series


def source(time_step):
    return {
        "timestamps": ["2024-01-01", "2024-01-02"],
        "values": [2, 4],
        "units": "1",
        "time_step": time_step,
    }


def test_expression_refuses_different_time_steps_even_when_timestamps_match():
    with pytest.raises(ProcessingError) as error:
        process_series(
            {
                "series": {"A": source("3-hourly"), "B": source("daily")},
                "operations": [{"id": "result", "expression": "A + B"}],
            }
        )
    assert error.value.code == "unaligned_series"
    assert "Time step" in str(error.value)


def test_resampling_uses_series_aggregation_and_supports_three_hourly_buckets():
    # #48 amendment: temporal aggregation follows the Series, not an invented default.
    response = process_series(
        {
            "series": {
                "A": {
                    "timestamps": [
                        "2024-01-01T00:00:00Z",
                        "2024-01-01T01:00:00Z",
                        "2024-01-01T03:00:00Z",
                    ],
                    "values": [2, 8, 4],
                    "units": "K",
                    "time_step": "hourly",
                    "aggregation": "maximum",
                }
            },
            "operations": [
                {
                    "id": "result",
                    "operation": "resample",
                    "input": "A",
                    "frequency": "3-hourly",
                }
            ],
        }
    )
    result = response["series"]["result"]
    assert result["values"] == [8, 4]
    assert result["timestamps"] == [
        "2024-01-01T00:00:00+00:00",
        "2024-01-01T03:00:00+00:00",
    ]
    assert result["time_step"] == "3-hourly"
    assert result["aggregation"] == "maximum"


@pytest.mark.parametrize(
    ("aggregation", "expected"),
    [
        ("root mean square", 5**0.5),
        ("standard deviation", 2),
        ("mean absolute value", 2),
    ],
)
def test_new_aggregations_apply_over_already_spatially_reduced_values(
    aggregation, expected
):
    # #48 amendment and #72 BS-008: space first (input Series), then time.
    result = process_series(
        {
            "series": {
                "A": {
                    "timestamps": ["2024-01-01T00:00:00Z", "2024-01-01T03:00:00Z"],
                    "values": [-1, 3],
                    "units": "K",
                    "time_step": "3-hourly",
                    "aggregation": aggregation,
                }
            },
            "operations": [
                {
                    "id": "result",
                    "operation": "resample",
                    "input": "A",
                    "frequency": "daily",
                }
            ],
        }
    )["series"]["result"]
    assert result["values"] == pytest.approx([expected])
    assert result["aggregation"] == aggregation


def test_resampling_cannot_override_the_series_aggregation():
    with pytest.raises(ProcessingError) as error:
        process_series(
            {
                "series": {"A": {**source("daily"), "aggregation": "maximum"}},
                "operations": [
                    {
                        "id": "result",
                        "operation": "resample",
                        "input": "A",
                        "frequency": "monthly",
                        "aggregation": "mean",
                    }
                ],
            }
        )
    assert error.value.code == "aggregation_mismatch"


def test_daily_time_steps_are_always_utc_for_explore_my_world():
    with pytest.raises(ProcessingError) as error:
        process_series(
            {
                "series": {"A": {**source("3-hourly"), "aggregation": "mean"}},
                "operations": [
                    {
                        "id": "result",
                        "operation": "resample",
                        "input": "A",
                        "frequency": "daily",
                        "timezone": "America/Sao_Paulo",
                    }
                ],
            }
        )
    assert error.value.code == "invalid_timezone"


def test_monthly_series_cannot_be_resampled_to_a_finer_time_step():
    with pytest.raises(ProcessingError) as error:
        process_series(
            {
                "series": {"A": {**source("monthly"), "aggregation": "mean"}},
                "operations": [
                    {
                        "id": "result",
                        "operation": "resample",
                        "input": "A",
                        "frequency": "daily",
                    }
                ],
            }
        )
    assert error.value.code == "upsampling_not_supported"


def test_aggregation_is_reused_over_area_series_instead_of_pooling_cells():
    # #72 BS-008: spatial medians of [0,0,10], [0,0,10], [5,5,5] are 0,0,5.
    result = process_series(
        {
            "series": {
                "A": {
                    "timestamps": [
                        "2024-01-01T00:00:00Z",
                        "2024-01-01T03:00:00Z",
                        "2024-01-01T06:00:00Z",
                    ],
                    "values": [0, 0, 5],
                    "units": "K",
                    "time_step": "3-hourly",
                    "aggregation": "median",
                }
            },
            "operations": [
                {
                    "id": "result",
                    "operation": "resample",
                    "input": "A",
                    "frequency": "daily",
                }
            ],
        }
    )["series"]["result"]
    assert result["values"] == [0]


def test_matching_time_step_aliases_and_metadata_survive_arithmetic_and_scaling():
    a = {**source("daily"), "frequency": "day", "aggregation": "median"}
    result = process_series(
        {
            "series": {"A": a, "B": {**a, "time_step": "day"}},
            "operations": [
                {"id": "sum", "expression": "A + B"},
                {"id": "scaled", "operation": "minmax", "input": "sum"},
            ],
        }
    )["series"]["scaled"]
    assert result["time_step"] == "daily"
    assert result["aggregation"] == "median"
    assert result["values"] == [0, 1]


def test_contradictory_time_step_metadata_is_rejected():
    with pytest.raises(ProcessingError) as error:
        process_series(
            {
                "series": {"A": {**source("daily"), "frequency": "month"}},
                "operations": [{"id": "result", "expression": "A + 1"}],
            }
        )
    assert error.value.code == "invalid_time_step"


def test_chained_resampling_replays_with_original_aggregation():
    payload = {
        "series": {"A": {**source("daily"), "aggregation": "root mean square"}},
        "operations": [
            {"id": "shifted", "expression": "A + 1"},
            {
                "id": "monthly",
                "operation": "resample",
                "input": "shifted",
                "frequency": "monthly",
            },
        ],
    }
    response = process_series(payload)
    replay = process_series({"series": payload["series"], **response["recipe"]})
    assert response == replay
    assert response["series"]["monthly"]["values"] == pytest.approx([17**0.5])
    assert response["series"]["monthly"]["time_step"] == "monthly"
