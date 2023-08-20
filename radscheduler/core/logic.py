from collections import namedtuple
from datetime import timedelta, date
from dataclasses import dataclass
import holidays

from django.contrib.auth import get_user_model
from radscheduler.core.models import (
    Shift,
    Weekday,
    ShiftType,
    Leave,
    LeaveType,
    Status,
)
import radscheduler.core.validators as validators

AVG_WEEKLY_FATIGUE = 1.65  # 15 people roster
RECENCY_WGT = 1.5

User = get_user_model()
canterbury_holidays = holidays.NZ(subdiv="CAN")


@dataclass
class Assignment:
    shift: Shift
    registrar: User


class NoOneAvailable(Exception):
    pass


def generate_shifts(start: date, end: date) -> list[Shift]:
    """
    1. Generate a list of empty shifts from Start to End date.
    2. Public holidys should be stat days.
    """
    regular_shifts = generate_regular_shifts(start, end)
    shifts = [mark_stat_days(shift) for shift in regular_shifts]
    return shifts


def generate_regular_shifts(start: date, end: date) -> list[Shift]:
    """
    Generate a list of shifts from Start to End date.
    Public holidys should be stat days.

    This is the roster requirement as of 2023:

    Monday and Tuesday:
    - Long day and night
    - WRDO (Pre-weekend)
    - NRDO (Post-weekend)

    Wednesday:
    - Long day and night

    Thursday:
    - Long day and night
    - WRDO (Post-weekend)

    Friday:
    - Long day and night
    - NRDO (Post weekday night)
    - WRDO (Post-weekend)

    Saturday and Sunday:
    - Long day and night
    - NRDO (Post weekday night)
    """
    results = []
    for day in daterange(start, end):
        # Every day has a long day shift and a night shift
        shifts = [
            Shift(date=day, type=ShiftType.LONG),
            Shift(date=day, type=ShiftType.NIGHT),
        ]
        match day.weekday():
            case Weekday.MON | Weekday.TUE:
                shifts.append(Shift(date=day, type=ShiftType.WRDO))
                if start <= day - timedelta(2):
                    shifts.append(Shift(date=day, type=ShiftType.NRDO))
            case Weekday.WED:
                pass
            case Weekday.THUR:
                if start <= day - timedelta(5):
                    shifts.append(Shift(date=day, type=ShiftType.WRDO))

            case Weekday.FRI:
                if start <= day - timedelta(5):
                    shifts.append(Shift(date=day, type=ShiftType.WRDO))

                if start <= day - timedelta(2):
                    shifts.append(Shift(date=day, type=ShiftType.NRDO))
            case Weekday.SAT | Weekday.SUN:
                shifts = [
                    Shift(date=day, type=ShiftType.WEEKEND),
                    Shift(date=day, type=ShiftType.NIGHT),
                ]

                if start <= day - timedelta(2):
                    shifts.append(Shift(date=day, type=ShiftType.NRDO))

        results.extend(shifts)
    return results


def mark_stat_days(shift: Shift) -> Shift:
    """
    Change a shift to a stat day if it falls on a public holiday.
    Public holidays are never on weekends per NZ law.

    If a LONG, WEEKEND, WRDO, NRDO falls on a stat day, it should be a stat day.
    Unless the NRDO is a weekend NRDO, then it should not be a stat day.
    If a NIGHT shift falls is one day before a stat day, it should be a stat day.
    """
    if shift.date in canterbury_holidays:
        if shift.type in [
            ShiftType.LONG,
            ShiftType.WEEKEND,
            ShiftType.NIGHT,
            ShiftType.WRDO,
        ]:
            shift.stat_day = True
        elif shift.type == ShiftType.NRDO:
            if shift.date.weekday() not in [Weekday.SAT, Weekday.SUN]:
                shift.stat_day = True

    elif shift.type == ShiftType.NIGHT:
        tomorrow = shift.date + timedelta(1)
        if tomorrow in canterbury_holidays:
            shift.stat_day = True

    return shift


def group_shifts_by_type(shifts: list[Shift]) -> dict[ShiftType, list[Shift]]:
    """
    Group shifts by type
    """
    results = {}
    for shift in shifts:
        if shift.type not in results:
            results[shift.type] = []
        results[shift.type].append(shift)
    return results


