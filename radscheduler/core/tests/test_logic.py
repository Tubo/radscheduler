from functools import partial
from datetime import date, timedelta
import pytest
import holidays
import statistics

from radscheduler.core.models import ShiftType, LeaveType, Status, StatusType, Weekday
from radscheduler.core.validators import validate_assignments
from radscheduler.core.logic import (
    Assignment,
    generate_shifts,
    generate_leaves,
    filter_shifts_by_date,
    filter_shifts_by_types,
    filter_shifts_by_date_and_type,
    fill_roster,
    registrar_by_fatigue,
    assignment_shift_breakdown,
    registrar_assignment_date_distance,
)

FATIGUE_STDEV_THRESHOLD = 3


def fill_weekend_and_rdos(shifts, reg, saturday):
    prev_monday = saturday - timedelta(days=5)
    prev_tuesday = saturday - timedelta(days=4)
    sunday = saturday + timedelta(days=1)
    next_thurs = saturday + timedelta(days=5)
    next_fri = saturday + timedelta(days=6)

    monday_rdo = filter_shifts_by_date_and_type(shifts, prev_monday, ShiftType.WRDO)
    tuesday_rdo = filter_shifts_by_date_and_type(shifts, prev_tuesday, ShiftType.WRDO)
    saturday_shift = filter_shifts_by_date_and_type(shifts, saturday, ShiftType.WEEKEND)
    sunday_shift = filter_shifts_by_date_and_type(shifts, sunday, ShiftType.WEEKEND)
    thursday_rdo = filter_shifts_by_date_and_type(shifts, next_thurs, ShiftType.WRDO)
    friday_rdo = filter_shifts_by_date_and_type(shifts, next_fri, ShiftType.WRDO)

    return [
        Assignment(shift=monday_rdo[0], registrar=reg),
        Assignment(shift=tuesday_rdo[0], registrar=reg),
        Assignment(shift=saturday_shift[0], registrar=reg),
        Assignment(shift=sunday_shift[0], registrar=reg),
        Assignment(shift=thursday_rdo[0], registrar=reg),
        Assignment(shift=friday_rdo[0], registrar=reg),
    ]


def test_generate_usual_shifts():
    """
    Test that the numbers of generated shifts per day are correct.
    """
    shifts = generate_shifts(date(2023, 1, 2), date(2023, 1, 22))

    mon = filter_shifts_by_date(shifts, date(2023, 1, 9))
    assert len(mon) == 4, "Monday: LONG, NIGHT, WRDO, NRDO"

    tue = filter_shifts_by_date(shifts, date(2023, 1, 10))
    assert len(tue) == 4, "Tuesday: same as Monday"

    wed = filter_shifts_by_date(shifts, date(2023, 1, 11))
    assert len(wed) == 2, "Wednesday: LONG, NIGHT"

    thur = filter_shifts_by_date(shifts, date(2023, 1, 12))
    assert len(thur) == 3, "Thursday: LONG, NIGHT, WRDO"

    fri = filter_shifts_by_date(shifts, date(2023, 1, 13))
    assert len(fri) == 4, "Friday: LONG, NIGHT, WRDO, NRDO"

    sat = filter_shifts_by_date(shifts, date(2023, 1, 14))
    assert len(sat) == 3, "Saturday: WEEKEND, NIGHT, NRDO"

    sun = filter_shifts_by_date(shifts, date(2023, 1, 15))
    assert len(sun) == 3, "Sunday: WEEKEND, NIGHT, NRDO"


def test_mark_stat_day_in_generated_shifts():
    shifts = generate_shifts(date(2022, 12, 22), date(2022, 12, 29))

    # 24th is Saturday, not a stat day. Only NIGHT should be stat_day
    day_24 = filter_shifts_by_date(shifts, date(2022, 12, 24))
    weekend = filter_shifts_by_types(day_24, [ShiftType.WEEKEND])
    assert not any([shift.stat_day for shift in weekend])
    nights = filter_shifts_by_types(day_24, [ShiftType.NIGHT])
    assert nights[0].stat_day
    nrdo = filter_shifts_by_types(day_24, [ShiftType.NRDO])
    assert not nrdo[0].stat_day

    # 25th is Sunday and Christmas day, WEEKEND, NIGHT should be stat_day, but not NRDO
    day_25 = filter_shifts_by_date(shifts, date(2022, 12, 25))
    weekend_and_nights = filter_shifts_by_types(
        day_25, [ShiftType.WEEKEND, ShiftType.NIGHT]
    )
    assert all([shift.stat_day for shift in weekend_and_nights])
    nrdo = filter_shifts_by_types(day_25, [ShiftType.NRDO])
    assert not nrdo[0].stat_day

    # 26th is Monday and Boxing day and Christmas holiday, every shift is stat_day
    day_26 = filter_shifts_by_date(shifts, date(2022, 12, 26))
    assert all([shift.stat_day for shift in day_26])

    # 27th is Tuesday and Boxing holiday, every shift is stat_day
    day_27 = filter_shifts_by_date(shifts, date(2022, 12, 27))
    assert all([shift.stat_day for shift in day_27])


