"""#56 S1: Variable-name selections are loaded before numeric correlation."""

import copy

import pytest

from data.data_processing import ProcessingError, build_correlation_map, process_series


def source(values, *, time_step="daily", timestamps=None, **metadata):
    return {
        "timestamps": timestamps
        or [f"2024-01-{i + 1:02d}" for i in range(len(values))],
        "values": values,
        "units": "K",
        "time_step": time_step,
        "aggregation": "mean",
        "quality": {"included": True, "missing_fraction": 0.0},
        **metadata,
    }


def test_variable_names_are_loaded_and_return_an_ordered_symmetric_numeric_map():
    # #56 BS-005: no Source-series values are supplied in the user request.
    available = {"temperature": source([1, 2, 3]), "precipitation": source([2, 4, 6])}

    def loader(selection, period):
        return available[selection["variable"]]

    request = {
        "variables": ["temperature", "precipitation"],
        "area": "sahel",
        "period": {"start": "2024-01-01", "end": "2024-01-03"},
    }
    original = copy.deepcopy(request)
    result = build_correlation_map(request, loader=loader)
    assert [item["variable"] for item in result["inputs"]] == request["variables"]
    assert result["matrix"] == [[1, 1], [1, 1]]
    assert result["observation_count"] == 3
    assert result["excluded"] == []
    assert result["settings"]["time_step"] == "daily"
    assert request == original


@pytest.mark.parametrize(
    "bad",
    [
        source([2, None, 6]),
        source([5, 5, 5]),
        source(
            [2, 4, 6],
            quality={"included": False, "exclusions": ["insufficient_land_fraction"]},
        ),
        source([2, 6], timestamps=["2024-01-01", "2024-01-03"]),
    ],
)
def test_unusable_loaded_input_is_excluded_without_losing_valid_comparisons(bad):
    # #56 BS-004: complete inputs remain, with an actionable per-input explanation.
    available = {"A": source([1, 2, 3]), "B": source([2, 4, 6]), "C": bad}
    result = build_correlation_map(
        {
            "variables": ["A", "B", "C"],
            "area": "sahel",
            "period": {"start": "2024-01-01", "end": "2024-01-03"},
        },
        loader=lambda selection, period: available[selection["variable"]],
    )
    assert [item["variable"] for item in result["inputs"]] == ["A", "B"]
    assert result["matrix"] == [[1, 1], [1, 1]]
    assert result["excluded"][0]["variable"] == "C"
    assert result["excluded"][0]["message"]


def test_named_variables_and_regions_load_from_backend_cache_without_input_series(
    tmp_path,
):
    import json

    from data.data_processing.correlation_source import SeedSeriesLoader

    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "regions": [{"region_id": "sahel", "name": "Sahel"}],
                "variables": [
                    {"variable_id": "temperature", "name": "Air temperature"},
                    {"variable_id": "precipitation", "name": "Precipitation"},
                ],
            }
        )
    )
    for variable, values in [("temperature", [1, 2, 3]), ("precipitation", [2, 4, 6])]:
        (tmp_path / f"sahel__{variable}.json").write_text(
            json.dumps(
                {
                    "variable_id": variable,
                    "region_id": "sahel",
                    "units": "K",
                    "period": {"start": "2024-01", "end": "2024-03"},
                    "values": values,
                    "quality": {"included": True, "missing_fraction": 0},
                }
            )
        )
    result = build_correlation_map(
        {
            "variables": ["Air temperature", "Precipitation"],
            "area": "Sahel",
            "period": {"start": "2024-01", "end": "2024-03"},
        },
        loader=SeedSeriesLoader(catalog_path=catalog, series_dir=tmp_path),
    )
    assert result["matrix"] == [[1, 1], [1, 1]]
    assert result["observation_count"] == 3


