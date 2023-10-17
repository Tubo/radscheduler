import statistics
from datetime import date, timedelta
from functools import partial

import holidays
import pandas as pd

from radscheduler.roster.assigner import AutoAssigner
from radscheduler.roster.generator import SingleOnCallRoster
from radscheduler.roster.models import LeaveType, Shift, ShiftType, Status, StatusType
from radscheduler.roster.utils import (
    filter_shifts,
    filter_shifts_by_date,
    filter_shifts_by_date_and_type,
    filter_shifts_by_types,
    generate_leaves,
    registrar_shift_distance,
    shift_breakdown,
    shifts_to_dataframe,
)
from radscheduler.roster.validators import validate_roster

FATIGUE_STDEV_THRESHOLD = 3


def test_complete_week(juniors, seniors):
    shifts = SingleOnCallRoster().generate_shifts(date(2023, 1, 2), date(2023, 1, 10))
    assigner = AutoAssigner(registrars=juniors + seniors, future_shifts=shifts)
    result = assigner.fill_roster()
    get_shift = partial(filter_shifts, result)

    # Weekend
    mon_rdo = get_shift(date(2023, 1, 2), ShiftType.RDO)[0]
    tue_rdo = get_shift(date(2023, 1, 3), ShiftType.RDO)[0]
    fri = get_shift(date(2023, 1, 6), ShiftType.LONG)[0]
    sat = get_shift(date(2023, 1, 7), ShiftType.LONG)[0]
    sun = get_shift(date(2023, 1, 8), ShiftType.LONG)[0]
    mon2 = get_shift(date(2023, 1, 9), ShiftType.LONG)[0]

    assert mon_rdo.registrar == tue_rdo.registrar, "same reg on two rdos"
    assert fri.registrar != sat.registrar, "not oncall pre weekend"
    assert mon_rdo.registrar == sat.registrar, "rdo reg on weekend"
    assert sat.registrar == sun.registrar, "same registrar on weekend"
    assert sun.registrar != mon2.registrar, "not oncall post weekend"

    # Weekend nights
    thur = get_shift(date(2023, 1, 5), ShiftType.LONG)[0]
    fri_night = get_shift(date(2023, 1, 6), ShiftType.NIGHT)[0]
    fri_long = get_shift(date(2023, 1, 6), ShiftType.LONG)[0]
    sat_night = get_shift(date(2023, 1, 7), ShiftType.NIGHT)[0]
    sun_night = get_shift(date(2023, 1, 8), ShiftType.NIGHT)[0]
    mon2 = get_shift(date(2023, 1, 9), ShiftType.LONG)[0]

    assert thur.registrar != fri_night.registrar, "no oncall pre nights"
    assert fri_night.registrar == sat_night.registrar, "same reg on nights"
    assert fri_long.registrar != sat_night.registrar, "no oncall on evening"
    assert sat_night.registrar == sun_night.registrar, "same reg on nights"
    assert sun_night.registrar != mon2.registrar, "not oncall post nights"

    # Weekday nights
    mon_night = get_shift(date(2023, 1, 2), ShiftType.NIGHT)[0]
    tue_night = get_shift(date(2023, 1, 3), ShiftType.NIGHT)[0]
    wed_night = get_shift(date(2023, 1, 4), ShiftType.NIGHT)[0]
    thur_night = get_shift(date(2023, 1, 5), ShiftType.NIGHT)[0]
    fri_long = get_shift(date(2023, 1, 6), ShiftType.LONG)[0]

    assert mon_night.registrar == tue_night.registrar
    assert tue_night.registrar == wed_night.registrar
    assert wed_night.registrar == thur_night.registrar
    assert thur_night.registrar != fri_long.registrar  # not oncall post nights

    assert validate_roster(result, [], [])