def test_2022_holidays():
    # Use 2022 Christmas holidays as an example to test holidays.NZ
    canterbury_holidays = holidays.NZ(prov="Canterbury")
    assert date(2022, 12, 24) not in canterbury_holidays, "Not a holiday"
    assert date(2022, 12, 25) in canterbury_holidays, "Christmas Day on Sunday"
    assert date(2022, 12, 26) in canterbury_holidays, "Boxing day but Christmas holiday"
    assert date(2022, 12, 27) in canterbury_holidays, "Boxing holiday"
    assert date(2022, 12, 28) not in canterbury_holidays, "Not a holiday"

    # Use 2022 Canterbury anniversary as an example to test holidays.NZ
    assert date(2022, 11, 11) in canterbury_holidays, "Canterbury anniversary"


def get_assignments(assignments, date, shift_type):
    return list(
        filter(
            lambda a: (a.shift.date == date) and (a.shift.type == shift_type),
            assignments,
        )
    )


def test_recency_weighting(juniors):
    assignment = fill_weekend_and_rdos(
        generate_shifts(date(2023, 1, 2), date(2023, 1, 22)),
        juniors[0],
        date(2023, 1, 7),
    )
    assert (
        registrar_by_fatigue(juniors, assignment, [], [], date(2023, 1, 21))[-1][1] > 6
    ), "Fatigue > 6 due to recency"


def test_complete_week(juniors, seniors):
    result = fill_roster(
        generate_shifts(date(2023, 1, 2), date(2023, 1, 10)), juniors + seniors
    )
    roster = partial(get_assignments, result)

    # Weekend
    mon_rdo = roster(date(2023, 1, 2), ShiftType.WRDO)[0]
    tue_rdo = roster(date(2023, 1, 3), ShiftType.WRDO)[0]
    fri = roster(date(2023, 1, 6), ShiftType.LONG)[0]
    sat = roster(date(2023, 1, 7), ShiftType.WEEKEND)[0]
    sun = roster(date(2023, 1, 8), ShiftType.WEEKEND)[0]
    mon2 = roster(date(2023, 1, 9), ShiftType.LONG)[0]

    assert mon_rdo.registrar == tue_rdo.registrar, "same reg on two rdos"
    assert fri.registrar != sat.registrar, "not oncall pre weekend"
    assert mon_rdo.registrar == sat.registrar, "rdo reg on weekend"
    assert sat.registrar == sun.registrar, "same registrar on weekend"
    assert sun.registrar != mon2.registrar, "not oncall post weekend"

    # Weekend nights
    thur = roster(date(2023, 1, 5), ShiftType.LONG)[0]
    fri_night = roster(date(2023, 1, 6), ShiftType.NIGHT)[0]
    fri_long = roster(date(2023, 1, 6), ShiftType.LONG)[0]
    sat_night = roster(date(2023, 1, 7), ShiftType.NIGHT)[0]
    sun_night = roster(date(2023, 1, 8), ShiftType.NIGHT)[0]
    mon2 = roster(date(2023, 1, 9), ShiftType.LONG)[0]

    assert thur.registrar != fri_night.registrar, "no oncall pre nights"
    assert fri_night.registrar == sat_night.registrar, "same reg on nights"
    assert fri_long.registrar != sat_night.registrar, "no oncall on evening"
    assert sat_night.registrar == sun_night.registrar, "same reg on nights"
    assert sun_night.registrar != mon2.registrar, "not oncall post nights"

    # Weekday nights
    mon_night = roster(date(2023, 1, 2), ShiftType.NIGHT)[0]
    tue_night = roster(date(2023, 1, 3), ShiftType.NIGHT)[0]
    wed_night = roster(date(2023, 1, 4), ShiftType.NIGHT)[0]
    thur_night = roster(date(2023, 1, 5), ShiftType.NIGHT)[0]
    fri_long = roster(date(2023, 1, 6), ShiftType.LONG)[0]

    assert mon_night.registrar == tue_night.registrar
    assert tue_night.registrar == wed_night.registrar
    assert wed_night.registrar == thur_night.registrar
    assert thur_night.registrar != fri_long.registrar  # not oncall post nights


