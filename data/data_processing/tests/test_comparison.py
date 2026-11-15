"""Manual Pearson comparison through the public processing method (BS-010)."""

import copy
import json

import pytest

from data.data_processing import ProcessingError, process_series

DAYS = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]


def series(values, timestamps=None, units="mm", **metadata):
    return {
        "timestamps": list(timestamps or DAYS[: len(values)]),
        "values": values,
        "units": units,
        "time_step": "daily",
        **metadata,
    }


def compare(sources, *steps, inputs=("A", "B")):
    return process_series(
        {
            "series": sources,
            "operations": [
                *steps,
                {"id": "AB", "operation": "pearson", "inputs": list(inputs)},
            ],
        }
    )


# BS-010: Nonconstant pairs produce correlation without automatic Evidence labels
def test_nonconstant_pairs_report_r_sample_period_and_overlap():
    sources = {"A": series([1, 2, 3]), "B": series([2, 4, 6])}
    original = copy.deepcopy(sources)

    response = compare(sources)
    result = response["comparisons"]["AB"]

    assert result["method"] == "pearson"
    assert result["r"] == 1
    assert result["valid_pairs"] == 3
    assert result["filled_pairs"] == 0
    assert result["analyzed_period"] == {"start": DAYS[0], "end": DAYS[2]}
    assert result["overlap"] == {"start": DAYS[0], "end": DAYS[2], "timestamps": 3}
    assert result["explanation"] is None
    assert not any("evidence" in key.lower() for key in result)
    assert sources == original
    json.dumps(response, allow_nan=False)


# BS-010: Fewer than three valid pairs cannot produce Pearson correlation
def test_fewer_than_three_jointly_valid_pairs_explain_insufficient_pairs():
    sources = {"A": series([1, 2, None]), "B": series([2, 4, 6])}

    result = compare(sources)["comparisons"]["AB"]

    assert result["r"] is None
    assert result["valid_pairs"] == 2
    assert result["explanation"]["code"] == "insufficient_pairs"
    assert result["explanation"]["required_pairs"] == 3
    assert result["analyzed_period"] == {"start": DAYS[0], "end": DAYS[1]}
    assert result["overlap"] == {"start": DAYS[0], "end": DAYS[2], "timestamps": 3}


def test_three_jointly_valid_pairs_are_enough():
    sources = {"A": series([1, 2, None, 4]), "B": series([2, 4, 6, 7])}

    result = compare(sources)["comparisons"]["AB"]

    assert result["valid_pairs"] == 3
    assert result["explanation"] is None
    assert result["r"] is not None


# BS-010: A constant input cannot produce Pearson correlation
def test_a_constant_input_is_identified_instead_of_returning_r():
    sources = {"A": series([1, 1, 1]), "B": series([2, 3, 4])}

    result = compare(sources)["comparisons"]["AB"]

    assert result["r"] is None
    assert result["valid_pairs"] == 3
    assert result["explanation"]["code"] == "constant_input"
    assert result["explanation"]["inputs"] == ["A"]


def test_both_constant_inputs_are_identified():
    sources = {"A": series([1, 1, 1]), "B": series([5, 5, 5])}

    result = compare(sources)["comparisons"]["AB"]

    assert result["explanation"]["inputs"] == ["A", "B"]


def test_constancy_is_judged_on_the_jointly_valid_pairs():
    # B varies only at the timestamp where A is missing.
    sources = {"A": series([1, 2, 3, None]), "B": series([4, 4, 4, 9])}

    result = compare(sources)["comparisons"]["AB"]

    assert result["explanation"]["code"] == "constant_input"
    assert result["explanation"]["inputs"] == ["B"]


# BS-010: Explicitly filled values participate with a visible filled-pair count
def test_explicitly_filled_values_count_as_filled_pairs():
    sources = {"A": series([1, None, 3]), "B": series([1, 2, 3])}
    fill = {
        "id": "A_filled",
        "operation": "missing",
        "input": "A",
        "replacements": {DAYS[1]: 2},
    }

    result = compare(sources, fill, inputs=("A_filled", "B"))["comparisons"]["AB"]

    assert result["r"] == 1
    assert result["valid_pairs"] == 3
    assert result["filled_pairs"] == 1
    assert result["sample"]["series"]["A_filled"]["filled"] == [False, True, False]
    assert result["sample"]["series"]["B"]["filled"] == [False, False, False]


def test_only_jointly_valid_pairs_with_a_filled_side_count_as_filled():
    # B is filled at day 2; A is filled at day 4 where B is still missing.
    sources = {
        "A": series([1, 2, 3, 4], filled=[False, False, False, True]),
        "B": series([1, 5, 2, None], filled=[False, True, False, False]),
    }

    result = compare(sources)["comparisons"]["AB"]

    assert result["valid_pairs"] == 3
    assert result["filled_pairs"] == 1


