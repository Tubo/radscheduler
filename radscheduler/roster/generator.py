from datetime import date, timedelta

import holidays

from .models import DetailedShiftType, LeaveType, Shift, ShiftType, Weekday
from .rosters import SingleOnCallRoster
from .utils import daterange, filter_shifts, sort_shifts_by_date

canterbury_holidays = holidays.country_holidays("NZ", subdiv="CAN")


def generate_shifts(roster, start: date, end: date, filled: [Shift] = []) -> list[Shift]:
    """
    Generate a list of shifts from Start to End date.
    Public holidys should be stat days.

    If a shift is already filled, then it is not generated.
    """
    results = []

    for day in daterange(start, end + timedelta(days=1)):
        match day.weekday():
            case Weekday.MON:
                results.extend(_gen_shifts(day, roster.MON, filled))
            case Weekday.TUE:
                results.extend(_gen_shifts(day, roster.TUE, filled))
            case Weekday.WED:
                results.extend(_gen_shifts(day, roster.WED, filled))
            case Weekday.THUR:
                results.extend(_gen_shifts(day, roster.THUR, filled))
            case Weekday.FRI:
                results.extend(_gen_shifts(day, roster.FRI, filled))
            case Weekday.SAT:
                results.extend(_gen_shifts(day, roster.SAT, filled))
            case Weekday.SUN:
                results.extend(_gen_shifts(day, roster.SUN, filled))

    results = [mark_stat_day(shift, roster.STAT_DAY_SHIFTS, roster.STAT_NIGHT_SHIFTS) for shift in results]
    return results


def _gen_shifts(day, shifts, filled) -> [Shift]:
    result = []
    for shiftType, count in shifts:
        for i in range(count):
            series = i + 1
            identical_shifts = [
                shift for shift in filled if shift.same_shift(Shift(date=day, type=shiftType, series=series))
            ]
            if not identical_shifts:
                result.append(Shift(date=day, type=shiftType, series=series))
    return result


def mark_stat_day(shift: Shift, day_shifts: [ShiftType], night_shifts: [ShiftType]) -> Shift:
    """
    Change a shift to a stat day if it falls on a public holiday.
    Public holidays are never on weekends per NZ law.

    If a LONG, WEEKEND, RDO falls on a stat day, it should be a stat day.
    If a NIGHT shift falls starts on or finishes on a stat day, it should be counted.
    Post night sleep day should not be a stat day according to clause 17.4.6
    """
    if (shift.date in canterbury_holidays) and (shift.type in day_shifts + night_shifts):
        shift.stat_day = True

    elif shift.type in night_shifts:
        tomorrow = shift.date + timedelta(1)
        if tomorrow in canterbury_holidays:
            shift.stat_day = True

    return shift


def merge_shifts(*args) -> list[Shift]:
    """
    Merge shifts that are the same date and type.

    If the shift has a registrar, then the registrar is kept.
    """
    shifts = [shift for arg in args for shift in arg]
    result = []
    sorted_shifts = sorted(shifts, key=lambda shift: (shift.date, shift.type, shift.series))
    for i, shift in enumerate(sorted_shifts):
        if next_shift := sorted_shifts[i + 1] if i + 1 < len(sorted_shifts) else None:
            if shift.same_shift(next_shift):
                if shift.registrar:
                    next_shift.registrar = shift.registrar
                    next_shift.id = shift.id
                continue
        result.append(shift)
    return sort_shifts_by_date(result)
