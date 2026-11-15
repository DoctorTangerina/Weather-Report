"""Explicit missing policies, elapsed-time interpolation and fill lineage."""

import copy
import json

import pytest

from data.data_processing import ProcessingError, process_series

TIMES = [
    "2024-01-01T00:00:00Z",
    "2024-01-01T01:00:00Z",
    "2024-01-01T04:00:00Z",
    "2024-01-01T08:00:00Z",
]


def request(values, **parameters):
    return {
        "series": {
            "A": {
                "timestamps": TIMES[: len(values)],
                "values": values,
                "units": "mm",
                "quality": {"included": True, "missing_fraction": 0.1},
                "source": {"dataset": "acquired"},
            }
        },
        "operations": [
            {"id": "restored", "operation": "missing", "input": "A", **parameters}
        ],
    }


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        ({"policy": "zero"}, [2, 0, 6, 10]),
        ({"policy": "mean"}, [2, 6, 6, 10]),
        ({"policy": "average"}, [2, 6, 6, 10]),
        ({"policy": "min"}, [2, 2, 6, 10]),
        ({"policy": "minimum"}, [2, 2, 6, 10]),
        ({"policy": "max"}, [2, 10, 6, 10]),
        ({"policy": "maximum"}, [2, 10, 6, 10]),
        ({"policy": "custom", "value": -7}, [2, -7, 6, 10]),
    ],
)
def test_common_fill_policies_preserve_timestamps_units_quality_and_sources(
    parameters, expected
):
    payload = request([2, None, 6, 10], **parameters)
    original = copy.deepcopy(payload)
    result = process_series(payload)["series"]["restored"]
    assert result["values"] == expected
    assert result["timestamps"] == TIMES
    assert result["units"] == "mm"
    assert result["filled"] == [False, True, False, False]
    assert result["missing_values"]["filled_timestamps"] == [TIMES[1]]
    assert result["provenance"]["A"]["quality"] == original["series"]["A"]["quality"]
    assert payload == original
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("policy", ["mean", "min", "max"])
def test_statistics_require_valid_observations(policy):
    with pytest.raises(ProcessingError) as error:
        process_series(request([None, None], policy=policy))
    assert error.value.code == "no_valid_values"


@pytest.mark.parametrize(
    "parameters", [{"policy": "zero"}, {"policy": "custom", "value": 5}]
)
def test_constants_can_fill_an_entirely_missing_input(parameters):
    result = process_series(request([None, None], **parameters))["series"]["restored"]
    assert all(value is not None for value in result["values"])
    assert result["filled"] == [True, True]


def test_removal_keeps_remaining_timestamps_and_records_exclusions():
    payload = request([2, None, 6], policy="remove")
    original = copy.deepcopy(payload)
    result = process_series(payload)["series"]["restored"]
    assert result["values"] == [2, 6]
    assert result["timestamps"] == [TIMES[0], TIMES[2]]
    assert result["filled"] == [False, False]
    assert result["missing_values"]["removed_timestamps"] == [TIMES[1]]
    assert result["missing_values"]["filled_timestamps"] == []
    assert payload == original


def test_removing_all_missing_observations_returns_an_empty_derived_series():
    result = process_series(request([None, None], policy="remove"))["series"][
        "restored"
    ]
    assert result["values"] == []
    assert result["timestamps"] == []
    assert result["filled"] == []


def test_individual_replacements_can_restore_only_chosen_missing_timestamps():
    payload = request([None, None, 6, None], replacements={TIMES[0]: 1, TIMES[3]: 9})
    original = copy.deepcopy(payload)
    result = process_series(payload)["series"]["restored"]
    assert result["values"] == [1, None, 6, 9]
    assert result["filled"] == [True, False, False, True]
    assert result["missing_values"]["policy"] == "individual"
    assert result["missing_values"]["filled_timestamps"] == [TIMES[0], TIMES[3]]
    assert payload == original


def test_interpolation_uses_elapsed_time_and_accepts_gap_at_limit():
    payload = request([0, None, 8], policy="interpolation", max_gap_seconds=4 * 3600)
    result = process_series(payload)["series"]["restored"]
    assert result["values"] == [0, 2, 8]
    assert result["filled"] == [False, True, False]


def test_gap_larger_than_limit_stays_missing():
    payload = request(
        [0, None, None, 8], policy="interpolate", max_gap_seconds=4 * 3600
    )
    result = process_series(payload)["series"]["restored"]
    assert result["values"] == [0, None, None, 8]
    assert result["filled"] == [False] * 4


