"""Precipitation arrives from MERRA-2 as a monthly mean rate and is shown to
students as a monthly total. These tests pin the conversion month by month."""

from __future__ import annotations

import math

import pytest

from engine.units import (
    MERRA2_FILL_VALUE,
    PRECIPITATION_RATE_UNITS,
    precipitation_rate_to_monthly_total,
    seconds_in_month,
)

RATE = PRECIPITATION_RATE_UNITS
DAY = 86_400


def convert(rates, start="2001-01", units=RATE):
    return precipitation_rate_to_monthly_total(rates, start, units)


def test_a_rate_becomes_the_total_for_a_31_day_month():
    # 1e-5 kg m-2 s-1 over 31 days is 1e-5 x 86,400 x 31 = 26.784 mm.
    assert convert([1e-5], "2001-01") == [pytest.approx(26.784, rel=1e-12)]


def test_each_month_uses_its_own_length():
    totals = convert([1e-5] * 4, "2001-01")
    assert totals == [
        pytest.approx(1e-5 * DAY * 31, rel=1e-12),  # January
        pytest.approx(1e-5 * DAY * 28, rel=1e-12),  # February 2001
        pytest.approx(1e-5 * DAY * 31, rel=1e-12),  # March
        pytest.approx(1e-5 * DAY * 30, rel=1e-12),  # April
    ]


def test_leap_februaries_follow_the_gregorian_rules():
    assert seconds_in_month(2000, 2) == 29 * DAY  # divisible by 400: leap
    assert seconds_in_month(2004, 2) == 29 * DAY  # divisible by 4: leap
    assert seconds_in_month(2001, 2) == 28 * DAY
    assert seconds_in_month(1900, 2) == 28 * DAY  # divisible by 100 only: not leap
    leap, plain = convert([1e-5], "2000-02")[0], convert([1e-5], "2001-02")[0]
    assert leap / plain == pytest.approx(29 / 28, rel=1e-12)


def test_months_stay_aligned_across_a_year_boundary():
    totals = convert([1e-5] * 4, "2000-11")
    days = [round(total / (1e-5 * DAY)) for total in totals]
    assert days == [30, 31, 31, 28]  # Nov 2000, Dec 2000, Jan 2001, Feb 2001


def test_the_whole_study_period_adds_up_to_its_9132_days():
    # 2000-01 to 2024-12 is 25 years, 7 of them leap: 25 x 365 + 7 = 9,132 days.
    totals = convert([1e-5] * 300, "2000-01")
    assert len(totals) == 300
    assert sum(totals) == pytest.approx(1e-5 * DAY * 9132, rel=1e-12)


def test_a_typical_wet_month_lands_in_a_realistic_range():
    # 1e-4 kg m-2 s-1 is about 8.6 mm a day: a very wet tropical month.
    assert convert([1e-4], "2001-04")[0] == pytest.approx(259.2, rel=1e-12)


def test_dividing_by_the_month_gives_back_the_rate():
    rates = [3.7e-6, 1.2e-5, 0.0, 8.9e-5]
    totals = convert(rates, "2003-12")
    months = [(2003, 12), (2004, 1), (2004, 2), (2004, 3)]
    for rate, total, (year, month) in zip(rates, totals, months):
        assert total / seconds_in_month(year, month) == pytest.approx(rate, rel=1e-12)


@pytest.mark.parametrize(
    "missing",
    [None, math.nan, math.inf, -math.inf, MERRA2_FILL_VALUE, 999999986991104.0],
    ids=["none", "nan", "inf", "-inf", "fill", "fill-read-as-float64"],
)
def test_a_missing_month_stays_missing(missing):
    assert convert([1e-5, missing, 1e-5], "2001-01")[1] is None


def test_missing_months_do_not_shift_the_ones_after_them():
    totals = convert([None, 1e-5], "2001-01")
    assert totals[0] is None
    assert totals[1] == pytest.approx(1e-5 * DAY * 28, rel=1e-12)  # still February


def test_zero_rain_is_a_real_zero_not_missing():
    assert convert([0.0], "2001-01") == [0.0]


@pytest.mark.parametrize("units", ["mm/month", "mm/day", "mm", "kg m-2"])
def test_other_units_are_refused_so_nothing_is_converted_twice(units):
    with pytest.raises(ValueError, match="expected precipitation"):
        convert([1e-5], units=units)


def test_the_units_may_be_spaced_differently():
    assert convert([1e-5], units="kg  m-2   s-1")[0] == pytest.approx(26.784)


def test_a_negative_rate_is_refused():
    with pytest.raises(ValueError, match="negative precipitation rate"):
        convert([1e-5, -2e-6], "2001-01")


def test_millimetres_per_day_labelled_as_a_rate_are_caught():
    # 5 mm a day passed as 5 kg m-2 s-1 would become about 13.4 million mm.
    with pytest.raises(ValueError, match="wetter than any month ever recorded"):
        convert([5.0], "2001-01")


@pytest.mark.parametrize("start", ["2001-13", "2001-00", "2001-1", "01-2001", "2001"])
def test_a_malformed_start_month_is_refused(start):
    with pytest.raises(ValueError, match="YYYY-MM"):
        convert([1e-5], start)


def test_the_input_is_left_untouched():
    rates = [1e-5, None, 2e-5]
    convert(rates, "2001-01")
    assert rates == [1e-5, None, 2e-5]