def test_explicit_monthly_target_resamples_loaded_daily_series_using_its_aggregation():
    # #56 BS-003 and #62 amendment: space first, then the Series Aggregation over time.
    from datetime import date, timedelta

    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(60)]
    daily = source(
        [None if day.day == 10 else (1 if day.month == 1 else 3) for day in days],
        timestamps=[day.isoformat() for day in days],
        quality={"included": True, "missing_fraction": 2 / 60},
    )
    monthly = source(
        [2, 4], time_step="monthly", timestamps=["2024-01-01", "2024-02-01"]
    )
    available = {"A": daily, "B": monthly}
    result = build_correlation_map(
        {
            "variables": ["A", "B"],
            "area": "sahel",
            "time_step": "monthly",
            "period": {"start": "2024-01", "end": "2024-02"},
        },
        loader=lambda selection, period: available[selection["variable"]],
    )
    assert result["matrix"] == [[1, 1], [1, 1]]
    assert result["settings"]["time_step"] == "monthly"
    assert result["observation_count"] == 2
    assert daily["values"][9] is None


def test_two_observations_return_the_score_with_an_alert():
    # #56 BS-005: the map permits two observations, unlike the separate #51 method.
    available = {"A": source([1, 2]), "B": source([4, 3])}
    result = build_correlation_map(
        {
            "variables": ["A", "B"],
            "area": "sahel",
            "period": {"start": "2024-01-01", "end": "2024-01-02"},
        },
        loader=lambda selection, period: available[selection["variable"]],
    )
    assert result["matrix"] == [[1, -1], [-1, 1]]
    assert result["warnings"][0]["code"] == "two_observations"


def test_filled_values_and_source_history_remain_distinguishable():
    from data.data_processing import process_series

    raw = source(
        [1, None, 3],
        source={"dataset": "test-source"},
        quality={"included": True, "missing_fraction": 0.1},
    )
    restored = process_series(
        {
            "series": {"source": raw},
            "operations": [
                {
                    "id": "restored",
                    "operation": "missing",
                    "input": "source",
                    "policy": "mean",
                },
            ],
        }
    )["series"]["restored"]
    available = {"A": restored, "B": source([2, 4, 6])}
    original = copy.deepcopy(available)
    result = build_correlation_map(
        {
            "variables": ["A", "B"],
            "area": "sahel",
            "period": {"start": "2024-01-01", "end": "2024-01-03"},
        },
        loader=lambda selection, period: available[selection["variable"]],
    )
    assert result["matrix"] == [[1, 1], [1, 1]]
    assert result["filled_pair_counts"] == [[1, 1], [1, 0]]
    assert result["inputs"][0]["metadata"]["provenance"] == restored["provenance"]
    assert result["inputs"][0]["metadata"]["recipe"] == restored["recipe"]
    assert available == original


def test_duplicate_names_are_not_loaded_twice_or_added_as_extra_matrix_rows():
    available = {"A": source([1, 2, 3]), "B": source([3, 2, 1])}
    result = build_correlation_map(
        {
            "variables": ["A", "A", "B"],
            "area": "sahel",
            "period": {"start": "2024-01-01", "end": "2024-01-03"},
        },
        loader=lambda selection, period: available[selection["variable"]],
    )
    assert [item["variable"] for item in result["inputs"]] == ["A", "B"]
    assert result["matrix"] == [[1, -1], [-1, 1]]
    assert result["warnings"][0]["code"] == "duplicate_selection"


def test_quality_exclusion_keeps_its_reason_even_if_no_values_are_available():
    available = {
        "A": source([1, 2, 3]),
        "B": source([3, 2, 1]),
        "C": {
            "quality": {
                "included": False,
                "exclusions": ["insufficient_land_fraction"],
            },
        },
    }
    result = build_correlation_map(
        {
            "variables": ["A", "B", "C"],
            "area": "sahel",
            "period": {"start": "2024-01-01", "end": "2024-01-03"},
        },
        loader=lambda selection, period: available[selection["variable"]],
    )
    assert result["excluded"][0]["code"] == "excluded_series"
    assert result["excluded"][0]["details"]["quality"]["exclusions"] == [
        "insufficient_land_fraction"
    ]


