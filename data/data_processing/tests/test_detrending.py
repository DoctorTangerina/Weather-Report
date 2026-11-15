"""#53 / BS-013: explicit linear detrending at S1 (process_series)."""

import copy
import json

import pytest

from data.data_processing import ProcessingError, process_series


def request(values, preserve_mean=False, **metadata):
    return {
        "series": {
            "A": {
                "timestamps": [f"2024-01-{i + 1:02}" for i in range(len(values))],
                "values": values,
                "units": "K",
                **metadata,
            }
        },
        "operations": [
            {
                "id": "detrended",
                "operation": "detrend",
                "input": "A",
                "preserve_mean": preserve_mean,
            }
        ],
    }


# Parent: BS-013, explicit request removes exactly linear change and preserves input.
# Given values 1, 3, 5 on equally spaced dates; When explicitly subtracting the
# fitted line at process_series; Then Derived values are zero and input is intact.
def test_explicit_detrending_removes_exact_linear_change_without_changing_input():
    payload = request([1, 3, 5])
    original = copy.deepcopy(payload)
    result = process_series(payload)["series"]["detrended"]
    assert result["values"] == pytest.approx([0, 0, 0], abs=1e-14)
    assert payload == original


# Parent: BS-013 / Q6: finite representable results survive large intermediates.
@pytest.mark.parametrize(
    "values, preserve_mean, expected",
    [
        ([-1e308, 0, 1e308], False, [0, 0, 0]),
        ([1e308, 1e308, 1e308], True, [1e308, 1e308, 1e308]),
        ([1e16, 1e16 + 2, 1e16 + 4], False, [0, 0, 0]),
    ],
)
def test_representable_results_do_not_overflow_during_fitting(
    values, preserve_mean, expected
):
    response = process_series(request(values, preserve_mean))
    assert response["series"]["detrended"]["values"] == pytest.approx(expected)
    json.dumps(response, allow_nan=False)


# Parent: BS-013 / Q6: a nonfinite result is rejected without mutating input.
def test_unrepresentable_residual_returns_an_explanatory_error():
    payload = request([1.7e308, -1.7e308, 1.7e308])
    original = copy.deepcopy(payload)
    with pytest.raises(ProcessingError, match="nonfinite") as error:
        process_series(payload)
    assert error.value.code == "nonfinite_result"
    assert payload == original


# Parent: BS-013 / Q4: fewer than two valid distinct instants has no fit.
@pytest.mark.parametrize("values", [[None, None], [None, 4], [4]])
def test_detrending_explains_insufficient_valid_observations(values):
    payload = request(values)
    original = copy.deepcopy(payload)
    with pytest.raises(ProcessingError, match="at least two") as error:
        process_series(payload)
    assert error.value.code == "insufficient_observations"
    assert payload == original


# Parent: BS-013, Processing recipe without detrending retains linear change.
# Given 1, 3, 5; When processing an identity arithmetic recipe; Then retain them.
def test_recipe_without_detrending_keeps_linear_change():
    payload = request([1, 3, 5])
    payload["operations"] = [{"id": "unchanged", "expression": "A + 0"}]
    result = process_series(payload)["series"]["unchanged"]
    assert result["values"] == [1, 3, 5]


# Parent: BS-013 / Q1: convention is explicit and both choices retain metadata.
@pytest.mark.parametrize(
    "preserve_mean, expected", [(False, [0, 0, 0]), (True, [22, 22, 22])]
)
def test_mean_convention_is_recorded_for_the_derived_series(preserve_mean, expected):
    response = process_series(request([20, 22, 24], preserve_mean))
    result = response["series"]["detrended"]
    assert result["values"] == pytest.approx(expected)
    assert result["detrending"] == {
        "method": "ols",
        "time_basis": "elapsed_utc_seconds",
        "preserve_mean": preserve_mean,
    }
    assert response["recipe"]["operations"][0]["preserve_mean"] is preserve_mean
    assert response["warnings"] == []


