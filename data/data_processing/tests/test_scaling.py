"""Explicit scaling through the same public method as arithmetic."""

import copy
import json
import statistics
from datetime import UTC, datetime, timedelta

import pytest

from data.data_processing import ProcessingError, process_series


def request(values, method, **parameters):
    return {
        "series": {
            "A": {
                "timestamps": [f"2024-01-{i + 1:02}" for i in range(len(values))],
                "values": values,
                "units": "K",
                "source": {"dataset": "example"},
                "quality": {"included": True, "missing_fraction": 0.1},
            }
        },
        "operations": [
            {"id": "scaled", "operation": method, "input": "A", **parameters}
        ],
    }


def test_minmax_preserves_nulls_input_and_quality():
    payload = request([2, None, 4, 6], "minmax")
    original = copy.deepcopy(payload)
    result = process_series(payload)["series"]["scaled"]
    assert result["values"] == [0, None, 0.5, 1]
    assert result["units"] == "1"
    assert result["timestamps"] == payload["series"]["A"]["timestamps"]
    assert result["provenance"]["A"]["quality"] == {
        "included": True,
        "missing_fraction": 0.1,
    }
    assert result["scaling"] == {"method": "minmax"}
    assert payload == original
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("ddof", [0, 1])
def test_zscore_centres_valid_input_and_preserves_missing(ddof):
    payload = request([1, None, 2, 3], "zscore", ddof=ddof)
    result = process_series(payload)["series"]["scaled"]
    valid = [v for v in result["values"] if v is not None]
    assert statistics.fmean(valid) == pytest.approx(0, abs=1e-15)
    deviation = statistics.pstdev(valid) if ddof == 0 else statistics.stdev(valid)
    assert deviation == pytest.approx(1)
    assert result["values"][1] is None
    assert result["units"] == "1"
    assert result["scaling"] == {"method": "zscore", "ddof": ddof}
    assert payload["series"]["A"]["values"] == [1, None, 2, 3]


@pytest.mark.parametrize(
    ("method", "parameters"),
    [("minmax", {}), ("zscore", {"ddof": 0}), ("zscore", {"ddof": 1})],
)
@pytest.mark.parametrize("values", [[5, None, 5], [5], [0, 0]])
def test_constant_scaling_is_blocked_with_explanation(method, parameters, values):
    payload = request(values, method, **parameters)
    with pytest.raises(ProcessingError, match="constant") as error:
        process_series(payload)
    assert error.value.code == "constant_input"
    assert payload["series"]["A"]["values"] == values


@pytest.mark.parametrize(
    ("method", "parameters"), [("minmax", {}), ("zscore", {"ddof": 0})]
)
def test_all_missing_has_no_statistics(method, parameters):
    with pytest.raises(ProcessingError) as error:
        process_series(request([None, None], method, **parameters))
    assert error.value.code == "no_valid_values"


@pytest.mark.parametrize("parameters", [{}, {"ddof": True}, {"ddof": -1}, {"ddof": 2}])
def test_zscore_requires_explicit_supported_convention(parameters):
    with pytest.raises(ProcessingError) as error:
        process_series(request([1, 2, 3], "zscore", **parameters))
    assert error.value.code == "invalid_scaling_parameters"


def test_scaling_and_arithmetic_chain_in_order_and_replay():
    payload = request([2, None, 4, 6], "minmax")
    payload["operations"].insert(0, {"id": "shifted", "expression": "A + 10"})
    payload["operations"][1]["input"] = "shifted"
    payload["operations"].append({"id": "result", "expression": "scaled * 2 - 1"})
    response = process_series(payload)
    assert response["series"]["result"]["values"] == pytest.approx([-1, None, 0, 1])
    assert response["series"]["scaled"]["inputs"] == ["shifted"]
    replacement = request([10, None, 20, 30], "minmax")["series"]
    replay = process_series({"series": replacement, **response["recipe"]})
    assert replay["series"]["result"]["values"] == pytest.approx([-1, None, 0, 1])


@pytest.mark.parametrize(
    ("method", "parameters"),
    [("minmax", {}), ("zscore", {"ddof": 0}), ("zscore", {"ddof": 1})],
)
def test_scaling_large_finite_values_does_not_overflow(method, parameters):
    response = process_series(request([-1e308, None, 0, 1e308], method, **parameters))
    json.dumps(response, allow_nan=False)
    assert response["series"]["scaled"]["values"][1] is None