def test_zero_correlation_is_not_filtered_or_replaced_by_an_error():
    available = {"A": source([1, 2, 3]), "B": source([1, 0, 1])}
    result = build_correlation_map(
        {
            "variables": ["A", "B"],
            "area": "sahel",
            "period": {"start": "2024-01-01", "end": "2024-01-03"},
        },
        loader=lambda selection, period: available[selection["variable"]],
    )
    assert result["matrix"] == [[1, 0], [0, 1]]
    assert result["excluded"] == []
    assert not any("evidence" in key.lower() for key in result)


def test_different_variables_and_joined_areas_are_forwarded_to_the_backend_source():
    selections = [
        {
            "id": "temp_A",
            "variable": "temperature",
            "area": {"id": "area_A", "rectangles": [{"west": 170, "east": -170}]},
        },
        {
            "id": "soil_B",
            "variable": "soil-moisture",
            "area": {
                "id": "area_B",
                "rectangles": [{"west": 10, "east": 20}, {"west": 20, "east": 30}],
            },
        },
    ]

    def loader(selection, period):
        assert selection["area"] == next(
            x["area"] for x in selections if x["id"] == selection["id"]
        )
        return source(
            [1, 2, 3] if selection["variable"] == "temperature" else [3, 2, 1]
        )

    result = build_correlation_map(
        {
            "variables": selections,
            "period": {"start": "2024-01-01", "end": "2024-01-03"},
        },
        loader=loader,
    )
    assert [x["id"] for x in result["inputs"]] == ["temp_A", "soil_B"]
    assert result["matrix"] == [[1, -1], [-1, 1]]


def test_only_the_chosen_period_is_compared():
    available = {"A": source([1000, 1, 2, 3, -500]), "B": source([0, 2, 4, 6, 100])}
    result = build_correlation_map(
        {
            "variables": ["A", "B"],
            "area": "sahel",
            "period": {"start": "2024-01-02", "end": "2024-01-04"},
        },
        loader=lambda selection, period: available[selection["variable"]],
    )
    assert result["matrix"] == [[1, 1], [1, 1]]
    assert result["observation_count"] == 3


def test_equivalent_offsets_match_without_changing_the_observation_instants():
    available = {
        "A": source(
            [1, 2], timestamps=["2024-01-01T12:00:00Z", "2024-01-02T12:00:00Z"]
        ),
        "B": source(
            [2, 4],
            timestamps=["2024-01-01T09:00:00-03:00", "2024-01-02T09:00:00-03:00"],
        ),
    }
    result = build_correlation_map(
        {
            "variables": ["A", "B"],
            "area": "sahel",
            "period": {"start": "2024-01-01", "end": "2024-01-02"},
        },
        loader=lambda selection, period: available[selection["variable"]],
    )
    assert result["matrix"] == [[1, 1], [1, 1]]
    assert result["timestamps"] == [
        "2024-01-01T12:00:00+00:00",
        "2024-01-02T12:00:00+00:00",
    ]


def test_nearby_timestamps_are_refused_without_silently_pairing_them():
    from data.data_processing import ProcessingError

    available = {
        "A": source(
            [1, 2], timestamps=["2024-01-01T12:00:00Z", "2024-01-02T12:00:00Z"]
        ),
        "B": source(
            [2, 4], timestamps=["2024-01-01T12:05:00Z", "2024-01-02T12:05:00Z"]
        ),
    }
    with pytest.raises(ProcessingError) as error:
        build_correlation_map(
            {
                "variables": ["A", "B"],
                "area": "sahel",
                "period": {"start": "2024-01-01", "end": "2024-01-02"},
            },
            loader=lambda selection, period: available[selection["variable"]],
        )
    assert error.value.code == "unaligned_series"


