from datetime import timedelta, date

import radscheduler.core.logic as logic
from radscheduler.core.models import Weekday, ShiftType, StatusType


def validate(shift, registrar, assignments, **kwargs):
    validators = [
        validate_not_rostered_status,
        validate_not_on_leave,
        validate_only_one_shift_per_day,
        validate_no_back_to_back_long_days,
        validate_no_more_than_2_long_days_in_7,
        validate_leave_abutting_weekends,
        validate_every_second_weekend_free,
    ]
    return all(
        validator(shift, registrar, assignments, **kwargs) for validator in validators
    )


def validate_assignments(registrars, assignments, leaves, statuses):
    for registrar in registrars:
        shifts = [
            assignment.shift
            for assignment in filter(lambda a: a.registrar == registrar, assignments)
        ]
        leaves = list(filter(lambda l: l.registrar == registrar, leaves))
        statuses = list(filter(lambda s: s.registrar == registrar, statuses))

        groupby_date = logic.group_shifts_by_date(shifts)
        for date, shifts in groupby_date.items():
            if len(shifts) > 1:
                assert (
                    False
                ), f"{registrar} cannot work more than 1 shift per day: {shifts}"

        working_days = [
            shift.date
            for shift in shifts
            if shift.type in [ShiftType.LONG, ShiftType.NIGHT, ShiftType.WEEKEND]
        ]
        for i in range(len(working_days) - 7):
            if len(working_days[i : i + 7]) >= 2:
                assert False, f"{registrar} cannot work more than 2 shifts in 7 days"

        for leave in leaves:
            shifts = list(filter(lambda s: (s.date == leave.date), shifts))
            assert (
                shifts == []
            ), f"{registrar} cannot work {shifts} while on leave {leave}"

        for leave in leaves:
            if leave.date.weekday() == Weekday.MON:
                shifts = list(
                    filter(
                        lambda a: (
                            date - timedelta(2) <= a.shift.date <= date - timedelta(1)
                        ),
                        shifts,
                    )
                )
                assert (
                    shifts == []
                ), f"{registrar} cannot work on weekends abutting leave"

        for status in statuses:
            if status.type == StatusType.BUDDY:
                continue
            shifts = filter(
                lambda shift: (status.start <= shift.date <= status.end), shifts
            )
            assert list(shifts) == [], f"{registrar} cannot work while on {status}"


def validate_only_one_shift_per_day(shift, registrar, assignments, **kwargs):
    """
    Return False if a registrar was placed on two shifts on a same day.
    """
    my_shifts = logic.filter_assignments(
        assignments, lambda a: a.registrar == registrar
    )
    same_date = list(
        filter(
            lambda a: (a.shift.date == shift.date),
            my_shifts,
        )
    )

    return len(same_date) == 0


def validate_not_on_leave(shift, registrar, assignments, *args, **kwargs):
    """
    Return False if a registrar was placed on two shifts on a same day.
    """
    leaves = kwargs.get("leaves", [])
    leaves_on_this_day = list(
        filter(lambda l: (l.date == shift.date) and (l.registrar == registrar), leaves)
    )
    if leaves_on_this_day:
        return False
    return True


def validate_not_rostered_status(shift, registrar, assignments, *args, **kwargs):
    """
    Return False if a registrar has a status that is for no_roster.
    """
    statuses = kwargs.get("statuses", [])
    no_roster = list(
        filter(
            lambda s: (s.registrar == registrar)
            and (s.start <= shift.date <= s.end)
            and s.not_oncall,
            statuses,
        )
    )
    if no_roster:
        return False
    return True


def validate_no_more_than_2_long_days_in_7(
    shift, registrar, assignments, *args, **kwargs
):
    """
    17.2.2 RMOs shall not be rostered on duty for more than 2 long days in 7.
    For the purposes of this clause, a “long day” shall be a duty where in excess of 10 hours are worked.
    """
    my_shifts = logic.filter_assignments(
        assignments, lambda a: a.registrar == registrar
    )
    lats_7_days = logic.filter_assignments(
        my_shifts,
        lambda a: (a.shift.date >= shift.date - timedelta(7)),
    )

    return len(lats_7_days) <= 1


def validate_no_back_to_back_long_days(shift, registrar, assignments, *args, **kwargs):
    """
    A registrar should not be placed on a long day if they worked a long day the day before.

    Nights and weekends are special cases that will be handled separately.
    """
    my_shifts = logic.filter_assignments(
        assignments, lambda a: a.registrar == registrar
    )
    prev_day = logic.filter_assignments(
        my_shifts, lambda a: (a.shift.date == shift.date - timedelta(1))
    )
    return prev_day == []


def validate_leave_abutting_weekends(shift, registrar, assignments, *args, **kwargs):
    """
    21.4.1 When an RMO is on annual leave on the days immediately before or after a weekend,
    she/he cannot be required to work the weekend(s).

    - Friday long is not considered a weekend shift, but a Friday night shift is part of a weekend.
    - Lieu days are not considered in this clause
    """
    leaves = kwargs.get("leaves", [])
    my_leaves = list(filter(lambda l: l.registrar == registrar, leaves))
    if shift.type == ShiftType.WRDO:
        # This is a Monday WRDO
        assert shift.date.weekday() == Weekday.MON, "Must be a Monday WRDO"
        # Other shifts are deteremined by the shift generation algorithm
        leaves_next_fri_or_mon = list(
            filter(
                lambda l: (l.date == shift.date + timedelta(4))  # Friday
                or (l.date == shift.date + timedelta(7)),  # Monday
                my_leaves,
            )
        )
        return leaves_next_fri_or_mon == []
    elif shift.type == ShiftType.NIGHT:
        if shift.date.weekday() == Weekday.MON:
            # Monday night is handled by validate_not_on_leave
            pass
        elif shift.date.weekday() == Weekday.FRI:
            # Cannot work this weekend night if on leave on Monday
            leaves_next_mon = list(
                filter(
                    lambda l: (l.date == shift.date + timedelta(3)),
                    my_leaves,
                )
            )
            return leaves_next_mon == []

    return True


def validate_every_second_weekend_free(shift, registrar, assignments, *args, **kwargs):
    """
    17.3.5 Employees shall have, as a minimum, every second weekend completely free from duty.
    """
    if shift.date.weekday() in [Weekday.SAT, Weekday.SUN]:
        if next(
            logic.filter_assignments(
                assignments,
                lambda a: (a.registrar == registrar)
                and (a.shift.date == shift.date - timedelta(7)),
            )
        ):
            return False

    return True


def shift_validate_post_night_RDOs(shift, registrar, assignments, *args, **kwargs):
    """
    17.4.6 Employees working three-night duties or less shall be given a minimum break of the
    calendar day upon which the employee ceased the last night duty plus a further one
    calendar day free from rostered duty.

    In other words:
    - Weekend nights = Fri, Sat, Sun RDOs
    - Weekdays nights = Mon, Tues RDOs

    This has been built into the shift generation algorithm already.
    """


def leave_validate_lieu_day_notice():
    """
    24.1 Lieu days must be applied
    - 14 days before regular day
    - 28 days before long day, weekends or nights
    - within 12 months
    """
