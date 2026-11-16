"""Public recipe boundary: numeric results, validation, units and replay."""

import copy
import json

import pytest

from data.data_processing import ProcessingError, preview_expression, process_series

TIMES = ["2024-01-01", "2024-02-01", "2024-03-01"]


def series(values, units="1", **metadata):
    return {
        "timestamps": TIMES[: len(values)],
        "values": values,
        "units": units,
        "quality": {"included": True, "missing_fraction": 0.0},
        **metadata,
    }


def calculate(inputs, expression, **parameters):
    return process_series(
        {
            "series": inputs,
            "operations": [
                {"id": "result", "expression": expression, **parameters},
            ],
        }
    )


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("A + B + C", 9),
        ("A - B - C", -5),
        ("A * B * C", 24),
        ("A * B / C", 1.5),
        ("2 * A", 4),
        ("2 * A + 3 * B - C", 9),
        ("0 * A + B", 3),
        ("(A + B) * C", 20),
        ("A + B * C", 14),
        ("-A + +B", 1),
        ("-2 * A + B", -1),
    ],
)
def test_arbitrary_multi_input_arithmetic(expression, expected):
    response = calculate(
        {"A": series([2]), "B": series([3]), "C": series([4])}, expression
    )
    assert response["series"]["result"]["values"] == [expected]
    json.dumps(response, allow_nan=False)


def test_chaining_replay_lineage_and_input_immutability():
    a = series(
        [1, 2, 3],
        units="°C",
        area={"west": 0, "east": 1},
        source={"dataset": "real-source"},
    )
    request = {
        "series": {"A": a},
        "operations": [
            {"id": "offset", "expression": "A + 1"},
            {"id": "double", "expression": "offset * 2"},
        ],
    }
    original = copy.deepcopy(request)
    response = process_series(request)
    result = response["series"]["double"]
    assert result["values"] == [4, 6, 8]
    assert result["units"] == "°C"
    assert result["timestamps"] == TIMES
    assert result["provenance"]["offset"]["provenance"]["A"]["source"] == a["source"]
    replay = process_series(
        {"series": {"A": series([2, 3, 4], "°C")}, **response["recipe"]}
    )
    assert replay["series"]["double"]["values"] == [6, 8, 10]
    assert request == original
    result["provenance"]["offset"]["provenance"]["A"]["area"]["west"] = -20
    assert request == original
    json.dumps(response, allow_nan=False)


def test_derived_result_can_be_supplied_to_a_later_request():
    derived = calculate({"A": series([1, 2, 3])}, "A * 2")["series"]["result"]
    output = calculate({"previous": derived}, "previous + 3")
    assert output["series"]["result"]["values"] == [5, 7, 9]
    assert derived["values"] == [2, 4, 6]


def test_preview_lists_inputs_constants_and_retains_parentheses():
    assert preview_expression("(A + 2 * B) / C") == {
        "expression": "(A + 2 * B) / C",
        "inputs": ["A", "B", "C"],
        "constants": [2],
    }


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('id')",
        "A[0]",
        "A.__class__",
        "A ** 2",
        "A // 2",
        "A % 2",
        "A > 2",
        "True + A",
        "A + '2'",
        "A +",
        "",
        "A + 1e999",
    ],
)
def test_unsupported_instructions_are_rejected(expression):
    with pytest.raises(ProcessingError) as error:
        calculate({"A": series([1, 2, 3])}, expression)
    assert error.value.code == "invalid_expression"


@pytest.mark.parametrize("expression", ["A / B", "A / (B - 1)"])
def test_zero_denominators_block_without_returning_partial_results(expression):
    inputs = {"A": series([0, None, 4]), "B": series([0, 1, 2])}
    before = copy.deepcopy(inputs)
    with pytest.raises(ProcessingError) as error:
        calculate(inputs, expression)
    assert error.value.code == "zero_denominator"
    assert error.value.details["timestamps"]
    json.dumps(error.value.as_dict(), allow_nan=False)
    assert inputs == before


def test_explicit_denominator_correction_and_zero_numerator():
    response = calculate({"A": series([0, 4]), "B": series([0, 1])}, "A / (B + 1)")
    assert response["series"]["result"]["values"] == [0, 2]


def test_nulls_propagate_without_zero_fill_or_shortened_timeline():
    response = calculate(
        {"A": series([1, None, 3]), "B": series([None, 2, 4])}, "A + B"
    )
    result = response["series"]["result"]
    assert result["values"] == [None, None, 7]
    assert result["timestamps"] == TIMES