def group_shifts_by_date(shifts: list[Shift]) -> dict[date, list[Shift]]:
    """
    Group shifts by date
    """
    results = {}
    for shift in shifts:
        if shift.date not in results:
            results[shift.date] = []
        results[shift.date].append(shift)
    return results


def filter_shifts_by_date(shifts: list[Shift], date: date) -> list[Shift]:
    """
    Filter shifts by date
    """
    return list(filter(lambda s: s.date == date, shifts))


def filter_shifts_by_date_range(
    shifts: list[Shift], start: date, end: date
) -> list[Shift]:
    """
    Filter shifts by date range
    """
    return list(filter(lambda s: start <= s.date <= end, shifts))


def filter_shifts_by_types(
    shifts: list[Shift], shift_types: list[ShiftType]
) -> list[Shift]:
    """
    Filter shifts by type
    """
    return list(filter(lambda s: s.type in shift_types, shifts))


def filter_shifts_by_date_and_type(
    shifts: list[Shift], date: date, shift_type: ShiftType
) -> list[Shift]:
    return list(filter(lambda s: s.date == date and s.type == shift_type, shifts))


def assignment_user_breakdown(assignments: list[Assignment]) -> dict:
    """
    Returns a breakdown of how many shifts each registrar has per type of shift.
    """
    results = {}
    for assignment in assignments:
        username = assignment.registrar.username
        if username not in results:
            results[username] = {}
        if assignment.shift.type not in results[username]:
            results[username][assignment.shift.type] = 0
        results[username][assignment.shift.type] += 1
    return results


def assignment_shift_breakdown(assignments: list[Assignment]) -> dict:
    """
    Returns a breakdown of how many shifts each registrar has per type of shift.
    """
    results = {}
    for assignment in assignments:
        username = assignment.registrar.username
        shift = assignment.shift
        if shift.type not in results:
            results[shift.type] = {}
        if username not in results[shift.type]:
            results[shift.type][username] = 0
        results[shift.type][username] += 1
    return results


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)


def fill_roster(
    shifts: list[Shift],
    registrars: list[User],
    prev_shifts: list[Shift] = [],
    leaves: list[Leave] = [],
    statuses: list[Status] = [],
) -> list[Assignment]:
    results = []

    for shift in shifts:
        if shift.type == ShiftType.LONG:
            # Long days and holidays
            # Find next rested registrar
            registrar = next_registrar(
                shift, registrars, results, prev_shifts, leaves, statuses
            )

        elif shift.type == ShiftType.NIGHT:
            if is_start_of_set(shift):
                # Start of week day and weekend nights
                # Simply find next rested registrar
                registrar = next_registrar(
                    shift, registrars, results, prev_shifts, leaves, statuses
                )
            else:  # keep the same registrar as yesterday
                registrar = same_registrar_yesterday(shift, results, prev_shifts)

        elif shift.type == ShiftType.WEEKEND:
            if is_start_of_set(shift):
                # Find the registrar that had RDO 5 days ago
                # Weekend shifts are special, they are deteremined by the RDO from previous Monday and Tuesday
                # Find the registrar that had RDO from 5 days ago (Monday),
                last_rdo = shift.date - timedelta(5)
                registrar = find_registrar(
                    last_rdo, ShiftType.WRDO, results, "No RDO before weekends"
                )
            else:
                # On Sunday, find the weekend registrar from yesterday
                registrar = same_registrar_yesterday(shift, results, prev_shifts)

        elif shift.type == ShiftType.WRDO:
            if is_start_of_set(shift):
                # Find next rested registrar
                registrar = next_registrar(
                    shift, registrars, results, prev_shifts, leaves, statuses
                )

            elif shift.date.weekday() == Weekday.THUR:
                # Find the registrar from last weekend
                registrar = last_weekend_registrar(shift, results, prev_shifts)

            else:
                registrar = same_registrar_yesterday(shift, results, prev_shifts)

        elif shift.type == ShiftType.NRDO:
            # Find the registrar that worked nights last weekend
            last_rdo = shift.date - timedelta(3)  # look back 3 days
            registrar = find_registrar(
                last_rdo, ShiftType.NIGHT, results, "No RDO post weekends nights"
            )

        else:
            raise ValueError("Unknown shift type")

        results.append(Assignment(shift, registrar))

    validators.validate_assignments(registrars, results, leaves, statuses)
    return results


