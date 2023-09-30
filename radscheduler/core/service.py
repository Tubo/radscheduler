from datetime import date, timedelta
from django.db.models import F, Q, When, Case, Value
from django.db.models.functions import Now, TruncYear
from pandas import DataFrame, concat

from radscheduler.core.models import (
    Registrar,
    Shift,
    ShiftType,
    Leave,
    LeaveType,
    ISOWeekday,
)
from radscheduler.core.roster import canterbury_holidays, daterange


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


def default_start_and_end(start, end):
    if not (start and end):
        start = date.today() - timedelta(days=14 * 2)
        end = date.today() + timedelta(days=31)
    elif start and not end:
        end = date.today() + timedelta(days=31 * 6)
    elif not start and end:
        start = date.today() - timedelta(days=31 * 3)
    return (start, end)


def retrieve_roster_events(start: date = None, end: date = None):
    start, end = default_start_and_end(start, end)

    registrars = Registrar.objects.exclude(start=None).annotate(
        days=(Now() - F("start"))
    )

    shifts = Shift.objects.values("date", "type", "registrar", "extra_duty")
    leaves = Leave.objects.values("date", "type", "registrar", "portion")

    registrars = registrars.exclude(Q(finish__lt=start) | Q(start__gt=end))
    shifts = shifts.filter(date__range=[start, end])
    leaves = leaves.filter(date__range=[start, end])

    df_registrars = DataFrame(registrars.values("id", "username", "days"))
    df_registrars["year"] = df_registrars.days.dt.days // 365 + 1
    df_registrars["year"] = "Year " + df_registrars.year.astype("str")

    df_shifts = DataFrame(shifts)
    df_shifts["type"] = df_shifts.type.apply(lambda x: ShiftType(x).label)
    # Mark shift type with EXTRA DUTY
    df_shifts["extra_duty"] = df_shifts.extra_duty.apply(lambda x: "extra" if x else "")
    df_shifts["type"] = df_shifts["type"] + "," + df_shifts.extra_duty

    df_leaves = DataFrame(leaves)
    df_leaves["type"] = df_leaves.type.apply(lambda x: LeaveType(x).label)
    # Mark leave type with PORTION
    df_leaves["type"] = df_leaves.apply(
        lambda row: row["type"] + " " + row["portion"].lower()
        if row["portion"] != "ALL"
        else row["type"],
        axis=1,
    )

    df = concat([df_shifts, df_leaves])

    holidays = df["date"].drop_duplicates().apply(lambda x: canterbury_holidays.get(x))

    df["date"] = df.date.astype("str")

    pivot = df.pivot_table(
        index="date",
        columns="registrar",
        values="type",
        aggfunc=lambda x: ",".join(x),
    )
    pivot = df_registrars.merge(pivot.T, right_index=True, left_on="id", how="left")
    pivot.drop(["id", "days"], axis=1, inplace=True)

    return pivot


def retrieve_workload_breakdown(start: date = None, end: date = None):
    start, end = default_start_and_end(start, end)

    registrars = Registrar.objects.exclude(start=None)
    shifts = Shift.objects.filter(
        date__range=[start, end], type__in=[ShiftType.LONG, ShiftType.NIGHT]
    ).annotate(
        type_=Case(
            When(
                Q(type=ShiftType.LONG)
                & Q(date__iso_week_day__in=[ISOWeekday.SAT, ISOWeekday.SUN]),
                then=Value("WEEKEND"),
            ),
            When(
                Q(type=ShiftType.NIGHT)
                & Q(
                    date__iso_week_day__in=[
                        ISOWeekday.FRI,
                        ISOWeekday.SAT,
                        ISOWeekday.SUN,
                    ]
                ),
                then=Value("WKD NIGHT"),
            ),
            default=F("type"),
        )
    )

    df_registrars = DataFrame(registrars.values("id", "username"))
    df_shifts = DataFrame(shifts.values("registrar", "type_"))
    workload = df_shifts.groupby(["registrar", "type_"]).size().unstack().fillna(0)
    workload["FATIGUE"] = (
        workload["LONG"] * 1
        + workload["NIGHT"] * 7
        + workload["WEEKEND"] * 4
        + workload["WKD NIGHT"] * 5
    )
    workload = workload.merge(df_registrars, left_index=True, right_on="id", how="left")
    workload.drop(["id"], axis=1, inplace=True)
    return workload


def retrieve_date_annotations(start: date = None, end: date = None):
    start, end = default_start_and_end(start, end)
    dates = list(daterange(start, end))
    result = []
    for day in dates:
        holiday = canterbury_holidays.get(day)
        if holiday:
            result.append(
                {
                    "date": str(day),
                    "holiday": holiday,
                }
            )

    df = DataFrame(result)
    return df


def generate_buddy_shifts(start, end):
    pass


def save_assignments(assignments):
    pass