def test_unavailable_variable_yields_an_explanation_and_keeps_other_inputs():
    from data.data_processing import ProcessingError

    def loader(selection, period):
        if selection["variable"] == "unavailable":
            raise ProcessingError(
                "variable_unavailable", "No data for this Variable; choose another."
            )
        return source([1, 2, 3])

    result = build_correlation_map(
        {
            "variables": ["A", "unavailable", "B"],
            "area": "sahel",
            "period": {"start": "2024-01-01", "end": "2024-01-03"},
        },
        loader=loader,
    )
    assert [x["variable"] for x in result["inputs"]] == ["A", "B"]
    assert result["excluded"][0]["variable"] == "unavailable"
    assert result["excluded"][0]["code"] == "variable_unavailable"


def test_fewer_than_two_usable_inputs_returns_an_error_with_exclusions():
    from data.data_processing import ProcessingError

    with pytest.raises(ProcessingError) as error:
        build_correlation_map(
            {
                "variables": ["A", "B"],
                "area": "sahel",
                "period": {"start": "2024-01-01", "end": "2024-01-03"},
            },
            loader=lambda selection, period: source(
                [1, 2, 3] if selection["variable"] == "A" else [5, 5, 5]
            ),
        )
    assert error.value.code == "insufficient_inputs"
    assert error.value.details["excluded"][0]["variable"] == "B"
    assert "matrix" not in error.value.as_dict()


def test_resource_failure_asks_for_fewer_inputs_and_returns_no_partial_matrix():
    from data.data_processing import ProcessingError

    def loader(selection, period):
        raise MemoryError

    with pytest.raises(ProcessingError) as error:
        build_correlation_map(
            {
                "variables": ["A", "B"],
                "area": "sahel",
                "period": {"start": "2024-01-01", "end": "2024-01-03"},
            },
            loader=loader,
        )
    assert error.value.code == "resource_exhausted"
    assert "Reduce the number of inputs" in str(error.value)
    assert "matrix" not in error.value.as_dict()


@pytest.mark.parametrize(
    "target, code",
    [(None, "resampling_required"), ("daily", "upsampling_not_supported")],
)
def test_different_sampling_needs_an_explicit_coarser_target(target, code):
    from data.data_processing import ProcessingError

    available = {
        "A": source([1, 2, 3]),
        "B": source(
            [1, 2], time_step="monthly", timestamps=["2024-01-01", "2024-02-01"]
        ),
    }
    request = {
        "variables": ["A", "B"],
        "area": "sahel",
        "period": {"start": "2024-01", "end": "2024-02"},
    }
    if target:
        request["time_step"] = target
    with pytest.raises(ProcessingError) as error:
        build_correlation_map(
            request, loader=lambda selection, period: available[selection["variable"]]
        )
    assert error.value.code == code


def test_input_count_has_no_small_fixed_limit():
    result = build_correlation_map(
        {
            "variables": [f"var_{i}" for i in range(12)],
            "area": "sahel",
            "period": {"start": "2024-01-01", "end": "2024-01-03"},
        },
        loader=lambda selection, period: source([1, 2, 3]),
    )
    assert len(result["matrix"]) == 12
    assert all(len(row) == 12 for row in result["matrix"])


@pytest.mark.parametrize(
    "change, code",
    [
        ({"variables": [{"variable": "A", "values": [1, 2]}, "B"]}, "invalid_request"),
        ({"area": None}, "invalid_request"),
        ({"period": None}, "invalid_period"),
        ({"timezone": "invalid-zone"}, "invalid_timezone"),
        (
            {
                "variables": [
                    {"variable": "A", "id": "same"},
                    {"variable": "B", "id": "same"},
                ]
            },
            "duplicate_input_id",
        ),
    ],
)
def test_invalid_requests_return_structured_errors(change, code):
    from data.data_processing import ProcessingError

    request = {
        "variables": ["A", "B"],
        "area": "sahel",
        "period": {"start": "2024-01-01", "end": "2024-01-03"},
        **change,
    }
    with pytest.raises(ProcessingError) as error:
        build_correlation_map(
            request, loader=lambda selection, period: source([1, 2, 3])
        )
    assert error.value.code == code