def assign(assignments: list[Assignment]) -> list[Shift]:
    """
    Assign shifts to registrars.
    """
    results = []
    for assignment in assignments:
        assignment.shift.registrar = assignment.registrar
        results.append(assignment.shift)
    return results


def next_registrar(
    shift, registrars, proposed_assignments, prev_shifts, leaves, statuses
) -> User:
    """
    Select the next registrar to be rostered on.
    """
    prev = list(map(lambda s: shift_to_assignment(s, s.registrar), prev_shifts))
    assignments = sort_assignments_by_date(proposed_assignments + prev)
    registrars = registrar_by_fatigue(
        registrars, assignments, leaves, statuses, shift.date
    )

    for idx, (registrar, _) in enumerate(registrars):
        if not validators.validate(
            shift, registrar, assignments, leaves=leaves, statuses=statuses
        ):
            # Go to next registrar if this one is not valid for this shift
            continue

        # Look at the next registrar, just in case they worked less of this shift type
        next_reg = registrars[(idx + 1) % len(registrars)][0]
        if not validators.validate(
            shift, next_reg, assignments, leaves=leaves, statuses=statuses
        ):
            # If the next registrar is not valid, then this registrar is the best choice
            return registrar
        elif compare_with_next_reg(registrar, next_reg, shift.type, assignments):
            # If next registrar worked less of this shift type, then this registrar is the best choice
            return next_reg
        else:
            return registrar

    raise NoOneAvailable("No one available")


def compare_with_next_reg(current_registrar, next_registrar, shift_type, assignments):
    """
    If the current registrar has more shiftType than the next registrar, then return True.
    """
    current_reg_count = len(
        filter_assignments(
            assignments,
            lambda a: (a.registrar == current_registrar)
            and (a.shift.type == shift_type),
        )
    )
    next_reg_count = len(
        filter_assignments(
            assignments,
            lambda a: (a.registrar == next_registrar) and (a.shift.type == shift_type),
        )
    )
    return current_reg_count > next_reg_count


def filter_assignments(assignments, filter_func):
    return list(filter(filter_func, assignments))


def same_registrar_yesterday(shift, proposed_assignments, previous_assignments) -> User:
    yesterday = shift.date - timedelta(1)

    return find_registrar(
        yesterday,
        shift.type,
        previous_assignments + proposed_assignments,
        "No one worked this shift yesterday",
    )


def last_weekend_registrar(shift, proposed_assignments, previous_assignments) -> User:
    delta = abs(shift.date.weekday() + 2)  # weekday starts from 0
    saturday = shift.date - timedelta(delta)

    return find_registrar(
        saturday,
        ShiftType.WEEKEND,
        previous_assignments + proposed_assignments,
        "No one worked last weekend",
    )


def find_registrar(date, shift_type, assignments, error_msg):
    try:
        last_shift = next(
            filter(
                lambda a: (a.shift.date == date) and (a.shift.type == shift_type),
                assignments,
            )
        )
        return last_shift.registrar
    except StopIteration:
        raise NoOneAvailable(error_msg)


def registrar_by_fatigue(
    registrars: list[User],
    assignments: list[Assignment],
    leaves: [Leave],
    statuses: [Status],
    until: date,
    recency_wgt: bool = True,
) -> [(User, int)]:
    """
    A key function that determines the next registrar to be rostered on.

    1. Calculate the fatigue weighting for each registrar.
    2. Stronger weighting on the last 7 days.
    3. Sort the list by fatigue weighting.
    """
    try:
        latest_shift_date = assignments[-1].shift.date if recency_wgt else None
    except IndexError:
        latest_shift_date = None

    result = []
    for registrar in registrars:
        total = 0

        leaves = list(filter(lambda l: l.registrar == registrar, leaves))
        total += leave_fatigue_wgt(leaves, until)

        statuses = list(filter(lambda s: s.registrar == registrar, statuses))
        total += status_fatigue_wgt(statuses, until)

        for assignment in assignments:
            if assignment.registrar == registrar:
                if latest_shift_date and (
                    assignment.shift.date >= latest_shift_date - timedelta(14)
                ):
                    recency_wgt = RECENCY_WGT
                else:
                    recency_wgt = 1
                total += shift_fatigue_wgt(assignment) * recency_wgt

        result.append((registrar, total))
    return sorted(result, key=lambda x: x[1])