def test_weekend_and_rdos(seniors):
    """
    When a registrar is assigned to a weekend, they should also be assigned to
    RDOs on the Mon and Tue on the same week, Thurs and Fri for the next week.
    """
    result = fill_roster(
        generate_shifts(date(2023, 1, 2), date(2023, 1, 16)),
        seniors,
    )
    roster = partial(get_assignments, result)

    mon_rdo = roster(date(2023, 1, 2), ShiftType.WRDO)[0]
    tue_rdo = roster(date(2023, 1, 3), ShiftType.WRDO)[0]
    sat = roster(date(2023, 1, 7), ShiftType.WEEKEND)[0]
    sun = roster(date(2023, 1, 8), ShiftType.WEEKEND)[0]
    mon_rdo2 = roster(date(2023, 1, 9), ShiftType.WRDO)[0]
    tue_rdo2 = roster(date(2023, 1, 10), ShiftType.WRDO)[0]
    thur_rdo = roster(date(2023, 1, 12), ShiftType.WRDO)[0]
    fri_rdo = roster(date(2023, 1, 13), ShiftType.WRDO)[0]
    sat2 = roster(date(2023, 1, 14), ShiftType.WEEKEND)[0]
    sun2 = roster(date(2023, 1, 15), ShiftType.WEEKEND)[0]

    assert sat.registrar == sun.registrar, "same reg on Sat and Sun for weekend1"
    assert sat2.registrar == sun2.registrar, "same reg on Sat and Sun on weekend2"
    assert sat.registrar != sat2.registrar, "different reg on Sat for weekend1 and 2"
    assert mon_rdo.registrar == sat.registrar, "Mon RDO"
    assert tue_rdo.registrar == sat.registrar, "Tue RDO"
    assert thur_rdo.registrar == sat.registrar, "Thur RDO"
    assert fri_rdo.registrar == sat.registrar, "Fri RDO"
    assert sat2.registrar == mon_rdo2.registrar, "Mon RDO for weekend 2"
    assert mon_rdo2.registrar == tue_rdo2.registrar, "Tue RDO for weekend 2"


def test_nights_and_rdos(seniors):
    """
    After a weekend set of nights (Fri, Sat and Sun), the registrar should have
    2 RDOs (Mon and Tue) in the following week.
    """
    result = fill_roster(
        generate_shifts(date(2023, 1, 2), date(2023, 1, 11)),
        seniors,
    )
    roster = partial(get_assignments, result)

    fri_night = roster(date(2023, 1, 6), ShiftType.NIGHT)[0]
    sat_night = roster(date(2023, 1, 7), ShiftType.NIGHT)[0]
    sun_night = roster(date(2023, 1, 8), ShiftType.NIGHT)[0]
    mon_rdo = roster(date(2023, 1, 9), ShiftType.NRDO)[0]
    tue_rdo = roster(date(2023, 1, 10), ShiftType.NRDO)[0]

    assert (
        fri_night.registrar == sat_night.registrar
    ), "same registrar for Fri and Sat night"
    assert (
        sat_night.registrar == sun_night.registrar
    ), "same registrar for Sat and Sun night"
    assert (
        mon_rdo.registrar == sat_night.registrar
    ), "same registrar for Mon RDO and Sat night"
    assert (
        mon_rdo.registrar == tue_rdo.registrar
    ), "same registrar for Tue RDO and Mon RDO"


def test_three_year_roster_equal_start(juniors, seniors):
    """
    In a group of registrars, the number of shifts should be even across all
    when they have no previous assignments.
    """

    shifts = generate_shifts(date(2023, 1, 2), date(2026, 1, 1))
    assignments = fill_roster(shifts, juniors + seniors)

    shift_breakdown = assignment_shift_breakdown(assignments)
    for shift_type, counts in shift_breakdown.items():
        shift_count_stdev = statistics.stdev(counts.values())
        assert shift_count_stdev < 5, f"{shift_type} should be even"

    fatigue_breakdown = registrar_by_fatigue(
        juniors + seniors, assignments, [], [], date(2026, 1, 1), recency_wgt=False
    )
    fatigue_stdev = statistics.stdev([f for _, f in fatigue_breakdown])
    assert (
        fatigue_stdev < FATIGUE_STDEV_THRESHOLD
    ), "Fatigue level should be fairly even across all registrars: f{fatigue_breakdown}"


def test_no_shifts_when_on_leave(juniors, seniors):
    shifts = generate_shifts(date(2023, 1, 2), date(2023, 1, 22))
    leaves = generate_leaves(
        date(2023, 1, 2), date(2023, 1, 22), LeaveType.ANNUAL, juniors[0]
    )
    assignments = fill_roster(shifts, juniors + seniors, leaves=leaves)
    assert (
        list(filter(lambda a: a.registrar == juniors[0], assignments)) == []
    ), "No shifts if on leave"


