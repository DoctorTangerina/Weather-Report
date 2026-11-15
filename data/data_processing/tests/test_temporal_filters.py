"""#52 / #46 BS-012: explicit temporal filters at S1 (``process_series``).

Endpoint convention (agreed for #52): a local time-of-day window includes its
start and excludes its end; a custom date window includes both dates. Daily and
monthly Series are read on their UTC calendar labels.
"""

import copy

import pytest

from data.data_processing import ProcessingError, process_series


def hourly(timestamps, values=None, **extra):
    return {
        "timestamps": timestamps,
        "values": values or [float(i + 1) for i in range(len(timestamps))],
        "units": "K",
        "time_step": "hourly",
        **extra,
    }


def apply(series, **step):
    return process_series(
        {
            "series": {"A": series},
            "operations": [
                {"id": "sample", "operation": "filter", "input": "A", **step}
            ],
        }
    )


def test_overnight_window_includes_observations_on_both_sides_of_midnight():
    response = apply(
        hourly(
            [
                "2024-01-01T19:00:00Z",
                "2024-01-02T02:00:00Z",
                "2024-01-02T12:00:00Z",
            ],
            [10.0, 20.0, 30.0],
        ),
        timezone="UTC",
        mode="include",
        hours={"start": "18:00", "end": "06:00"},
    )
    sample = response["series"]["sample"]
    assert sample["timestamps"] == ["2024-01-01T19:00:00Z", "2024-01-02T02:00:00Z"]
    assert sample["values"] == [10.0, 20.0]
    assert sample["temporal_filter"]["excluded_timestamps"] == ["2024-01-02T12:00:00Z"]


def test_local_time_window_is_read_in_the_inputs_confirmed_time_zone():
    # 23:00 UTC on 2024-01-01 is 20:00 in Sao Paulo, outside 06:00-18:00 there,
    # although 23:00 is also outside it in UTC; 12:00 UTC (09:00 local) is the
    # observation a UTC reading would also keep, and 20:00 UTC (17:00 local) is
    # the one only the local reading keeps.
    response = apply(
        hourly(
            [
                "2024-01-01T12:00:00Z",
                "2024-01-01T20:00:00Z",
                "2024-01-01T23:00:00Z",
            ]
        ),
        timezone="America/Sao_Paulo",
        mode="include",
        hours={"start": "06:00", "end": "18:00"},
    )
    sample = response["series"]["sample"]
    assert sample["timestamps"] == ["2024-01-01T12:00:00Z", "2024-01-01T20:00:00Z"]
    assert "2024-01-01T23:00:00Z" in sample["temporal_filter"]["excluded_timestamps"]


def test_repeated_local_hour_keeps_both_observed_instants_with_their_utc_identity():
    # On 2024-11-03 New York falls back: 05:30 UTC and 06:30 UTC are both 01:30
    # local. 07:30 UTC (02:30 local) lies outside the window.
    response = apply(
        hourly(
            [
                "2024-11-03T05:30:00Z",
                "2024-11-03T06:30:00Z",
                "2024-11-03T07:30:00Z",
            ]
        ),
        timezone="America/New_York",
        mode="include",
        hours={"start": "01:00", "end": "02:00"},
    )
    sample = response["series"]["sample"]
    assert sample["timestamps"] == ["2024-11-03T05:30:00Z", "2024-11-03T06:30:00Z"]
    assert sample["values"] == [1.0, 2.0]


@pytest.mark.parametrize(
    ("selection", "retained", "excluded"),
    [
        ({"weekdays": ["monday"]}, "2024-01-01T12:00:00Z", "2024-01-02T12:00:00Z"),
        ({"months": [1]}, "2024-01-15T12:00:00Z", "2024-02-15T12:00:00Z"),
        (
            {"dates": {"start": "2024-01-10", "end": "2024-01-12"}},
            "2024-01-11T12:00:00Z",
            "2024-01-13T12:00:00Z",
        ),
    ],
    ids=["mondays", "january", "date-window"],
)
def test_calendar_filter_retains_only_the_selected_observation(
    selection, retained, excluded
):
    response = apply(
        hourly([retained, excluded]), timezone="UTC", mode="include", **selection
    )
    sample = response["series"]["sample"]
    assert sample["timestamps"] == [retained]
    assert sample["temporal_filter"]["excluded_timestamps"] == [excluded]


def coarse(time_step, timestamps):
    return {
        "timestamps": timestamps,
        "values": [1.0] * len(timestamps),
        "units": "K",
        "time_step": time_step,
    }


MONTHLY = ["2024-01-01", "2024-02-01", "2024-03-01"]
DAILY = ["2024-01-01", "2024-01-02", "2024-01-03"]