def test_a_wholly_empty_month_after_resampling_excludes_only_that_input():
    available = {
        "A": source(
            [1, 2, 3],
            time_step="monthly",
            timestamps=["2024-01-01", "2024-02-01", "2024-03-01"],
        ),
        "B": source(
            [2, 4, 6],
            time_step="monthly",
            timestamps=["2024-01-01", "2024-02-01", "2024-03-01"],
        ),
        "C": source([1, 3], timestamps=["2024-01-01", "2024-03-01"]),
    }
    result = build_correlation_map(
        {
            "variables": ["A", "B", "C"],
            "area": "test",
            "period": {"start": "2024-01", "end": "2024-03"},
            "time_step": "monthly",
        },
        loader=lambda selection, period: available[selection["variable"]],
    )
    assert result["matrix"] == [[1, 1], [1, 1]]
    assert result["excluded"][0]["code"] == "incomplete_output_timeline"
    assert result["excluded"][0]["details"]["missing_timestamps"] == [
        "2024-02-01T00:00:00+00:00"
    ]


def test_zero_usable_inputs_returns_exclusions_and_no_matrix():
    from data.data_processing import ProcessingError

    with pytest.raises(ProcessingError) as error:
        build_correlation_map(
            {
                "variables": ["A", "B"],
                "area": "test",
                "period": {"start": "2024-01-01", "end": "2024-01-03"},
            },
            loader=lambda selection, period: {"quality": {"included": False}},
        )
    assert error.value.code == "insufficient_inputs"
    assert len(error.value.details["excluded"]) == 2
    assert "matrix" not in error.value.as_dict()


def test_legacy_local_zone_uses_common_local_bucket_boundaries():
    hourly = source(
        [1, 2, 3, 4, 5, 6],
        timestamps=[
            "2024-01-01T02:00Z",
            "2024-01-01T04:00Z",
            "2024-01-02T02:00Z",
            "2024-01-02T04:00Z",
            "2024-01-03T02:00Z",
            "2024-01-03T04:00Z",
        ],
    )
    hourly.pop("time_step")
    hourly["frequency"] = "hour"
    daily = source([1, 2], timestamps=["2024-01-01T03:00Z", "2024-01-02T03:00Z"])
    daily.pop("time_step")
    daily["frequency"] = "day"
    result = build_correlation_map(
        {
            "variables": ["A", "B"],
            "area": "test",
            "period": {"start": "2024-01-01", "end": "2024-01-02"},
            "time_step": "daily",
            "timezone": "America/Sao_Paulo",
        },
        loader=lambda selection, period: (
            hourly if selection["variable"] == "A" else daily
        ),
    )
    assert result["matrix"] == [[1, 1], [1, 1]]
    assert result["timestamps"] == [
        "2024-01-01T03:00:00+00:00",
        "2024-01-02T03:00:00+00:00",
    ]
    assert result["settings"]["timezone"] == "America/Sao_Paulo"


# #62: a prepared Derived series keeps the local-zone semantics its #48
# resampling confirmed, while acquired Time steps keep following UTC.
SAO_PAULO = "America/Sao_Paulo"


def local_daily(values, operations=()):
    """Hourly legacy data resampled by #48 to Sao Paulo days, then processed."""
    hourly = source(
        [v for value in values for v in (value, value)],
        timestamps=[
            f"2024-01-{day + 1:02d}T{hour}Z"
            for day in range(len(values))
            for hour in ("04:00", "05:00")
        ],
    )
    hourly.pop("time_step")
    hourly["frequency"] = "hour"
    steps = [
        {
            "id": "local",
            "operation": "resample",
            "input": "hourly",
            "frequency": "daily",
            "timezone": SAO_PAULO,
        },
        *operations,
    ]
    response = process_series({"series": {"hourly": hourly}, "operations": steps})
    return response["series"][steps[-1]["id"]]