def test_compatible_units_require_acknowledgement_then_convert():
    inputs = {"A": series([1], "m"), "B": series([100], "cm")}
    with pytest.raises(ProcessingError) as error:
        calculate(inputs, "A + B")
    assert error.value.code == "unit_confirmation_required"
    response = calculate(inputs, "A + B", acknowledge_unit_difference=True)
    assert response["series"]["result"]["values"] == [2]
    assert response["series"]["result"]["units"] == "m"
    assert response["warnings"][0]["conversion"]["factor"] == 0.01
    assert inputs["B"]["values"] == [100]


def test_offset_unit_conversion():
    result = calculate(
        {"A": series([0], "°C"), "B": series([273.15], "K")},
        "A + B",
        acknowledge_unit_difference=True,
    )["series"]["result"]
    assert result["values"] == pytest.approx([0])
    assert result["units"] == "°C"


def test_incompatible_addition_requires_acknowledgement_and_mixed_label():
    inputs = {"A": series([2], "°C"), "B": series([3], "mm")}
    with pytest.raises(ProcessingError, match="Units differ"):
        calculate(inputs, "A + B")
    result = calculate(inputs, "A + B", acknowledge_unit_difference=True)["series"][
        "result"
    ]
    assert result["values"] == [5]
    assert result["units"] == "Mixed units: °C + mm"


@pytest.mark.parametrize(
    ("expression", "units", "values"),
    [
        ("A * B", "(m) * (s)", [6]),
        ("A / B", "(m) / (s)", [2 / 3]),
    ],
)
def test_multiplication_and_division_allow_compound_units(expression, units, values):
    result = calculate({"A": series([2], "m"), "B": series([3], "s")}, expression)[
        "series"
    ]["result"]
    assert result["units"] == units
    assert result["values"] == pytest.approx(values)


def test_timestamp_offsets_align_as_exact_instants():
    a = series([2], timestamps=["2024-01-01T12:00:00Z"])
    b = series([3], timestamps=["2024-01-01T09:00:00-03:00"])
    assert calculate({"A": a, "B": b}, "A + B")["series"]["result"]["values"] == [5]


@pytest.mark.parametrize(
    "change",
    [
        {"timestamps": ["2024-01-02", "2024-02-01", "2024-03-01"]},
        {"calendar": "360_day"},
    ],
)
def test_unaligned_inputs_are_not_silently_resampled(change):
    with pytest.raises(ProcessingError) as error:
        calculate({"A": series([1, 2, 3]), "B": series([1, 2, 3], **change)}, "A + B")
    assert error.value.code == "unaligned_series"


@pytest.mark.parametrize(
    "bad",
    [
        {"values": [1, float("nan"), 2]},
        {"values": [True, 2, 3]},
        {"timestamps": TIMES[:2]},
        {"timestamps": [TIMES[0]] * 3},
        {"quality": {"included": False, "exclusions": ["missing"]}},
        {"units": ""},
    ],
)
def test_invalid_or_excluded_source_values_are_rejected(bad):
    with pytest.raises(ProcessingError):
        calculate({"A": {**series([1, 2, 3]), **bad}}, "A + 1")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"series": {}, "operations": []},
        {
            "series": {"A": series([1])},
            "operations": [{"id": "A", "expression": "A + 1"}],
        },
        {
            "series": {"A": series([1])},
            "operations": [{"id": "B", "expression": "C + 1"}],
        },
        {
            "series": {"A": series([1])},
            "operations": [{"id": "B", "expression": "1 + 2"}],
        },
        {
            "series": {"A": series([1])},
            "operations": [{"id": "B", "expression": "A", "extra": 2}],
        },
    ],
)
def test_bad_recipe_does_not_partially_mutate_request(payload):
    before = copy.deepcopy(payload)
    with pytest.raises(ProcessingError):
        process_series(payload)
    assert payload == before


def test_nonfinite_results_are_structured_errors():
    with pytest.raises(ProcessingError) as error:
        calculate({"A": series([1e308])}, "A * 100")
    assert error.value.code == "nonfinite_result"


def test_percentage_converts_to_dimensionless_fraction():
    result = calculate(
        {"A": series([0.5], "1"), "B": series([50], "%")},
        "A + B",
        acknowledge_unit_difference=True,
    )["series"]["result"]
    assert result["values"] == [1]
    assert result["units"] == "1"