def test_unfilled_missing_values_are_excluded_not_filled():
    sources = {"A": series([1, None, 3, 4]), "B": series([1, 2, 3, 5])}

    result = compare(sources)["comparisons"]["AB"]

    assert result["valid_pairs"] == 3
    assert result["filled_pairs"] == 0
    assert result["sample"]["valid"] == [True, False, True, True]
    assert result["sample"]["series"]["A"]["values"] == [1, None, 3, 4]


def test_negative_correlation_is_reported_exactly():
    sources = {"A": series([1, 2, 3]), "B": series([6, 4, 2])}

    assert compare(sources)["comparisons"]["AB"]["r"] == -1


def test_rounding_never_reports_r_outside_minus_one_to_one():
    # Near-collinear values whose unclamped float correlation is 1.0000000000000002.
    a = [
        -313.3150574428041,
        592.4060223704473,
        -483.1583334690082,
        -493.0837020305023,
        460.304461570322,
        953.4765513105835,
    ]
    b = [
        -302525.5998496304,
        572005.6633565066,
        -466520.07678163535,
        -476103.65090763406,
        444453.21104761685,
        920642.2059062646,
    ]
    days = [f"2024-01-0{day}" for day in range(1, 7)]
    sources = {"A": series(a, timestamps=days), "B": series(b, timestamps=days)}

    assert compare(sources)["comparisons"]["AB"]["r"] == 1


def test_large_finite_values_do_not_overflow_the_correlation():
    sources = {"A": series([1e200, 2e200, 3e200]), "B": series([1, 2, 3])}

    assert compare(sources)["comparisons"]["AB"]["r"] == 1


# Acceptance: exact alignment only; nearby timestamps never pair.
def test_only_exactly_equal_instants_pair_across_different_coverage():
    a = series([1, 2, 3, 4], timestamps=DAYS[:4])
    b = series([10, 30, 20, 40], timestamps=DAYS[1:5])

    result = compare({"A": a, "B": b})["comparisons"]["AB"]

    assert result["sample"]["timestamps"] == DAYS[1:4]
    assert result["sample"]["series"]["A"]["values"] == [2, 3, 4]
    assert result["sample"]["series"]["B"]["values"] == [10, 30, 20]
    assert result["overlap"] == {"start": DAYS[1], "end": DAYS[3], "timestamps": 3}
    assert result["valid_pairs"] == 3


def test_nearby_but_unequal_timestamps_do_not_pair():
    hours = ["2024-01-01T00:00:00Z", "2024-01-01T03:00:00Z", "2024-01-01T06:00:00Z"]
    nearby = ["2024-01-01T00:01:00Z", "2024-01-01T03:01:00Z", "2024-01-01T06:01:00Z"]
    a = series([1, 2, 3], timestamps=hours, time_step="3-hourly")
    b = series([1, 2, 3], timestamps=nearby, time_step="3-hourly")

    result = compare({"A": a, "B": b})["comparisons"]["AB"]

    assert result["valid_pairs"] == 0
    assert result["overlap"] is None
    assert result["analyzed_period"] is None
    assert result["explanation"]["code"] == "insufficient_pairs"


def test_equal_instants_with_different_labels_pair():
    a = series([1, 2, 3], timestamps=["2024-01-01", "2024-01-02", "2024-01-03"])
    b = series(
        [3, 5, 9],
        timestamps=[
            "2024-01-01T00:00:00+00:00",
            "2024-01-02T00:00:00Z",
            "2024-01-02T21:00:00-03:00",
        ],
    )

    result = compare({"A": a, "B": b})["comparisons"]["AB"]

    assert result["valid_pairs"] == 3
    assert result["sample"]["timestamps"] == a["timestamps"]


def test_mixed_time_steps_must_be_resampled_first():
    a = series([1, 2, 3])
    b = series([1, 2, 3], timestamps=["2024-01", "2024-02", "2024-03"])
    b["time_step"] = "monthly"

    with pytest.raises(ProcessingError) as error:
        compare({"A": a, "B": b})
    assert error.value.code == "unaligned_series"


# Acceptance: different Regions, Variables and sampling resolutions.
def test_inputs_from_different_regions_variables_and_resolutions_compare():
    hourly = [
        f"2024-01-0{day}T{hour:02d}:00:00Z" for day in (1, 2, 3) for hour in (0, 12)
    ]
    rainfall = {
        "timestamps": hourly,
        "values": [1, 3, 2, 6, 5, 7],
        "units": "mm",
        "source": {"region": "Amazon Basin", "variable": "precipitation"},
    }
    temperature = series(
        [300.0, 301.0, 303.0],
        timestamps=DAYS[:3],
        units="K",
        source={"region": "Sahara", "variable": "air_temperature"},
    )
    daily = {
        "id": "rain_daily",
        "operation": "resample",
        "input": "R",
        "source_frequency": "hour",
        "frequency": "daily",
        "aggregation": "mean",
    }

    response = compare(
        {"R": rainfall, "T": temperature}, daily, inputs=("rain_daily", "T")
    )
    result = response["comparisons"]["AB"]

    assert result["valid_pairs"] == 3
    # Deviations (-2, 0, 2) and (-4/3, -1/3, 5/3): r = 6 / sqrt(8 * 14/3).
    assert result["r"] == pytest.approx(6 / (8 * 14 / 3) ** 0.5)
    assert result["sample"]["series"]["rain_daily"]["values"] == [2, 4, 6]
    assert result["sample"]["series"]["rain_daily"]["units"] == "mm"
    assert result["sample"]["series"]["T"]["units"] == "K"
    assert result["warnings"] == []
    assert result["provenance"]["T"]["source"]["region"] == "Sahara"
    assert (
        result["provenance"]["rain_daily"]["provenance"]["R"]["source"]["region"]
        == "Amazon Basin"
    )