def map_of(series_by_variable, **settings):
    return build_correlation_map(
        {
            "variables": list(series_by_variable),
            "area": "test",
            "period": {"start": "2024-01-01", "end": "2024-01-03"},
            **settings,
        },
        loader=lambda selection, period: copy.deepcopy(
            series_by_variable[selection["variable"]]
        ),
    )


def test_prepared_local_zone_derived_series_is_eligible_in_its_own_zone():
    prepared = local_daily([1, 2, 4])
    legacy = source([3, 2, 1], timestamps=[f"2024-01-0{d}T03:00Z" for d in (1, 2, 3)])
    legacy.pop("time_step")
    legacy["frequency"] = "day"

    result = map_of(
        {"prepared": prepared, "legacy": legacy}, time_step="daily", timezone=SAO_PAULO
    )

    assert [item["variable"] for item in result["inputs"]] == ["prepared", "legacy"]
    assert result["excluded"] == []
    assert result["timestamps"] == [f"2024-01-0{d}T03:00:00+00:00" for d in (1, 2, 3)]
    assert result["inputs"][0]["metadata"]["resampling"]["timezone"] == SAO_PAULO
    assert result["settings"]["timezone"] == SAO_PAULO


def test_processing_after_local_resampling_keeps_the_confirmed_zone():
    scaled = local_daily(
        [1, 2, 4],
        [{"id": "scaled", "expression": "2 * local"}],
    )
    other = local_daily([4, 1, 3])

    result = map_of({"scaled": scaled, "other": other}, timezone=SAO_PAULO)

    assert result["excluded"] == []
    assert result["settings"]["time_step"] == "daily"
    provenance = result["inputs"][0]["metadata"]["provenance"]["local"]
    assert provenance["resampling"]["timezone"] == SAO_PAULO


def test_prepared_local_days_resample_to_local_months_in_the_same_zone():
    january = local_daily([1, 2, 4])
    prepared = {
        **january,
        "timestamps": january["timestamps"] + ["2024-02-01T00:00:00-03:00"],
        "values": january["values"] + [9],
        "filled": january["filled"] + [False],
    }
    other = copy.deepcopy(prepared)
    other["values"] = [5, 5, 5, 1]

    result = build_correlation_map(
        {
            "variables": ["A", "B"],
            "area": "test",
            "period": {"start": "2024-01", "end": "2024-02"},
            "time_step": "monthly",
            "timezone": SAO_PAULO,
        },
        loader=lambda selection, period: copy.deepcopy(
            prepared if selection["variable"] == "A" else other
        ),
    )

    assert result["timestamps"] == [
        "2024-01-01T03:00:00+00:00",
        "2024-02-01T03:00:00+00:00",
    ]
    assert result["matrix"] == [[1, -1], [-1, 1]]


@pytest.mark.parametrize("timezone", ["UTC", "Europe/Lisbon"])
def test_prepared_local_series_is_not_rebucketed_into_another_zone(timezone):
    prepared = local_daily([1, 2, 4])
    other = local_daily([4, 1, 3])

    with pytest.raises(ProcessingError) as error:
        map_of({"prepared": prepared, "other": other}, timezone=timezone)

    assert error.value.code == "invalid_timezone"
    assert error.value.details["input"] == "input_0"
    assert SAO_PAULO in str(error.value)


def test_acquired_time_steps_still_follow_utc_in_a_local_map():
    with pytest.raises(ProcessingError) as error:
        map_of({"A": source([1, 2, 3]), "B": source([3, 1, 2])}, timezone=SAO_PAULO)

    assert error.value.code == "invalid_timezone"
    assert "UTC" in str(error.value)