# Parent: BS-013 / Q1: caller must explicitly choose a boolean convention.
@pytest.mark.parametrize(
    "parameters",
    [{}, {"preserve_mean": None}, {"preserve_mean": 0}, {"preserve_mean": "yes"}],
)
def test_detrending_requires_an_explicit_boolean_mean_convention(parameters):
    payload = request([1, 3, 5])
    payload["operations"][0].pop("preserve_mean")
    payload["operations"][0].update(parameters)
    with pytest.raises(ProcessingError) as error:
        process_series(payload)
    assert error.value.code == "invalid_detrending_parameters"


# Parent: BS-013 / Q2: OLS uses actual elapsed UTC time at every Time step.
@pytest.mark.parametrize(
    "time_step, timestamps, values",
    [
        (
            "3-hourly",
            [
                "2024-01-01T00:00:00Z",
                "2024-01-01T03:00:00Z",
                "2024-01-01T12:00:00+03:00",
            ],
            [10, 12, 16],
        ),
        ("daily", ["2024-01-01", "2024-01-02", "2024-01-04"], [10, 12, 16]),
        ("monthly", ["2024-01", "2024-02", "2024-03"], [10, 72, 130]),
    ],
)
def test_exact_elapsed_time_line_is_removed_at_any_time_step(
    time_step, timestamps, values
):
    payload = request(values, time_step=time_step)
    payload["series"]["A"]["timestamps"] = timestamps
    result = process_series(payload)["series"]["detrended"]
    assert result["values"] == pytest.approx([0, 0, 0], abs=1e-12)
    assert result["timestamps"] == timestamps
    assert result["time_step"] == time_step


# Parent: BS-013 / Q2: subtract the least-squares line, without removing outliers.
def test_noisy_sample_retains_its_known_ols_residuals():
    result = process_series(request([1, 2, 6]))["series"]["detrended"]
    assert result["values"] == pytest.approx([0.5, -1, 0.5])


# Parent: BS-013 / Q4-Q5: two samples suffice and constant values are supported.
@pytest.mark.parametrize(
    "values, preserve_mean, expected",
    [
        ([2, 8], False, [0, 0]),
        ([2, 8], True, [5, 5]),
        ([5, 5, 5], False, [0, 0, 0]),
        ([5, 5, 5], True, [5, 5, 5]),
    ],
)
def test_two_observations_and_constant_input_have_defined_results(
    values, preserve_mean, expected
):
    result = process_series(request(values, preserve_mean))["series"]["detrended"]
    assert result["values"] == pytest.approx(expected)


# Parent: BS-013 / Q6: calendars without Gregorian elapsed time are rejected.
def test_non_gregorian_calendar_returns_an_explanatory_error():
    payload = request([1, 3, 5], calendar="360_day")
    original = copy.deepcopy(payload)
    with pytest.raises(ProcessingError, match="Gregorian") as error:
        process_series(payload)
    assert error.value.code == "unsupported_calendar"
    assert payload == original


# Parent: BS-013 / Q3: valid and explicitly filled observations fit; nulls remain.
def test_missing_values_and_filled_observations_keep_their_identity_and_lineage():
    quality = {"included": True, "missing_fraction": 0.25}
    payload = request(
        [1, None, 2, 6],
        filled=[False, False, True, False],
        quality=quality,
        source={"dataset": "fixture"},
        time_step="daily",
        aggregation="mean",
    )
    original = copy.deepcopy(payload)
    result = process_series(payload)["series"]["detrended"]
    # Worked OLS example at days 0, 2, 3: slope 3/2, intercept 1/2.
    assert result["values"] == pytest.approx([0.5, None, -1.5, 1])
    assert result["filled"] == [False, False, True, False]
    assert result["units"] == "K"
    assert result["timestamps"] == original["series"]["A"]["timestamps"]
    assert result["time_step"] == "daily"
    assert result["aggregation"] == "mean"
    assert result["provenance"]["A"]["quality"] == quality
    assert result["provenance"]["A"]["source"] == {"dataset": "fixture"}
    assert payload == original