def test_derived_scaling_can_be_used_in_a_new_request():
    scaled = process_series(request([2, 4, 6], "minmax"))["series"]["scaled"]
    response = process_series(
        {
            "series": {"previous": scaled},
            "operations": [
                {"id": "again", "operation": "zscore", "input": "previous", "ddof": 1},
            ],
        }
    )
    assert response["series"]["again"]["values"] == pytest.approx([-1, 0, 1])


def test_zscore_retains_small_variation_on_a_large_baseline():
    result = process_series(request([1e16, 1e16 + 2, 1e16 + 4], "zscore", ddof=1))
    assert result["series"]["scaled"]["values"] == pytest.approx([-1, 0, 1])


@pytest.mark.parametrize(
    "step",
    [
        {"id": "scaled", "operation": "minmax", "input": "A", "ddof": 0},
        {"id": "scaled", "operation": "minmax", "input": "missing"},
        {"id": "scaled", "operation": "minmax", "input": "A + 1"},
        {"id": "scaled", "operation": "unknown", "input": "A"},
    ],
)
def test_invalid_scaling_instructions_are_structured_errors(step):
    payload = request([1, 2, 3], "minmax")
    payload["operations"] = [step]
    original = copy.deepcopy(payload)
    with pytest.raises(ProcessingError):
        process_series(payload)
    assert payload == original


def test_minmax_accepts_large_finite_integers_across_zero():
    response = process_series(request([-(10**308), 0, 10**308], "minmax"))
    assert response["series"]["scaled"]["values"] == [0, 0.5, 1]


@pytest.mark.parametrize(
    ("bounds", "expected"),
    [
        ([-1, 1], [-1, None, 0, 1]),
        ([10, 100], [10, None, 55, 100]),
        ([-20, -10], [-20, None, -15, -10]),
        ([0.2, 0.8], [0.2, None, 0.5, 0.8]),
        ([-1e308, 1e308], [-1e308, None, 0, 1e308]),
    ],
)
def test_custom_minmax_range_preserves_missing_and_records_bounds(bounds, expected):
    payload = request([2, None, 4, 6], "minmax", range=bounds)
    original = copy.deepcopy(payload)
    response = process_series(payload)
    result = response["series"]["scaled"]
    assert result["values"] == pytest.approx(expected)
    assert result["units"] == "1"
    assert result["scaling"] == {"method": "minmax", "range": bounds}
    assert result["timestamps"] == payload["series"]["A"]["timestamps"]
    assert payload == original
    json.dumps(response, allow_nan=False)


@pytest.mark.parametrize(
    "bounds",
    [
        None,
        [],
        [1],
        [0, 1, 2],
        [1, 1],
        [1, -1],
        [False, 1],
        [0, True],
        ["0", 1],
        [0, float("nan")],
        [0, float("inf")],
        "0,1",
        [0, 10**400],
    ],
)
def test_invalid_custom_ranges_return_structured_errors(bounds):
    with pytest.raises(ProcessingError) as error:
        process_series(request([2, 4, 6], "minmax", range=bounds))
    assert error.value.code == "invalid_scaling_range"


def test_custom_range_replays_and_does_not_alias_input_parameters():
    payload = request([2, None, 4, 6], "minmax", range=[10, 100])
    payload["operations"].append({"id": "twice", "expression": "scaled * 2"})
    response = process_series(payload)
    replacement = request([10, None, 20, 30], "minmax")["series"]
    replay = process_series({"series": replacement, **response["recipe"]})
    assert replay["series"]["twice"]["values"] == [20, None, 110, 200]
    response["recipe"]["operations"][0]["range"][0] = -999
    response["series"]["scaled"]["scaling"]["range"][0] = -500
    assert payload["operations"][0]["range"] == [10, 100]


def test_custom_range_does_not_apply_to_zscore():
    with pytest.raises(ProcessingError) as error:
        process_series(request([1, 2, 3], "zscore", ddof=0, range=[0, 1]))
    assert error.value.code == "invalid_operation"


# #50 amendment: scaling works on a Series at any Time step.
@pytest.mark.parametrize("hours", [1, 3, 24])
def test_scaling_does_not_depend_on_the_time_step(hours):
    payload = request([2, None, 4, 6], "minmax")
    start = datetime(2024, 1, 1, tzinfo=UTC)
    payload["series"]["A"]["timestamps"] = [
        (start + timedelta(hours=hours * i)).isoformat() for i in range(4)
    ]
    scaled = process_series(payload)["series"]["scaled"]
    assert scaled["values"] == [0.0, None, 0.5, 1.0]
    assert scaled["timestamps"] == payload["series"]["A"]["timestamps"]
