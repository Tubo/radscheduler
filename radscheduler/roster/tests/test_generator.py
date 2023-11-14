from datetime import date

from radscheduler.roster.generator import canterbury_holidays, generate_shifts, merge_shifts
from radscheduler.roster.models import Shift, ShiftType
from radscheduler.roster.rosters import SingleOnCallRoster
from radscheduler.roster.utils import (
    filter_shifts,
    filter_shifts_by_date,
    filter_shifts_by_types,
    find_registrar_from_shifts,
)


def test_generate_usual_shifts():
    """
    Test that the numbers of generated shifts per day are correct.
    """
    shifts = generate_shifts(SingleOnCallRoster, date(2023, 1, 2), date(2023, 1, 22))

    mon = filter_shifts_by_date(shifts, date(2023, 1, 9))
    assert len(mon) == 4, "Monday: LONG, NIGHT, RDO, SLEEP"

    tue = filter_shifts_by_date(shifts, date(2023, 1, 10))
    assert len(tue) == 4, "Tuesday: same as Monday"

    wed = filter_shifts_by_date(shifts, date(2023, 1, 11))
    assert len(wed) == 2, "Wednesday: LONG, NIGHT"

    thur = filter_shifts_by_date(shifts, date(2023, 1, 12))
    assert len(thur) == 3, "Thursday: LONG, NIGHT, RDO"

    fri = filter_shifts_by_date(shifts, date(2023, 1, 13))
    assert len(fri) == 4, "Friday: LONG, NIGHT, RDO, SLEPP"

    sat = filter_shifts_by_date(shifts, date(2023, 1, 14))
    assert len(sat) == 3, "Saturday: WEEKEND, NIGHT, SLEEP"

    sun = filter_shifts_by_date(shifts, date(2023, 1, 15))
    assert len(sun) == 3, "Sunday: WEEKEND, NIGHT, SLEEP"


def test_generate_double_oncall():
    # Ensures flexibility for double oncall
    DoubleOnCall = SingleOnCallRoster
    DoubleOnCall.TUE = ((ShiftType.LONG, 2), (ShiftType.NIGHT, 2))
    shifts = generate_shifts(DoubleOnCall, date(2023, 1, 2), date(2023, 1, 22))
    day = filter_shifts(shifts, date(2023, 1, 3), ShiftType.LONG)  # Tuesday
    assert len(day) == 2, "Double oncall on Tuesday"
    assert day[0].series != day[1].series, "Different series"


def test_mark_stat_day_in_generated_shifts():
    # todo: unpredictability of this test... investigate later
    shifts = generate_shifts(SingleOnCallRoster, date(2022, 12, 22), date(2022, 12, 29))

    # 24th is Saturday, not a stat day. Only NIGHT should be stat_day
    day_24 = filter_shifts_by_date(shifts, date(2022, 12, 24))
    weekend = filter_shifts_by_types(day_24, [ShiftType.LONG])
    assert not any([shift.stat_day for shift in weekend])
    nights = filter_shifts_by_types(day_24, [ShiftType.NIGHT])
    assert nights[0].stat_day
    sleep = filter_shifts_by_types(day_24, [ShiftType.SLEEP])
    assert not sleep[0].stat_day

    # 25th is Sunday and Christmas day, WEEKEND, NIGHT should be stat_day, but not SLEEP
    day_25 = filter_shifts_by_date(shifts, date(2022, 12, 25))
    weekend_and_nights = filter_shifts_by_types(day_25, [ShiftType.LONG, ShiftType.NIGHT])
    assert all([shift.stat_day for shift in weekend_and_nights])
    sleep = filter_shifts_by_types(day_25, [ShiftType.SLEEP])
    assert not sleep[0].stat_day

    # 26th is Monday and Boxing day and Christmas holiday, every shift is stat_day
    day_26 = filter_shifts_by_date(shifts, date(2022, 12, 26))
    assert len([shift.stat_day for shift in day_26 if shift.stat_day]) == 3, "not SLEEP"

    # 27th is Tuesday and Boxing holiday, every shift is stat_day
    day_27 = filter_shifts_by_date(shifts, date(2022, 12, 27))
    assert len([shift.stat_day for shift in day_27 if shift.stat_day]) == 3, "not SLEEP"


def test_2022_holidays():
    # Use 2022 Christmas holidays as an example to test holidays.NZ
    assert date(2022, 12, 24) not in canterbury_holidays, "Not a holiday"
    assert date(2022, 12, 25) in canterbury_holidays, "Christmas Day on Sunday"
    assert date(2022, 12, 26) in canterbury_holidays, "Boxing day but Christmas holiday"
    assert date(2022, 12, 27) in canterbury_holidays, "Boxing holiday"
    assert date(2022, 12, 28) not in canterbury_holidays, "Not a holiday"

    # Use 2022 Canterbury anniversary as an example to test holidays.NZ
    assert date(2022, 11, 11) in canterbury_holidays, "Canterbury anniversary"


def test_only_generate_unfilled_shifts(juniors):
    """
    If the generate_shifts function is given a list of filled shifts, then those filled shifts should not be generated.
    """
    filled = [
        Shift(date(2023, 1, 2), ShiftType.LONG, registrar=juniors[0]),
        Shift(date(2023, 1, 4), ShiftType.LONG, registrar=juniors[0]),
    ]
    result = generate_shifts(SingleOnCallRoster, date(2023, 1, 2), date(2023, 1, 4), filled=filled)
    assert filter_shifts(result, date(2023, 1, 2), ShiftType.LONG) == []
    assert filter_shifts(result, date(2023, 1, 4), ShiftType.LONG) == []


def test_merge_shifts(juniors):
    filled = [
        Shift(date(2023, 1, 2), ShiftType.LONG, registrar=juniors[0]),
        Shift(date(2023, 1, 3), ShiftType.LONG, series=1),
        Shift(date(2023, 1, 4), ShiftType.LONG, series=2, registrar=juniors[0]),
    ]
    unfilled = generate_shifts(SingleOnCallRoster, date(2023, 1, 2), date(2023, 1, 5))
    result = merge_shifts(filled, unfilled)
    assert len(result) == len(unfilled) + 1
    assert find_registrar_from_shifts(result, date(2023, 1, 2), ShiftType.LONG) == juniors[0]