def test_non_rostered_status(juniors, seniors):
    junior1 = juniors[0]
    shifts = generate_shifts(date(2023, 1, 2), date(2023, 1, 22))
    status = Status(
        start=date(2023, 1, 2),
        end=date(2023, 1, 22),
        type=StatusType.BUDDY,
        registrar=junior1,
    )
    assignments = fill_roster(shifts, juniors + seniors, statuses=[status])
    assert (
        list(filter(lambda a: a.registrar == junior1, assignments)) != []
    ), "Registrar with buddy status should be rostered"

    status = Status(
        start=date(2023, 1, 2),
        end=date(2023, 1, 22),
        type=StatusType.PRE_ONCALL,
        registrar=junior1,
    )
    assignments = fill_roster(shifts, juniors + seniors, statuses=[status])
    assert (
        list(filter(lambda a: a.registrar == junior1, assignments)) == []
    ), "Registrar with pre-oncall status should not be rostered"


def test_first_start_oncall(juniors, seniors):
    junior1 = juniors[0]
    shifts = generate_shifts(date(2023, 1, 2), date(2024, 1, 2))
    status = Status(
        start=date(2023, 1, 2),
        end=date(2023, 6, 22),
        type=StatusType.PRE_ONCALL,
        registrar=junior1,
    )
    assignments = fill_roster(shifts, juniors + seniors, statuses=[status])

    shift_breakdown = assignment_shift_breakdown(assignments)

    fatigue_breakdown = registrar_by_fatigue(
        juniors + seniors,
        assignments,
        leaves=[],
        statuses=[status],
        until=date(2024, 1, 2),
        recency_wgt=False,
    )
    fatigue_stdev = statistics.stdev([f for _, f in fatigue_breakdown])
    assert (
        fatigue_stdev < FATIGUE_STDEV_THRESHOLD
    ), "Fatigue level should be fairly even across all registrars: f{fatigue_breakdown}"

    distances = [
        (registrar.username, registrar_assignment_date_distance(registrar, assignments))
        for registrar in juniors + seniors
    ]
    dist_mean = statistics.mean([d for _, d in distances])
    dist_stdev = statistics.stdev([d for _, d in distances])
    assert (
        dist_mean - 2 * dist_stdev < distances[0][1] < dist_mean + 2 * dist_stdev
    ), "Distance should be fairly even"


def test_return_from_parental_leave(juniors, seniors):
    junior1 = juniors[0]
    shifts = generate_shifts(date(2023, 1, 2), date(2024, 1, 2))
    leaves = generate_leaves(
        date(2023, 3, 2), date(2023, 9, 22), LeaveType.PARENT, juniors[0]
    )
    assignments = fill_roster(shifts, juniors + seniors, leaves=leaves, statuses=[])

    shift_breakdown = assignment_shift_breakdown(assignments)

    fatigue_breakdown = registrar_by_fatigue(
        juniors + seniors,
        assignments,
        leaves=leaves,
        statuses=[],
        until=date(2024, 1, 2),
        recency_wgt=False,
    )
    fatigue_stdev = statistics.stdev([f for _, f in fatigue_breakdown])
    assert (
        fatigue_stdev < FATIGUE_STDEV_THRESHOLD
    ), "Fatigue level should be fairly even across all registrars: f{fatigue_breakdown}"

    distances = [
        (registrar.username, registrar_assignment_date_distance(registrar, assignments))
        for registrar in juniors + seniors
    ]
    dist_mean = statistics.mean([d for _, d in distances])
    dist_stdev = statistics.stdev([d for _, d in distances])
    assert (
        dist_mean - 2 * dist_stdev < distances[0][1]
    ), "Distance should be higher than mean, as registrar is returning from leave"


def test_no_weekend_shift_abutting_leaves(juniors, seniors):
    junior1 = juniors[0]
    shifts = generate_shifts(date(2023, 1, 2), date(2023, 12, 31))
    leaves = generate_leaves(
        date(2023, 1, 2), date(2024, 1, 2), LeaveType.ANNUAL, juniors[0]
    )
    mon_leaves = list(filter(lambda l: l.date.weekday() == Weekday.MON, leaves))
    fri_leaves = list(filter(lambda l: l.date.weekday() == Weekday.FRI, leaves))

    # If taking leaves every Monday or Friday, then no weekend day or night shifts
    for day, leaves in [("Mon", mon_leaves), ("Fri", fri_leaves)]:
        assignments = fill_roster(shifts, juniors + seniors, leaves=leaves, statuses=[])
        shift_breakdown = assignment_shift_breakdown(assignments)

        junior1_assignments = list(
            filter(lambda a: a.registrar == junior1, assignments)
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
