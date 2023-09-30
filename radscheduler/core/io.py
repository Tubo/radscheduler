"""
Imports the history of shifts and leaves from a CSV file.

The file was exported from Google Sheets designed by the previous roster master (Dr. Ed Ganly).
"""
from datetime import date, datetime
import csv
import yaml

from radscheduler.core.models import Shift, ShiftType, Leave, LeaveType, Registrar
from radscheduler.core.roster import canterbury_holidays

shift_types = {
    "Long day": ShiftType.LONG,
    "Sleep": ShiftType.SLEEP,
    "Nights": ShiftType.NIGHT,
    "RDO": ShiftType.RDO,
    "Extra duty - long day": ShiftType.LONG,
    "Extra duty - nights": ShiftType.NIGHT,
}

leave_types = {
    "Lieu day": LeaveType.LIEU,
    "Annual leave": LeaveType.ANNUAL,
    "Annual leave - a.m.": LeaveType.ANNUAL,
    "Annual leave - p.m.": LeaveType.ANNUAL,
    "MEL": LeaveType.EDU,
    "MEL - a.m.": LeaveType.EDU,
    "MEL - p.m.": LeaveType.EDU,
    "Sick leave": LeaveType.SICK,
    "Sick leave - a.m.": LeaveType.SICK,
    "Sick leave - p.m.": LeaveType.SICK,
    "Parental leave": LeaveType.PARENTAL,
}


def import_history(filename: str, users: list[Registrar], start: date, end: date):
    """Imports the history of shifts and leaves from a CSV file.
    Specify a range to import from START to END.
    """
    rows = []
    with open(filename) as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    results = parse(rows, users, start, end)
    return results


def parse(rows, users, start, end):
    shifts = []
    leaves = []
    for row in rows:
        shift_or_leave = parse_row(row[0], row[1], row[2], start, end, users)
        if shift_or_leave:
            if isinstance(shift_or_leave, Shift):
                shifts.append(shift_or_leave)
            elif isinstance(shift_or_leave, Leave):
                leaves.append(shift_or_leave)
    return (shifts, leaves)


def parse_row(date, username, shift_type_str, start, end, users):
    date = datetime.strptime(date, "%d/%m/%Y").date()
    if start or end:
        keep = True
        if not start:
            keep = date <= end
        if not end:
            keep = date >= start
        if not (start <= date <= end) or not keep:
            return None

    if shift_type_str in shift_types:
        shift_type = shift_types[shift_type_str]
        extra = "Extra duty" in shift_type_str
        stat = date in canterbury_holidays
        user = users[username]
        return Shift(
            date=date, type=shift_type, registrar=user, extra_duty=extra, stat_day=stat
        )

    elif shift_type_str in leave_types:
        leave_type = leave_types[shift_type_str]
        user = users[username]
        if "a.m." in shift_type_str:
            portion = "AM"
        elif "p.m." in shift_type_str:
            portion = "PM"
        else:
            portion = "ALL"
        return Leave(date=date, type=leave_type, registrar=user, portion=portion)


def import_users(fname):
    with open(fname) as f:
        data = yaml.safe_load(f)
    result = {}
    for username, profile in data.items():
        senior = profile["senior"]
        start = datetime.strptime(profile["start"], "%d/%m/%Y").date()
        finish = datetime.strptime(profile["finish"], "%d/%m/%Y").date()
        result[username] = Registrar(
            username=username, senior=senior, start=start, finish=finish
        )
    return result