# Parent: BS-013 / DS-005 / Q3: fit the temporal subset at the recipe position.
def test_missing_filter_detrending_and_arithmetic_chain_replays_in_order():
    payload = request([1, None, 2, 6], time_step="daily", aggregation="mean")
    detrend = {**payload["operations"][0], "input": "subset"}
    payload["operations"] = [
        {
            "id": "filled",
            "operation": "missing",
            "input": "A",
            "policy": "custom",
            "value": 4,
        },
        {
            "id": "subset",
            "operation": "filter",
            "input": "filled",
            "mode": "include",
            "timezone": "UTC",
            "dates": {"start": "2024-01-01", "end": "2024-01-03"},
        },
        detrend,
        {"id": "offset", "expression": "detrended + 10"},
    ]
    original = copy.deepcopy(payload)
    response = process_series(payload)
    detrended = response["series"]["detrended"]
    assert detrended["values"] == pytest.approx([-5 / 6, 5 / 3, -5 / 6])
    assert detrended["filled"] == [False, True, False]
    assert detrended["inputs"] == ["subset"]
    assert (
        detrended["provenance"]["subset"]["provenance"]["filled"]["missing_values"][
            "policy"
        ]
        == "custom"
    )
    assert response["recipe"]["operations"] == original["operations"]
    assert response["series"]["offset"]["values"] == pytest.approx(
        [55 / 6, 35 / 3, 55 / 6]
    )
    replacement = request([10, None, 10, 10], time_step="daily")["series"]
    replay = process_series({"series": replacement, **response["recipe"]})
    assert replay["series"]["offset"]["values"] == pytest.approx([12, 6, 12])
    assert payload == original


# Parent: BS-013 / Q3: later missing-value changes do not alter the earlier fit.
def test_filling_after_detrending_does_not_retroactively_change_fit():
    payload = request([1, None, 2, 6])
    payload["operations"].append(
        {
            "id": "restored",
            "operation": "missing",
            "input": "detrended",
            "policy": "custom",
            "value": 4,
        }
    )
    result = process_series(payload)["series"]["restored"]
    assert result["values"] == pytest.approx([0.5, 4, -1.5, 1])
    assert result["filled"] == [False, True, False, False]


# Parent: BS-013 / US-002: raw and detrended samples stay available for comparison.
def test_raw_and_detrended_comparison_exposes_samples_and_fill_flags():
    payload = request([1, 2, 6], filled=[False, True, False])
    payload["operations"].append(
        {"id": "comparison", "operation": "pearson", "inputs": ["A", "detrended"]}
    )
    response = process_series(payload)
    comparison = response["comparisons"]["comparison"]
    assert comparison["valid_pairs"] == 3
    assert comparison["filled_pairs"] == 1
    assert comparison["sample"]["series"]["A"]["values"] == [1, 2, 6]
    assert comparison["sample"]["series"]["detrended"]["values"] == pytest.approx(
        [0.5, -1, 0.5]
    )
    assert comparison["sample"]["series"]["detrended"]["filled"] == [False, True, False]
    assert comparison["provenance"]["detrended"]["detrending"]["method"] == "ols"


# Parent: BS-013 / Q1-Q3: preserve the valid sample mean while removing its slope.
def test_preserving_mean_retains_noisy_missing_samples_mean():
    result = process_series(request([1, None, 2, 6], True))["series"]["detrended"]
    assert result["values"] == pytest.approx([3.5, None, 1.5, 4])


# Parent: BS-013 / Q4: duplicate UTC instants cannot define an elapsed-time fit.
def test_equivalent_timestamp_labels_are_rejected_as_duplicate_instants():
    payload = request([1, 2])
    payload["series"]["A"]["timestamps"] = [
        "2024-01-01T00:00:00Z",
        "2024-01-01T03:00:00+03:00",
    ]
    with pytest.raises(ProcessingError) as error:
        process_series(payload)
    assert error.value.code == "invalid_timestamps"