def test_weekend_and_rdos(seniors):
    """
    When a registrar is assigned to a weekend, they should also be assigned to
    RDOs on the Mon and Tue on the same week, Thurs and Fri for the next week.
    """
    shifts = SingleOnCallRoster().generate_shifts(date(2023, 1, 2), date(2023, 1, 16))
    assigner = AutoAssigner(registrars=seniors, future_shifts=shifts)
    result = assigner.fill_roster()
    get_shift = partial(filter_shifts, result)

    mon_rdo = get_shift(date(2023, 1, 2), ShiftType.RDO)[0]
    tue_rdo = get_shift(date(2023, 1, 3), ShiftType.RDO)[0]
    sat = get_shift(date(2023, 1, 7), ShiftType.LONG)[0]
    sun = get_shift(date(2023, 1, 8), ShiftType.LONG)[0]
    mon_rdo2 = get_shift(date(2023, 1, 9), ShiftType.RDO)[0]
    tue_rdo2 = get_shift(date(2023, 1, 10), ShiftType.RDO)[0]
    thur_rdo = get_shift(date(2023, 1, 12), ShiftType.RDO)[0]
    fri_rdo = get_shift(date(2023, 1, 13), ShiftType.RDO)[0]
    sat2 = get_shift(date(2023, 1, 14), ShiftType.LONG)[0]
    sun2 = get_shift(date(2023, 1, 15), ShiftType.LONG)[0]

    assert sat.registrar == sun.registrar, "same reg on Sat and Sun for weekend1"
    assert sat2.registrar == sun2.registrar, "same reg on Sat and Sun on weekend2"
    assert sat.registrar != sat2.registrar, "different reg on Sat for weekend1 and 2"
    assert mon_rdo.registrar == sat.registrar, "Mon RDO"
    assert tue_rdo.registrar == sat.registrar, "Tue RDO"
    assert thur_rdo.registrar == sat.registrar, "Thur RDO"
    assert fri_rdo.registrar == sat.registrar, "Fri RDO"
    assert sat2.registrar == mon_rdo2.registrar, "Mon RDO for weekend 2"
    assert mon_rdo2.registrar == tue_rdo2.registrar, "Tue RDO for weekend 2"

    assert validate_roster(result, [], [])


def test_nights_and_rdos(seniors):
    """
    After a weekend set of nights (Fri, Sat and Sun), the registrar should have
    2 RDOs (Mon and Tue) in the following week.
    """
    shifts = SingleOnCallRoster().generate_shifts(date(2023, 1, 2), date(2023, 1, 11))
    assigner = AutoAssigner(registrars=seniors, future_shifts=shifts)
    result = assigner.fill_roster()
    get_shift = partial(filter_shifts, result)

    fri_night = get_shift(date(2023, 1, 6), ShiftType.NIGHT)[0]
    sat_night = get_shift(date(2023, 1, 7), ShiftType.NIGHT)[0]
    sun_night = get_shift(date(2023, 1, 8), ShiftType.NIGHT)[0]
    mon_rdo = get_shift(date(2023, 1, 9), ShiftType.SLEEP)[0]
    tue_rdo = get_shift(date(2023, 1, 10), ShiftType.SLEEP)[0]

    assert fri_night.registrar == sat_night.registrar, "same registrar for Fri and Sat night"
    assert sat_night.registrar == sun_night.registrar, "same registrar for Sat and Sun night"
    assert mon_rdo.registrar == sat_night.registrar, "same registrar for Mon RDO and Sat night"
    assert mon_rdo.registrar == tue_rdo.registrar, "same registrar for Tue RDO and Mon RDO"

    assert validate_roster(result, [], [])


def test_three_year_roster_equal_start(juniors, seniors):
    """
    In a group of registrars, the number of shifts should be even across all
    when they have no previous assignments.
    """
    shifts = SingleOnCallRoster().generate_shifts(date(2023, 1, 2), date(2026, 1, 1))
    assigner = AutoAssigner(registrars=juniors + seniors, future_shifts=shifts)
    result = assigner.fill_roster()

    df = shifts_to_dataframe(result)
    breakdown = shift_breakdown(df)
    stdevs = breakdown.std()
    assert (stdevs < 5).all(), f"New breakdown should be even"

    fatigue_breakdown = assigner.registrars_sorted_by_fatigue(result)
    fatigue_stdev = statistics.stdev([f for _, f in fatigue_breakdown])
    assert (
        fatigue_stdev < FATIGUE_STDEV_THRESHOLD
    ), "Fatigue level should be fairly even across all registrars: f{fatigue_breakdown}"

    assert validate_roster(result, [], [])


def test_no_shifts_when_on_leave(juniors, seniors):
    leaves = generate_leaves(date(2023, 1, 2), date(2023, 1, 22), LeaveType.ANNUAL, juniors[0])
    shifts = SingleOnCallRoster().generate_shifts(date(2023, 1, 2), date(2023, 1, 22))
    assigner = AutoAssigner(registrars=juniors + seniors, future_shifts=shifts, leaves=leaves)
    result = assigner.fill_roster()

    assert list(filter(lambda shift: shift.registrar == juniors[0], result)) == [], "No shifts if on leave"
    assert validate_roster(result, leaves=leaves, statuses=[])