def test_interpolation_does_not_extrapolate_endpoints():
    result = process_series(
        request([None, 2, 6, None], policy="interpolate", max_gap_seconds=4 * 3600)
    )["series"]["restored"]
    assert result["values"] == [None, 2, 6, None]
    assert result["filled"] == [False] * 4


def test_interpolation_without_anchors_keeps_missing_values():
    result = process_series(
        request([None, None], policy="interpolate", max_gap_seconds=3600)
    )["series"]["restored"]
    assert result["values"] == [None, None]


def test_interpolation_compares_offsets_as_utc_instants():
    payload = request([0, None, 8], policy="interpolate", max_gap_seconds=4 * 3600)
    payload["series"]["A"]["timestamps"] = [
        "2024-01-01T00:00:00Z",
        "2023-12-31T22:00:00-03:00",
        "2024-01-01T04:00:00Z",
    ]
    assert process_series(payload)["series"]["restored"]["values"] == [0, 2, 8]


@pytest.mark.parametrize(
    "gap", [None, 0, -1, True, "4 hours", float("inf"), float("nan")]
)
def test_interpolation_requires_explicit_positive_finite_gap(gap):
    with pytest.raises(ProcessingError) as error:
        process_series(request([0, None, 8], policy="interpolate", max_gap_seconds=gap))
    assert error.value.code == "invalid_max_gap"


@pytest.mark.parametrize(
    "parameters",
    [
        {},
        {"policy": "unknown"},
        {"policy": "custom"},
        {"policy": "custom", "value": True},
        {"policy": "custom", "value": float("nan")},
        {"policy": "mean", "value": 5},
        {"policy": "zero", "max_gap_seconds": 3600},
        {"policy": "zero", "replacements": {TIMES[1]: 3}},
        {"replacements": None},
        {"replacements": {TIMES[1]: float("inf")}},
        {"replacements": {TIMES[0]: 10}},
        {"replacements": {"2025-01-01": 10}},
    ],
)
def test_bad_restoration_is_blocked_without_changing_inputs(parameters):
    payload = request([2, None, 6], **parameters)
    original = copy.deepcopy(payload)
    with pytest.raises(ProcessingError):
        process_series(payload)
    # NaN equality is not meaningful; metadata/value identities are otherwise preserved.
    assert payload["series"] == original["series"]


def test_individual_then_common_fill_and_arithmetic_scaling_preserve_flags():
    payload = request([2, None, None, 8], replacements={TIMES[1]: 4})
    payload["operations"] += [
        {
            "id": "remaining",
            "operation": "missing",
            "input": "restored",
            "policy": "mean",
        },
        {"id": "scaled", "operation": "minmax", "input": "remaining"},
        {"id": "result", "expression": "scaled * 2"},
    ]
    result = process_series(payload)
    assert result["series"]["remaining"]["values"] == pytest.approx([2, 4, 14 / 3, 8])
    assert result["series"]["result"]["filled"] == [False, True, True, False]
    replay = process_series({"series": payload["series"], **result["recipe"]})
    assert replay == result


def test_resampling_marks_buckets_containing_filled_contributions():
    payload = request([2, None, 6], policy="zero")
    payload["operations"].append(
        {
            "id": "daily",
            "operation": "resample",
            "input": "restored",
            "source_frequency": "hour",
            "frequency": "day",
            "aggregation": "mean",
        }
    )
    result = process_series(payload)["series"]["daily"]
    assert result["filled"] == [True]
    assert result["values"] == pytest.approx([8 / 3])


def test_removal_retains_existing_fill_flags():
    payload = request([2, None, 6], policy="remove")
    payload["series"]["A"]["filled"] = [True, False, False]
    result = process_series(payload)["series"]["restored"]
    assert result["filled"] == [True, False]


def test_failed_source_quality_cannot_be_rehabilitated_by_filling():
    payload = request([2, None, 6], policy="zero")
    payload["series"]["A"]["quality"]["included"] = False
    with pytest.raises(ProcessingError) as error:
        process_series(payload)
    assert error.value.code == "excluded_series"


@pytest.mark.parametrize(
    "flags", [None, [True], [True, True, False], [False, 0, False]]
)
def test_incorrect_fill_metadata_is_rejected(flags):
    payload = request([2, None, 6], policy="zero")
    payload["series"]["A"]["filled"] = flags
    with pytest.raises(ProcessingError) as error:
        process_series(payload)
    assert error.value.code == "invalid_series"


def test_non_gregorian_interpolation_is_explicitly_rejected():
    payload = request([0, None, 8], policy="interpolate", max_gap_seconds=3600)
    payload["series"]["A"]["calendar"] = "360_day"
    with pytest.raises(ProcessingError) as error:
        process_series(payload)
    assert error.value.code == "unsupported_calendar"
