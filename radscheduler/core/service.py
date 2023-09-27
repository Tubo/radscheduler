from datetime import date, timedelta
from django.db.models import F
from django.db.models.functions import Now, TruncYear
from pandas import DataFrame, concat

from radscheduler.core.models import Registrar, Shift, ShiftType, Leave, LeaveType


def format_date(date):
    return date.strftime("%Y-%m-%d")


def map_shift_type_to_colour(shift_type):
    if shift_type == "LONG":
        return "#ff0000"
    elif shift_type == "NIGHT":
        return "#000000"
    else:
        return None


def retrieve_fullcalendar_events():
    result = []
    shifts = (
        Shift.objects.all()
        .annotate(username=F("registrar__username"))
        .select_related("registrar")
        .values("id", "date", "type", "username")
    )
    for shift in shifts:
        shift_name = ShiftType(shift["type"]).name
        result.append(
            {
                "id": shift["id"],
                "start": format_date(shift["date"]),
                "title": f"{shift_name}: {shift['username']}",
                "allDay": True,
                "backgroundColor": map_shift_type_to_colour(shift["type"]),
            }
        )
    return result


def retrieve_roster_events(start: date = None, end: date = None):
    registrars = (
        Registrar.objects.exclude(start=None)
        .annotate(days=(Now() - F("start")))
        .values("id", "username", "days")
    )

    shifts = Shift.objects.values("date", "type", "registrar")
    leaves = Leave.objects.values("date", "type", "registrar")

    if start and end:
        shifts = shifts.filter(date__range=[start, end])
        leaves = leaves.filter(date__range=[start, end])
    elif start:
        end = date.today() + timedelta(days=31 * 6)
        shifts = shifts.filter(date__range=[start, end])
        leaves = leaves.filter(date__range=[start, end])
    elif end:
        start = date.today() - timedelta(days=31 * 3)
        shifts = shifts.filter(date__range=[start, end])
        leaves = leaves.filter(date__range=[start, end])
    else:
        start = date.today() - timedelta(days=14 * 2)
        end = date.today() + timedelta(days=31)
        shifts = shifts.filter(date__range=[start, end])
        leaves = leaves.filter(date__range=[start, end])

    df_registrars = DataFrame(registrars)
    df_registrars["year"] = df_registrars.days.dt.days // 365 + 1

    df_shifts = DataFrame(shifts)
    df_shifts["type"] = df_shifts.type.apply(lambda x: ShiftType(x).label)
    df_leaves = DataFrame(leaves)
    df_leaves["type"] = df_leaves.type.apply(lambda x: LeaveType(x).label)
    df = concat([df_shifts, df_leaves])
    df["date"] = df.date.astype("str")
    df = df.pivot(index="registrar", columns="date", values="type")
    df = df_registrars.merge(df, right_index=True, left_on="id")
    df.drop(["id", "days"], axis=1, inplace=True)

    return df


def generate_buddy_shifts(start, end):
    pass


def save_assignments(assignments):
    pass
