from datetime import date, timedelta

from pandas import DataFrame

from radscheduler.roster.models import DetailedShiftType, Leave, LeaveType, Registrar, Shift, ShiftType, Weekday


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)


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


def filter_shifts(shifts, date, shift_type) -> [Shift]:
    return [shift for shift in shifts if (shift.date == date) and (shift.type == shift_type)]


def find_registrar_from_shifts(filtered, date, shift_type) -> Registrar:
    filtered = filter_shifts(filtered, date, shift_type)
    if len(filtered) == 1:
        return filtered[0].registrar
    return None


def sort_shifts_by_date(shifts: list[Shift]) -> list[Shift]:
    """
    Sort assignments by date from earliest to latest.
    """
    return sorted(shifts, key=lambda shift: shift.date)


def filter_shifts_by_date(shifts: list[Shift], date: date) -> list[Shift]:
    """
    Filter shifts by date
    """
    return list(filter(lambda s: s.date == date, shifts))


def filter_shifts_by_types(shifts: list[Shift], shift_types: list[ShiftType]) -> list[Shift]:
    """
    Filter shifts by type
    """
    return list(filter(lambda s: s.type in shift_types, shifts))


def filter_shifts_by_date_and_type(shifts: list[Shift], date: date, shift_type: ShiftType) -> list[Shift]:
    return list(filter(lambda s: s.date == date and s.type == shift_type, shifts))


def registrar_shift_distance(registrar, shifts):
    dates = [
        shift.date
        for shift in shifts
        if (shift.registrar == registrar) and (DetailedShiftType.from_shift(shift) == DetailedShiftType.LONG)
    ]
    return average_date_distance(dates)


def average_date_distance(date_list):
    # Sort the list of dates
    sorted_dates = sorted(date_list)

    # Calculate differences between consecutive dates
    differences = [(sorted_dates[i] - sorted_dates[i - 1]).days for i in range(1, len(sorted_dates))]

    # Calculate the average difference
    avg_difference = sum(differences) / len(differences) if differences else 0

    return avg_difference


def shift_to_dict(shift):
    return {
        "date": shift.date,
        "type": DetailedShiftType.from_shift(shift).label,
        "username": shift.registrar.username if shift.registrar else None,
    }


def shifts_to_dataframe(shifts):
    """
    Convert a list of shifts to a dataframe.
    """
    shifts = [shift_to_dict(shift) for shift in shifts]
    return DataFrame(shifts)


def shift_breakdown(df: DataFrame):
    pivot_table = df.pivot_table(index=["username"], columns=["type"], values="date", aggfunc="count")
    return pivot_table
