from collections import namedtuple
from datetime import timedelta, date

from radscheduler.core.roster import (
    Assignment,
    DefaultRoster,
    daterange,
)
from radscheduler.core.models import (
    Registrar,
    Shift,
    Weekday,
    ShiftType,
    Leave,
    LeaveType,
)


def generate_leaves(start: date, end: date, type: LeaveType, registrar: Registrar):
    """
    Generate a list of leaves from Start to End date.
    Saturdays and Sundays are excluded.
    """
    result = []
    for day in daterange(start, end):
        if day.weekday() not in [Weekday.SAT, Weekday.SUN]:
            result.append(Leave(date=day, type=type, registrar=registrar))
    return result


def filter_shifts_by_date(shifts: list[Shift], date: date) -> list[Shift]:
    """
    Filter shifts by date
    """
    return list(filter(lambda s: s.date == date, shifts))


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
    results: dict = {}
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
    results: dict = {}
    for assignment in assignments:
        username = assignment.registrar.username
        shift = assignment.shift
        if shift.type not in results:
            results[shift.type] = {}
        if username not in results[shift.type]:
            results[shift.type][username] = 0
        results[shift.type][username] += 1
    return results


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