def test_non_rostered_status(juniors, seniors):
    junior1 = juniors[0]
    status = Status(
        start=date(2023, 1, 2),
        end=date(2023, 1, 22),
        type=StatusType.BUDDY,
        registrar=junior1,
    )
    shifts = SingleOnCallRoster().generate_shifts(date(2023, 1, 2), date(2023, 1, 22))
    assigner = AutoAssigner(registrars=juniors + seniors, future_shifts=shifts, statuses=[status])
    result = assigner.fill_roster()
    assert (
        list(filter(lambda a: a.registrar == junior1, result)) != []
    ), "Registrar with buddy status should be rostered"

    status = Status(
        start=date(2023, 1, 2),
        end=date(2023, 1, 22),
        type=StatusType.PRE_ONCALL,
        registrar=junior1,
    )
    assigner.statuses = [status]
    result = assigner.fill_roster()
    assert (
        list(filter(lambda a: a.registrar == junior1, result)) == []
    ), "Registrar with pre-oncall status should not be rostered"

    assert validate_roster(result, [], statuses=[status])


def test_first_start_oncall(juniors, seniors):
    junior1 = juniors[0]
    status = Status(
        start=date(2023, 1, 2),
        end=date(2023, 6, 22),
        type=StatusType.PRE_ONCALL,
        registrar=junior1,
    )
    shifts = SingleOnCallRoster().generate_shifts(date(2023, 1, 2), date(2024, 1, 2))
    assigner = AutoAssigner(registrars=juniors + seniors, future_shifts=shifts, statuses=[status])
    result = assigner.fill_roster()

    # Shift and user stats
    df = shifts_to_dataframe(result)
    breakdown = shift_breakdown(df)

    # Overall fatigue level breakdown
    fatigue_breakdown = assigner.registrars_sorted_by_fatigue(result)
    fatigue_stdev = statistics.stdev([f for _, f in fatigue_breakdown])
    assert (
        fatigue_stdev < FATIGUE_STDEV_THRESHOLD
    ), "Fatigue level should be fairly even across all registrars: f{fatigue_breakdown}"

    # Date distance breakdown
    distances = [(registrar.username, registrar_shift_distance(registrar, result)) for registrar in juniors + seniors]
    dist_mean = statistics.mean([d for _, d in distances])
    dist_stdev = statistics.stdev([d for _, d in distances])

    assert dist_stdev < 5, "Distance between shifts should be fairly even"

    assert validate_roster(result, [], [])


def test_return_from_parental_leave(juniors, seniors):
    leaves = generate_leaves(date(2023, 3, 2), date(2023, 9, 22), LeaveType.PARENTAL, juniors[0])
    shifts = SingleOnCallRoster().generate_shifts(date(2023, 1, 2), date(2024, 1, 2))
    assigner = AutoAssigner(registrars=juniors + seniors, future_shifts=shifts, leaves=leaves)
    result = assigner.fill_roster()

    breakdown = shift_breakdown(shifts_to_dataframe(result))

    fatigue_breakdown = assigner.registrars_sorted_by_fatigue(result)
    fatigue_stdev = statistics.stdev([f for _, f in fatigue_breakdown])
    assert (
        fatigue_stdev < FATIGUE_STDEV_THRESHOLD
    ), "Fatigue level should be fairly even across all registrars: f{fatigue_breakdown}"

    distances = [(registrar.username, registrar_shift_distance(registrar, result)) for registrar in juniors + seniors]
    dist_mean = statistics.mean([d for _, d in distances])
    dist_stdev = statistics.stdev([d for _, d in distances])
    assert (
        dist_mean - 2 * dist_stdev < distances[0][1]
    ), "Distance should be higher than mean, as registrar is returning from leave"

    assert validate_roster(result, leaves=leaves, statuses=[])


def test_fill_roster_with_prospective_slots_filled():
    # For example, the roster during Christmas time would be filled manually
    pass


def test_ignore_extra_duty_from_fatigue():
    pass


def test_swap_long_day():
    # should be moved to django
    pass


def test_swap_night():
    # should be moved to django
    pass


def test_swap_weekends():
    # should be moved to django
    pass