@pytest.mark.parametrize(
    ("time_step", "timestamps", "selection"),
    [
        ("monthly", MONTHLY, {"hours": {"start": "06:00", "end": "18:00"}}),
        ("daily", DAILY, {"hours": {"start": "06:00", "end": "18:00"}}),
        ("monthly", MONTHLY, {"weekdays": ["monday"]}),
        ("monthly", MONTHLY, {"dates": {"start": "2024-01-10", "end": "2024-01-12"}}),
    ],
    ids=["hours-monthly", "hours-daily", "weekdays-monthly", "dates-monthly"],
)
def test_filter_finer_than_the_input_time_step_is_refused_with_an_explanation(
    time_step, timestamps, selection
):
    with pytest.raises(ProcessingError) as error:
        apply(
            coarse(time_step, timestamps), timezone="UTC", mode="include", **selection
        )
    assert error.value.code == "unsupported_temporal_resolution"
    assert time_step in str(error.value)
    assert error.value.details["time_step"] == time_step


def test_filter_needs_the_inputs_declared_time_step_rather_than_guessing_it():
    undeclared = {
        "timestamps": ["2024-01-01T19:00:00Z", "2024-01-02T02:00:00Z"],
        "values": [1.0, 2.0],
        "units": "K",
    }
    with pytest.raises(ProcessingError) as error:
        apply(
            undeclared,
            timezone="UTC",
            mode="include",
            hours={"start": "18:00", "end": "06:00"},
        )
    assert error.value.code == "unknown_time_step"


@pytest.mark.parametrize(
    ("time_step", "selection", "retained", "excluded"),
    [
        # 2024-02-01T00:00Z is still January 31 in Sao Paulo; the monthly label
        # names February, and February is what the filter reads.
        ("monthly", {"months": [2]}, "2024-02-01", "2024-01-01"),
        # 2024-01-01 (UTC) is a Monday, though Sunday evening in Sao Paulo.
        ("daily", {"weekdays": ["monday"]}, "2024-01-01", "2024-01-02"),
        (
            "daily",
            {"dates": {"start": "2024-01-02", "end": "2024-01-02"}},
            "2024-01-02",
            "2024-01-03",
        ),
    ],
    ids=["monthly-month", "daily-weekday", "daily-date"],
)
def test_daily_and_monthly_inputs_are_read_on_their_utc_calendar_labels(
    time_step, selection, retained, excluded
):
    response = apply(
        coarse(time_step, sorted([retained, excluded])),
        timezone="America/Sao_Paulo",
        mode="include",
        **selection,
    )
    sample = response["series"]["sample"]
    assert sample["timestamps"] == [retained]
    assert sample["temporal_filter"]["excluded_timestamps"] == [excluded]


def test_time_of_day_window_includes_its_start_and_excludes_its_end():
    response = apply(
        hourly(
            [
                "2024-01-01T06:00:00Z",
                "2024-01-01T18:00:00Z",
                "2024-01-02T05:00:00Z",
                "2024-01-02T06:00:00Z",
            ]
        ),
        timezone="UTC",
        mode="include",
        hours={"start": "18:00", "end": "06:00"},
    )
    sample = response["series"]["sample"]
    assert sample["timestamps"] == ["2024-01-01T18:00:00Z", "2024-01-02T05:00:00Z"]

    daytime = apply(
        hourly(
            ["2024-01-01T06:00:00Z", "2024-01-01T17:00:00Z", "2024-01-01T18:00:00Z"]
        ),
        timezone="UTC",
        mode="include",
        hours={"start": "06:00", "end": "18:00"},
    )["series"]["sample"]
    assert daytime["timestamps"] == ["2024-01-01T06:00:00Z", "2024-01-01T17:00:00Z"]


def test_date_window_includes_the_whole_of_both_dates():
    response = apply(
        hourly(
            [
                "2024-01-09T23:00:00Z",
                "2024-01-10T00:00:00Z",
                "2024-01-12T23:00:00Z",
                "2024-01-13T00:00:00Z",
            ]
        ),
        timezone="UTC",
        mode="include",
        dates={"start": "2024-01-10", "end": "2024-01-12"},
    )
    sample = response["series"]["sample"]
    assert sample["timestamps"] == ["2024-01-10T00:00:00Z", "2024-01-12T23:00:00Z"]


def test_exclude_mode_drops_observations_matching_every_condition():
    # Monday nights are dropped; Monday noon and Tuesday night are kept.
    response = apply(
        hourly(
            [
                "2024-01-01T12:00:00Z",
                "2024-01-01T22:00:00Z",
                "2024-01-02T22:00:00Z",
            ],
            [1.0, 2.0, 3.0],
        ),
        timezone="UTC",
        mode="exclude",
        weekdays=["monday"],
        hours={"start": "18:00", "end": "06:00"},
    )
    sample = response["series"]["sample"]
    assert sample["timestamps"] == ["2024-01-01T12:00:00Z", "2024-01-02T22:00:00Z"]
    assert sample["values"] == [1.0, 3.0]
    assert sample["temporal_filter"]["mode"] == "exclude"
    assert sample["temporal_filter"]["excluded_timestamps"] == ["2024-01-01T22:00:00Z"]