def sort_assignments_by_date(assignments: list[Assignment]) -> list[Assignment]:
    """
    Sort assignments by date from earliest to latest.
    """
    return sorted(assignments, key=lambda a: a.shift.date)


def shift_to_assignment(shift: Shift, registrar: User) -> Assignment:
    return Assignment(shift, registrar)


def shift_fatigue_wgt(assignment: Assignment) -> float:
    """
    Calculates the fatigue weighting for a shift.

    If the shift has a fatigue override, then use that value.

    Otherwise if the shift is a LONG shift, then it is more tiring on Friday.
    If the registrar is not senior, then Wednesday is also more tiring.

    Note: WEEKEND and NIGHT has no fatigue weighting, because their RDOs are counted as shifts.
    """
    shift = assignment.shift
    registrar = assignment.registrar

    if shift.fatigue_override:
        return shift.fatigue_override

    elif shift.stat_day:
        return 2.0

    elif shift.type == ShiftType.LONG:
        if shift.date.weekday() == Weekday.FRI:
            return 1.5
        elif shift.date.weekday() == Weekday.WED and not registrar.profile.senior:
            return 1.5

    return 1


def leave_fatigue_wgt(leaves: list[Leave], until: date) -> float:
    """
    Only parental leave is given fatigue weighting.

    Every 5 day of parental leave is counted as 1 shift.
    """
    parental = list(
        filter(lambda l: (l.type == LeaveType.PARENT) and (l.date <= until), leaves)
    )
    return len(parental) / 5 * AVG_WEEKLY_FATIGUE


def status_fatigue_wgt(statuses: list[Status], until: date) -> float:
    """
    Only non-oncall status is given fatigue weighting.

    Every 7 day of non-oncall status is counted as 1 shift.
    """
    days = 0
    for status in filter(lambda s: s.not_oncall and s.end <= until, statuses):
        days += (status.end - status.start).days + 1
    return days / 7 * AVG_WEEKLY_FATIGUE


def is_start_of_set(shift: Shift) -> bool:
    """
    Determines if the shift is the first day of a shift block.

    If NIGHT shift, then Monday and Friday are first days.
    If WEEKEND shift, then Saturday is the first day.
    If WRDO shift, then Monday is the first day.
    """
    if shift.type == ShiftType.NIGHT:
        return shift.date.weekday() in [Weekday.MON, Weekday.FRI]
    elif shift.type == ShiftType.WEEKEND:
        return shift.date.weekday() == Weekday.SAT
    elif shift.type == ShiftType.WRDO:
        return shift.date.weekday() == Weekday.MON
    return False


def generate_leaves(start: date, end: date, type: LeaveType, registrar: User):
    """
    Generate a list of leaves from Start to End date.
    Saturdays and Sundays are excluded.
    """
    result = []
    for day in daterange(start, end):
        if day.weekday() not in [Weekday.SAT, Weekday.SUN]:
            result.append(Leave(date=day, type=type, registrar=registrar))
    return result


def registrar_assignment_date_distance(registrar, assignments):
    dates = [
        assignment.shift.date
        for assignment in assignments
        if (assignment.registrar == registrar)
        and (
            assignment.shift.type
            in [ShiftType.LONG, ShiftType.NIGHT, ShiftType.WEEKEND]
        )
    ]
    return average_date_distance(dates)


def average_date_distance(date_list):
    # Sort the list of dates
    sorted_dates = sorted(date_list)

    # Calculate differences between consecutive dates
    differences = [
        (sorted_dates[i] - sorted_dates[i - 1]).days
        for i in range(1, len(sorted_dates))
    ]

    # Calculate the average difference
    avg_difference = sum(differences) / len(differences) if differences else 0

    return avg_difference
