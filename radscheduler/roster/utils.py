from datetime import date, timedelta

from radscheduler.roster.models import Leave, LeaveType, Registrar, Weekday


def daterange(start_date, end_date):
    return [start_date + timedelta(n) for n in range(int((end_date - start_date).days))]


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
