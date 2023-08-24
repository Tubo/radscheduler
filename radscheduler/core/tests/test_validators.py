from functools import partial
from datetime import date, timedelta
import pytest
import holidays
import statistics

from radscheduler.core.models import ShiftType, LeaveType, Status, StatusType, Weekday
from radscheduler.core.roster import filter_assignments_by_date_and_shift_type
from radscheduler.core.logic import (
    Assignment,
    DefaultRoster,
    generate_leaves,
    filter_shifts_by_date,
    filter_shifts_by_types,
    filter_shifts_by_date_and_type,
    assignment_shift_breakdown,
    registrar_assignment_date_distance,
)


def test_no_weekend_shift_abutting_leaves(juniors, seniors):
    leaves = generate_leaves(
        date(2023, 1, 2), date(2024, 1, 2), LeaveType.ANNUAL, juniors[0]
    )
    roster = DefaultRoster(registrars=juniors + seniors)
    roster.generate_shifts(date(2023, 1, 2), date(2023, 12, 31))

    mon_leaves = list(filter(lambda l: l.date.weekday() == Weekday.MON, leaves))
    fri_leaves = list(filter(lambda l: l.date.weekday() == Weekday.FRI, leaves))

    # If taking leaves every Monday or Friday, then no weekend day or night shifts
    for day, leaves in [("Mon", mon_leaves), ("Fri", fri_leaves)]:
        roster.leaves = leaves
        assignments = roster.fill_roster()
        shift_breakdown = assignment_shift_breakdown(assignments)

        junior1_assignments = list(
            filter(lambda a: a.registrar == juniors[0], assignments)
        )

        weekend_assignments = list(
            filter(lambda a: a.shift.type == ShiftType.WEEKEND, junior1_assignments)
        )
        assert (
            list(weekend_assignments) == []
        ), f"No weekend day shifts abutting {day} leave"

        weekend_nights_assignments = list(
            filter(
                lambda a: (a.shift.type == ShiftType.NIGHT)
                and (a.shift.date.weekday() in [Weekday.FRI, Weekday.SAT, Weekday.SUN]),
                junior1_assignments,
            )
        )

        assert (
            weekend_nights_assignments == []
        ), f"No weekend night shifts abutting {day} leave"
