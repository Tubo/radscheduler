from datetime import date

from radscheduler.roster.models import Leave, LeaveType, Shift, ShiftType
from radscheduler.roster.utils import generate_leaves
from radscheduler.roster.validators import StonzMecaValidator


def test_not_on_leave(juniors):
    leaves = generate_leaves(date(2023, 1, 2), date(2023, 1, 22), LeaveType.ANNUAL, juniors[0])
    shifts = [Shift(date=date(2023, 1, 2), type=ShiftType.LONG)]
    validator = StonzMecaValidator(shift=shifts[0], registrar=juniors[0], shifts=shifts, leaves=leaves)
    assert validator.validate_not_on_leave() is False

    leaves = Leave(date=date(2024, 2, 29), type=LeaveType.ANNUAL, registrar=juniors[0])
    shifts = [
        Shift(date=date(2024, 2, 26), type=ShiftType.NIGHT),
        Shift(date=date(2024, 2, 27), type=ShiftType.NIGHT),
        Shift(date=date(2024, 2, 28), type=ShiftType.NIGHT),
    ]
    validator = StonzMecaValidator(shift=shifts[0], registrar=juniors[0], shifts=shifts, leaves=[leaves])
    assert validator.validate_not_on_leave() is False

    leave = Leave(date=date(2024, 2, 29), type=LeaveType.ANNUAL, registrar=juniors[0])
    shifts = [
        Shift(date=date(2024, 2, 26), type=ShiftType.NIGHT),
        Shift(date=date(2024, 2, 27), type=ShiftType.NIGHT),
        Shift(date=date(2024, 2, 28), type=ShiftType.NIGHT),
        Shift(date=date(2024, 2, 29), type=ShiftType.NIGHT),
    ]
    validator = StonzMecaValidator(shift=shifts[0], registrar=juniors[0], shifts=shifts, leaves=[leave])
    assert validator.validate_not_on_leave() is False


def test_no_weekend_shift_abutting_leaves(juniors):
    def is_valid(shift, leave_date):
        leave = Leave(date=leave_date, type=LeaveType.ANNUAL, registrar=juniors[0])
        validator = StonzMecaValidator(shift=shift, registrar=juniors[0], shifts=[], leaves=[leave])
        return validator.validate_no_weekend_abutting_leave()

    monday, friday = date(2023, 1, 9), date(2023, 1, 13)

    # Leave on Monday 9 Jan rules out the weekend before it, including Friday night
    assert is_valid(Shift(date=date(2023, 1, 7), type=ShiftType.LONG), monday) is False
    assert is_valid(Shift(date=date(2023, 1, 8), type=ShiftType.LONG), monday) is False
    assert is_valid(Shift(date=date(2023, 1, 6), type=ShiftType.NIGHT), monday) is False
    # Friday long day is not part of the weekend
    assert is_valid(Shift(date=date(2023, 1, 6), type=ShiftType.LONG), monday) is True

    # Leave on Friday 13 Jan rules out the weekend after it
    assert is_valid(Shift(date=date(2023, 1, 14), type=ShiftType.LONG), friday) is False
    assert is_valid(Shift(date=date(2023, 1, 15), type=ShiftType.LONG), friday) is False

    # A weekend not next to the leave is fine
    assert is_valid(Shift(date=date(2023, 1, 21), type=ShiftType.LONG), monday) is True


def test_no_gt_2_long_days_in_7(juniors):
    shifts = [
        Shift(date=date(2023, 12, 23), type=ShiftType.LONG),
        Shift(date=date(2023, 12, 24), type=ShiftType.LONG, registrar=juniors[0]),
        Shift(date=date(2023, 12, 25), type=ShiftType.LONG, registrar=juniors[0]),
    ]
    for shift in shifts:
        validator = StonzMecaValidator(shift=shift, registrar=juniors[0], shifts=shifts)
        assert validator.validate_no_gt_2_long_days_in_7() is False

    shifts = [
        Shift(date=date(2024, 3, 14), type=ShiftType.LONG, registrar=juniors[0]),
        Shift(date=date(2024, 3, 16), type=ShiftType.LONG),
    ]
    validator = StonzMecaValidator(shift=shifts[1], registrar=juniors[0], shifts=shifts)
    assert validator.validate_no_gt_2_long_days_in_7() is False


def test_one_shift_per_day(juniors):
    shifts = [
        Shift(date=date(2023, 12, 23), type=ShiftType.NIGHT, registrar=juniors[0]),
        Shift(date=date(2023, 12, 23), type=ShiftType.LONG, registrar=juniors[0]),
    ]
    for shift in shifts:
        validator = StonzMecaValidator(shift=shift, registrar=juniors[0], shifts=shifts)
        assert validator.validate_one_shift_per_day() is False