NIGHT = {"hours": {"start": "18:00", "end": "06:00"}}


@pytest.mark.parametrize(
    ("step", "code"),
    [
        ({"mode": "include", **NIGHT}, "invalid_timezone"),
        (
            {"timezone": "Mars/Olympus_Mons", "mode": "include", **NIGHT},
            "invalid_timezone",
        ),
        ({"timezone": "UTC", **NIGHT}, "invalid_filter"),
        ({"timezone": "UTC", "mode": "include"}, "invalid_filter"),
        (
            {
                "timezone": "UTC",
                "mode": "include",
                "hours": {"start": "06:00", "end": "06:00"},
            },
            "invalid_filter",
        ),
        (
            {
                "timezone": "UTC",
                "mode": "include",
                "dates": {"start": "2024-01-12", "end": "2024-01-10"},
            },
            "invalid_filter",
        ),
    ],
    ids=[
        "no-time-zone",
        "unknown-time-zone",
        "no-mode",
        "no-condition",
        "empty-hours",
        "reversed-dates",
    ],
)
def test_filter_requires_a_confirmed_time_zone_a_mode_and_a_condition(step, code):
    with pytest.raises(ProcessingError) as error:
        apply(hourly(["2024-01-01T19:00:00Z"]), **step)
    assert error.value.code == code


def test_selected_months_feed_later_steps_with_recipe_and_unchanged_source_quality():
    # #46 BS-009 at phase two: choosing June-August leaves the other nine months
    # outside the sample, recorded as deliberate exclusions, never as missing.
    months = [f"2023-{month:02d}-01" for month in range(1, 13)]
    values = [float(month) for month in range(1, 13)]
    values[6] = None  # July is genuinely missing in the source.
    request = {
        "series": {
            "A": {
                "timestamps": months,
                "values": values,
                "units": "K",
                "time_step": "monthly",
                "aggregation": "mean",
                "quality": {"included": True, "missing_fraction": 0.1},
            }
        },
        "operations": [
            {
                "id": "summer",
                "operation": "filter",
                "input": "A",
                "timezone": "UTC",
                "mode": "include",
                "months": [6, 7, 8],
            },
            {"id": "doubled", "expression": "summer * 2"},
        ],
    }
    untouched = copy.deepcopy(request)
    response = process_series(request)
    summer = response["series"]["summer"]
    doubled = response["series"]["doubled"]

    assert request == untouched
    assert summer["timestamps"] == ["2023-06-01", "2023-07-01", "2023-08-01"]
    assert summer["values"] == [6.0, None, 8.0]
    assert summer["temporal_filter"]["excluded_timestamps"] == [
        months[i] for i in (0, 1, 2, 3, 4, 8, 9, 10, 11)
    ]
    assert summer["provenance"]["A"]["quality"] == {
        "included": True,
        "missing_fraction": 0.1,
    }
    assert summer["time_step"] == "monthly"
    assert summer["aggregation"] == "mean"
    assert summer["units"] == "K"

    assert doubled["timestamps"] == summer["timestamps"]
    assert doubled["values"] == [12.0, None, 16.0]
    assert [step["id"] for step in doubled["recipe"]["operations"]] == [
        "summer",
        "doubled",
    ]
    assert doubled["provenance"]["summer"]["temporal_filter"]["months"] == [6, 7, 8]

    replacement = copy.deepcopy(request["series"])
    replacement["A"]["values"] = [10.0 * v if v else None for v in values]
    replayed = process_series({"series": replacement, **response["recipe"]})
    assert replayed["series"]["doubled"]["values"] == [120.0, None, 160.0]


def test_filter_refuses_a_non_gregorian_calendar():
    series = hourly(["0001-01-01 19:00:00", "0001-01-02 02:00:00"], calendar="noleap")
    with pytest.raises(ProcessingError) as error:
        apply(series, timezone="UTC", mode="include", **NIGHT)
    assert error.value.code == "unsupported_calendar"


def test_retained_observations_keep_their_filled_flags():
    series = hourly(
        ["2024-01-01T12:00:00Z", "2024-01-01T19:00:00Z", "2024-01-02T02:00:00Z"],
        [1.0, 2.0, 3.0],
        filled=[False, False, True],
    )
    sample = apply(series, timezone="UTC", mode="include", **NIGHT)["series"]["sample"]
    assert sample["timestamps"] == ["2024-01-01T19:00:00Z", "2024-01-02T02:00:00Z"]
    assert sample["filled"] == [False, True]
