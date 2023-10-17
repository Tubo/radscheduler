from datetime import date, timedelta

from radscheduler.roster.assigner import AutoAssigner
from radscheduler.roster.generator import SingleOnCallRoster
from radscheduler.roster.models import LeaveType, Shift, ShiftType, Status, StatusType, Weekday
from radscheduler.roster.utils import generate_leaves, shift_breakdown, shifts_to_dataframe


def test_no_weekend_shift_abutting_leaves(juniors, seniors):
    leaves = generate_leaves(date(2023, 1, 2), date(2024, 1, 2), LeaveType.ANNUAL, juniors[0])
    mon_leaves = list(filter(lambda l: l.date.weekday() == Weekday.MON, leaves))
    fri_leaves = list(filter(lambda l: l.date.weekday() == Weekday.FRI, leaves))

    # If taking leaves every Monday or Friday, then no weekend day or night shifts
    for day, leaves in [("Mon", mon_leaves), ("Fri", fri_leaves)]:
        shifts = SingleOnCallRoster().generate_shifts(date(2023, 1, 2), date(2023, 12, 31))
        assigner = AutoAssigner(registrars=juniors + seniors, future_shifts=shifts, leaves=leaves)

        result = assigner.fill_roster()
        breakdown = shift_breakdown(shifts_to_dataframe(result))
        j1_shifts = list(filter(lambda s: s.registrar == juniors[0], result))

        weekend_shifts = list(filter(lambda s: (s.type == ShiftType.LONG) and s.is_weekend, j1_shifts))
        assert list(weekend_shifts) == [], f"No weekend day shifts abutting {day} leave"

        weekend_nights_assignments = list(filter(lambda s: (s.type == ShiftType.NIGHT) and s.is_weekend, j1_shifts))
        assert weekend_nights_assignments == [], f"No weekend night shifts abutting {day} leave"


def test_no_gt_2_long_days_in_7():
    pass