# Acceptance: data for raw-versus-processed overlays, without Mirror preprocessing.
def test_raw_and_processed_series_compare_with_both_sample_values():
    sources = {"A": series([2, 4, 9])}
    scaled = {"id": "A_scaled", "operation": "minmax", "input": "A"}

    response = compare(sources, scaled, inputs=("A", "A_scaled"))
    result = response["comparisons"]["AB"]

    assert result["r"] == pytest.approx(1)
    assert result["sample"]["series"]["A"]["values"] == [2, 4, 9]
    assert result["sample"]["series"]["A_scaled"]["values"] == [0, 2 / 7, 1]
    assert result["sample"]["series"]["A_scaled"]["units"] == "1"
    assert response["series"]["A_scaled"]["values"] == [0, 2 / 7, 1]


# Integration with #52: a temporal filter's excluded observations leave the overlap.
def test_temporally_filtered_series_compare_only_on_retained_observations():
    # 2024-01-03 is a Wednesday; its outlying A value must not enter the sample.
    sources = {"A": series([1, 2, 100, 3, 4]), "B": series([2, 4, 0, 6, 8])}
    no_wednesday = {
        "id": "A_weekdays",
        "operation": "filter",
        "input": "A",
        "timezone": "UTC",
        "mode": "exclude",
        "weekdays": ["wednesday"],
    }

    response = compare(sources, no_wednesday, inputs=("A_weekdays", "B"))
    result = response["comparisons"]["AB"]

    assert result["r"] == 1
    assert result["valid_pairs"] == 4
    assert result["overlap"] == {"start": DAYS[0], "end": DAYS[4], "timestamps": 4}
    assert DAYS[2] not in result["sample"]["timestamps"]
    assert [step["id"] for step in result["recipe"]["operations"]] == [
        "A_weekdays",
        "AB",
    ]


def test_comparison_keeps_lineage_and_a_replayable_recipe():
    sources = {
        "A": series([1, 2, 4], quality={"included": True, "missing_fraction": 0}),
        "B": series([2, 3, 7]),
    }
    double = {"id": "A2", "expression": "2 * A"}

    response = compare(sources, double, inputs=("A2", "B"))
    result = response["comparisons"]["AB"]
    replacement = {"A": series([3, 1, 2]), "B": series([1, 2, 3])}
    replayed = process_series({"series": replacement, **result["recipe"]})

    assert result["inputs"] == ["A2", "B"]
    assert result["provenance"]["A2"]["provenance"]["A"]["quality"] == {
        "included": True,
        "missing_fraction": 0,
    }
    assert result["recipe"] == response["recipe"]
    assert [step["id"] for step in result["recipe"]["operations"]] == ["A2", "AB"]
    assert "AB" not in response["series"]
    assert replayed["comparisons"]["AB"]["r"] == pytest.approx(-0.5)


def test_an_input_that_failed_the_quality_gate_cannot_be_compared():
    sources = {
        "A": series([1, 2, 3], quality={"included": False}),
        "B": series([2, 4, 6]),
    }

    with pytest.raises(ProcessingError) as error:
        compare(sources)
    assert error.value.code == "excluded_series"


@pytest.mark.parametrize(
    "inputs", [["A"], ["A", "A"], ["A", "B", "C"], "AB", ["A", "not valid"]]
)
def test_a_comparison_needs_two_different_named_inputs(inputs):
    sources = {"A": series([1, 2, 3]), "B": series([2, 4, 6])}

    with pytest.raises(ProcessingError) as error:
        process_series(
            {
                "series": sources,
                "operations": [{"id": "AB", "operation": "pearson", "inputs": inputs}],
            }
        )
    assert error.value.code == "invalid_operation"


def test_a_comparison_is_not_a_series_input_for_later_steps():
    sources = {"A": series([1, 2, 3]), "B": series([2, 4, 6])}

    with pytest.raises(ProcessingError) as error:
        process_series(
            {
                "series": sources,
                "operations": [
                    {"id": "AB", "operation": "pearson", "inputs": ["A", "B"]},
                    {"id": "AB", "expression": "A + B"},
                ],
            }
        )
    assert error.value.code == "invalid_operation"
