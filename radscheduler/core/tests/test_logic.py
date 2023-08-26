from functools import partial
from datetime import date, timedelta
import holidays
import statistics

from radscheduler.core.models import ShiftType, LeaveType, Status, StatusType
from radscheduler.core.roster import (
    DefaultRoster,
    filter_assignments_by_date_and_shift_type,
)
from radscheduler.core.logic import (
    Assignment,
    generate_leaves,
    filter_shifts_by_date,
    filter_shifts_by_types,
    filter_shifts_by_date_and_type,
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

    monday_rdo = filter_shifts_by_date_and_type(shifts, prev_monday, ShiftType.RDO)
    tuesday_rdo = filter_shifts_by_date_and_type(shifts, prev_tuesday, ShiftType.RDO)
    saturday_shift = filter_shifts_by_date_and_type(shifts, saturday, ShiftType.LONG)
    sunday_shift = filter_shifts_by_date_and_type(shifts, sunday, ShiftType.LONG)
    thursday_rdo = filter_shifts_by_date_and_type(shifts, next_thurs, ShiftType.RDO)
    friday_rdo = filter_shifts_by_date_and_type(shifts, next_fri, ShiftType.RDO)

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
    roster = DefaultRoster()
    shifts = roster.generate_shifts(date(2023, 1, 2), date(2023, 1, 22))

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


def test_mark_stat_day_in_generated_shifts():
    roster = DefaultRoster()
    shifts = roster.generate_shifts(date(2022, 12, 22), date(2022, 12, 29))

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
    weekend_and_nights = filter_shifts_by_types(
        day_25, [ShiftType.LONG, ShiftType.NIGHT]
    )
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
    canterbury_holidays = holidays.NZ(prov="Canterbury")
    assert date(2022, 12, 24) not in canterbury_holidays, "Not a holiday"
    assert date(2022, 12, 25) in canterbury_holidays, "Christmas Day on Sunday"
    assert date(2022, 12, 26) in canterbury_holidays, "Boxing day but Christmas holiday"
    assert date(2022, 12, 27) in canterbury_holidays, "Boxing holiday"
    assert date(2022, 12, 28) not in canterbury_holidays, "Not a holiday"

    # Use 2022 Canterbury anniversary as an example to test holidays.NZ
    assert date(2022, 11, 11) in canterbury_holidays, "Canterbury anniversary"


def test_recency_weighting(juniors):
    roster = DefaultRoster(registrars=juniors)
    assignment = fill_weekend_and_rdos(
        roster.generate_shifts(date(2023, 1, 2), date(2023, 1, 22)),
        juniors[0],
        date(2023, 1, 7),
    )
    assert (
        roster.registrar_sorted_by_fatigue(assignment, date(2023, 1, 21))[-1][1] > 6
    ), "Fatigue > 6 due to recency"


def test_complete_week(juniors, seniors):
    roster = DefaultRoster(registrars=juniors + seniors)
    roster.generate_shifts(date(2023, 1, 2), date(2023, 1, 10))
    result = roster.fill_roster()
    get_assignment = partial(filter_assignments_by_date_and_shift_type, result)

    # Weekend
    mon_rdo = get_assignment(date(2023, 1, 2), ShiftType.RDO)[0]
    tue_rdo = get_assignment(date(2023, 1, 3), ShiftType.RDO)[0]
    fri = get_assignment(date(2023, 1, 6), ShiftType.LONG)[0]
    sat = get_assignment(date(2023, 1, 7), ShiftType.LONG)[0]
    sun = get_assignment(date(2023, 1, 8), ShiftType.LONG)[0]
    mon2 = get_assignment(date(2023, 1, 9), ShiftType.LONG)[0]

    assert mon_rdo.registrar == tue_rdo.registrar, "same reg on two rdos"
    assert fri.registrar != sat.registrar, "not oncall pre weekend"
    assert mon_rdo.registrar == sat.registrar, "rdo reg on weekend"
    assert sat.registrar == sun.registrar, "same registrar on weekend"
    assert sun.registrar != mon2.registrar, "not oncall post weekend"

    # Weekend nights
    thur = get_assignment(date(2023, 1, 5), ShiftType.LONG)[0]
    fri_night = get_assignment(date(2023, 1, 6), ShiftType.NIGHT)[0]
    fri_long = get_assignment(date(2023, 1, 6), ShiftType.LONG)[0]
    sat_night = get_assignment(date(2023, 1, 7), ShiftType.NIGHT)[0]
    sun_night = get_assignment(date(2023, 1, 8), ShiftType.NIGHT)[0]
    mon2 = get_assignment(date(2023, 1, 9), ShiftType.LONG)[0]

    assert thur.registrar != fri_night.registrar, "no oncall pre nights"
    assert fri_night.registrar == sat_night.registrar, "same reg on nights"
    assert fri_long.registrar != sat_night.registrar, "no oncall on evening"
    assert sat_night.registrar == sun_night.registrar, "same reg on nights"
    assert sun_night.registrar != mon2.registrar, "not oncall post nights"

    # Weekday nights
    mon_night = get_assignment(date(2023, 1, 2), ShiftType.NIGHT)[0]
    tue_night = get_assignment(date(2023, 1, 3), ShiftType.NIGHT)[0]
    wed_night = get_assignment(date(2023, 1, 4), ShiftType.NIGHT)[0]
    thur_night = get_assignment(date(2023, 1, 5), ShiftType.NIGHT)[0]
    fri_long = get_assignment(date(2023, 1, 6), ShiftType.LONG)[0]

    assert mon_night.registrar == tue_night.registrar
    assert tue_night.registrar == wed_night.registrar
    assert wed_night.registrar == thur_night.registrar
    assert thur_night.registrar != fri_long.registrar  # not oncall post nights


def test_weekend_and_rdos(seniors):
    """
    When a registrar is assigned to a weekend, they should also be assigned to
    RDOs on the Mon and Tue on the same week, Thurs and Fri for the next week.
    """
    roster = DefaultRoster(registrars=seniors)
    roster.generate_shifts(date(2023, 1, 2), date(2023, 1, 16))
    result = roster.fill_roster()
    get_assignment = partial(filter_assignments_by_date_and_shift_type, result)

    mon_rdo = get_assignment(date(2023, 1, 2), ShiftType.RDO)[0]
    tue_rdo = get_assignment(date(2023, 1, 3), ShiftType.RDO)[0]
    sat = get_assignment(date(2023, 1, 7), ShiftType.LONG)[0]
    sun = get_assignment(date(2023, 1, 8), ShiftType.LONG)[0]
    mon_rdo2 = get_assignment(date(2023, 1, 9), ShiftType.RDO)[0]
    tue_rdo2 = get_assignment(date(2023, 1, 10), ShiftType.RDO)[0]
    thur_rdo = get_assignment(date(2023, 1, 12), ShiftType.RDO)[0]
    fri_rdo = get_assignment(date(2023, 1, 13), ShiftType.RDO)[0]
    sat2 = get_assignment(date(2023, 1, 14), ShiftType.LONG)[0]
    sun2 = get_assignment(date(2023, 1, 15), ShiftType.LONG)[0]

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
    roster = DefaultRoster(registrars=seniors)
    roster.generate_shifts(date(2023, 1, 2), date(2023, 1, 11))
    result = roster.fill_roster()
    get_assignments = partial(filter_assignments_by_date_and_shift_type, result)

    fri_night = get_assignments(date(2023, 1, 6), ShiftType.NIGHT)[0]
    sat_night = get_assignments(date(2023, 1, 7), ShiftType.NIGHT)[0]
    sun_night = get_assignments(date(2023, 1, 8), ShiftType.NIGHT)[0]
    mon_rdo = get_assignments(date(2023, 1, 9), ShiftType.SLEEP)[0]
    tue_rdo = get_assignments(date(2023, 1, 10), ShiftType.SLEEP)[0]

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
    roster = DefaultRoster(registrars=juniors + seniors)
    roster.generate_shifts(date(2023, 1, 2), date(2026, 1, 1))
    assignments = roster.fill_roster()

    shift_breakdown = assignment_shift_breakdown(assignments)
    for shift_type, counts in shift_breakdown.items():
        shift_count_stdev = statistics.stdev(counts.values())
        assert shift_count_stdev < 5, f"{shift_type} should be even"

    fatigue_breakdown = roster.registrar_sorted_by_fatigue(
        assignments, date(2026, 1, 1), recency_length=0
    )
    fatigue_stdev = statistics.stdev([f for _, f in fatigue_breakdown])
    assert (
        fatigue_stdev < FATIGUE_STDEV_THRESHOLD
    ), "Fatigue level should be fairly even across all registrars: f{fatigue_breakdown}"


def test_no_shifts_when_on_leave(juniors, seniors):
    leaves = generate_leaves(
        date(2023, 1, 2), date(2023, 1, 22), LeaveType.ANNUAL, juniors[0]
    )
    roster = DefaultRoster(registrars=juniors + seniors, leaves=leaves)
    roster.generate_shifts(date(2023, 1, 2), date(2023, 1, 22))
    assignments = roster.fill_roster()

    assert (
        list(filter(lambda a: a.registrar == juniors[0], assignments)) == []
    ), "No shifts if on leave"


def test_non_rostered_status(juniors, seniors):
    junior1 = juniors[0]
    status = Status(
        start=date(2023, 1, 2),
        end=date(2023, 1, 22),
        type=StatusType.BUDDY,
        registrar=junior1,
    )
    roster = DefaultRoster(registrars=juniors + seniors, statuses=[status])
    roster.generate_shifts(date(2023, 1, 2), date(2023, 1, 22))

    assignments = roster.fill_roster()
    assert (
        list(filter(lambda a: a.registrar == junior1, assignments)) != []
    ), "Registrar with buddy status should be rostered"

    status = Status(
        start=date(2023, 1, 2),
        end=date(2023, 1, 22),
        type=StatusType.PRE_ONCALL,
        registrar=junior1,
    )
    roster.statuses = [status]
    assignments = roster.fill_roster()
    assert (
        list(filter(lambda a: a.registrar == junior1, assignments)) == []
    ), "Registrar with pre-oncall status should not be rostered"


def test_first_start_oncall(juniors, seniors):
    junior1 = juniors[0]
    status = Status(
        start=date(2023, 1, 2),
        end=date(2023, 6, 22),
        type=StatusType.PRE_ONCALL,
        registrar=junior1,
    )
    roster = DefaultRoster(registrars=juniors + seniors, statuses=[status])
    roster.generate_shifts(date(2023, 1, 2), date(2024, 1, 2))
    assignments = roster.fill_roster()

    shift_breakdown = assignment_shift_breakdown(assignments)
    fatigue_breakdown = roster.registrar_sorted_by_fatigue(
        assignments,
        until=date(2024, 1, 2),
        recency_length=0,
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
    leaves = generate_leaves(
        date(2023, 3, 2), date(2023, 9, 22), LeaveType.PARENTAL, juniors[0]
    )
    roster = DefaultRoster(registrars=juniors + seniors, leaves=leaves)
    roster.generate_shifts(date(2023, 1, 2), date(2024, 1, 2))
    assignments = roster.fill_roster()

    shift_breakdown = assignment_shift_breakdown(assignments)

    fatigue_breakdown = roster.registrar_sorted_by_fatigue(
        assignments,
        until=date(2024, 1, 2),
        recency_length=False,
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


def test_ignore_extra_duty_from_fatigue():
    pass


def test_swap_long_day():
    pass


def test_swap_night():
    pass


def test_swap_weekends():
    pass
