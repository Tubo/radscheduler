from datetime import date, timedelta

from radscheduler.roster.assigner import AutoAssigner
from radscheduler.roster.generator import generate_shifts
from radscheduler.roster.models import Leave, LeaveType, Shift, ShiftType, Status, StatusType, Weekday
from radscheduler.roster.rosters import SingleOnCallRoster
from radscheduler.roster.utils import daterange, generate_leaves, shift_breakdown, shifts_to_dataframe
from radscheduler.roster.validators import StonzMecaValidator


def test_not_on_leave(juniors):
    leaves = generate_leaves(date(2023, 1, 2), date(2023, 1, 22), LeaveType.ANNUAL, juniors[0])
    shifts = generate_shifts(SingleOnCallRoster, date(2023, 1, 2), date(2023, 1, 22))
    validator = StonzMecaValidator(shift=shifts[0], registrar=juniors[0], shifts=shifts, leaves=leaves)
    assert validator.validate_not_on_leave() == False

    leaves = Leave(date=date(2024, 2, 29), type=LeaveType.ANNUAL, registrar=juniors[0])
    shifts = [
        Shift(date=date(2024, 2, 26), type=ShiftType.NIGHT),
        Shift(date=date(2024, 2, 27), type=ShiftType.NIGHT),
        Shift(date=date(2024, 2, 28), type=ShiftType.NIGHT),
    ]
    validator = StonzMecaValidator(shift=shifts[0], registrar=juniors[0], shifts=shifts, leaves=[leaves])
    assert validator.validate_not_on_leave() == False

    leave = Leave(date=date(2024, 2, 29), type=LeaveType.ANNUAL, registrar=juniors[0])
    shifts = [
        Shift(date=date(2024, 2, 26), type=ShiftType.NIGHT),
        Shift(date=date(2024, 2, 27), type=ShiftType.NIGHT),
        Shift(date=date(2024, 2, 28), type=ShiftType.NIGHT),
        Shift(date=date(2024, 2, 29), type=ShiftType.NIGHT),
    ]
    validator = StonzMecaValidator(shift=shifts[0], registrar=juniors[0], shifts=shifts, leaves=[leave])
    assert validator.validate_not_on_leave() == False


def test_no_weekend_shift_abutting_leaves(juniors, seniors):
    # todo: simplify this test
    # add no_abutting_weekend test
    leaves = generate_leaves(date(2023, 1, 2), date(2024, 1, 2), LeaveType.ANNUAL, juniors[0])
    mon_leaves = list(filter(lambda l: l.date.weekday() == Weekday.MON, leaves))
    fri_leaves = list(filter(lambda l: l.date.weekday() == Weekday.FRI, leaves))

    # If taking leaves every Monday or Friday, then no weekend day or night shifts
    for day, leaves in [("Mon", mon_leaves), ("Fri", fri_leaves)]:
        shifts = generate_shifts(SingleOnCallRoster, date(2023, 1, 2), date(2023, 12, 31))
        assigner = AutoAssigner(registrars=juniors + seniors, unfilled=shifts, leaves=leaves)

        result = assigner.fill_roster()
        breakdown = shift_breakdown(shifts_to_dataframe(result))
        j1_shifts = list(filter(lambda s: s.registrar == juniors[0], result))

        weekend_shifts = list(filter(lambda s: (s.type == ShiftType.LONG) and s.is_weekend, j1_shifts))
        assert list(weekend_shifts) == [], f"No weekend day shifts abutting {day} leave"

        weekend_nights_assignments = list(filter(lambda s: (s.type == ShiftType.NIGHT) and s.is_weekend, j1_shifts))
        assert weekend_nights_assignments == [], f"No weekend night shifts abutting {day} leave"


def test_no_gt_2_long_days_in_7(juniors):
    shifts = [
        Shift(date=date(2023, 12, 23), type=ShiftType.LONG),
        Shift(date=date(2023, 12, 24), type=ShiftType.LONG, registrar=juniors[0]),
        Shift(date=date(2023, 12, 25), type=ShiftType.LONG, registrar=juniors[0]),
    ]
    for shift in shifts:
        validator = StonzMecaValidator(shift=shift, registrar=juniors[0], shifts=shifts)
        assert validator.validate_no_gt_2_long_days_in_7() == False

    shifts = [
        Shift(date=date(2024, 3, 14), type=ShiftType.LONG, registrar=juniors[0]),
        Shift(date=date(2024, 3, 16), type=ShiftType.LONG),
    ]
    validator = StonzMecaValidator(shift=shifts[1], registrar=juniors[0], shifts=shifts)
    assert validator.validate_no_gt_2_long_days_in_7() == False


def test_one_shift_per_day(juniors):
    shifts = [
        Shift(date=date(2023, 12, 23), type=ShiftType.NIGHT, registrar=juniors[0]),
        Shift(date=date(2023, 12, 23), type=ShiftType.LONG, registrar=juniors[0]),
    ]
    for shift in shifts:
        validator = StonzMecaValidator(shift=shift, registrar=juniors[0], shifts=shifts)
        assert validator.validate_one_shift_per_day() == False


def test_validate_roster():
    pass
