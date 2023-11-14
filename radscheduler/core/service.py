from datetime import date, timedelta

from django.db.models import Case, F, Q, Value, When
from django.db.models.functions import Now
from pandas import DataFrame, concat

from radscheduler.core import mapper
from radscheduler.core.models import Leave, Registrar, Shift, Status
from radscheduler.roster import LeaveType, ShiftType, SingleOnCallRoster, StatusType, Weekday, canterbury_holidays
from radscheduler.roster.assigner import AutoAssigner
from radscheduler.roster.generator import generate_shifts, merge_shifts
from radscheduler.roster.models import DetailedShiftType
from radscheduler.roster.utils import daterange, filter_shifts_by_date_range


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
        .annotate(username=F("registrar__user__username"))
        .select_related("registrar", "user")
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


def active_registrars(start: date = None, end: date = None):
    """
    Given a date range, return all registrars who are active during that period.
    Active registrars are those that have not finished training yet.
    """
    start, end = default_start_and_end(start, end)
    registrars = Registrar.objects.exclude(start=None).annotate(days=(Now() - F("start")))
    registrars = registrars.exclude(Q(finish__lt=start) | Q(start__gt=end))
    return registrars


def build_registrar_table(registrars):
    df_registrars = DataFrame(registrars)
    df_registrars["year"] = df_registrars.days.dt.days // 365 + 1
    df_registrars.drop(["days"], axis=1, inplace=True)
    df_registrars.rename(columns={"user__username": "username"}, inplace=True)
    return df_registrars


def build_pivot_table(start, end, shifts, leaves, registrars):
    columns = ["id", "date", "registrar"]

    df_shifts = DataFrame(shifts, columns=columns)
    if not df_shifts.empty:
        df_shifts["id"] = "shift:" + df_shifts.id.astype("str")

    df_leaves = DataFrame(leaves, columns=columns)
    if not df_leaves.empty:
        df_leaves["id"] = "leave:" + df_leaves["id"].astype("str")

    df = concat([df_shifts, df_leaves])

    if df.empty:
        pivot = DataFrame(columns=["date", "holiday"])
    else:
        pivot = df.pivot_table(index="date", columns="registrar", values="id", aggfunc="first")
    pivot.reset_index(inplace=True)
    pivot.fillna("", inplace=True)
    pivot["holiday"] = pivot.date.map(lambda d: canterbury_holidays.get(d, ""))
    pivot.date = pivot.date.astype("str")
    return pivot


def retrieve_roster(start: date = None, end: date = None):
    start, end = default_start_and_end(start, end)

    shifts = Shift.objects.filter(date__range=[start, end])
    shift_dict = {shift.id: mapper.shift_to_dict(shift) for shift in shifts}

    leaves = Leave.objects.filter(date__range=[start, end])
    leave_dict = {leave.id: mapper.leave_to_dict(leave) for leave in leaves}

    statuses = Status.objects.exclude(Q(end__lt=start) | Q(start__gt=end))
    status_dict = [mapper.status_to_dict(status) for status in statuses]

    registrars = active_registrars(start, end)
    df_registrars = build_registrar_table(registrars.values("id", "user__username", "days"))

    pivot = build_pivot_table(
        start,
        end,
        shifts.values("id", "date", "registrar"),
        leaves.values("id", "date", "registrar"),
        df_registrars,
    )

    result = {
        "columns": df_registrars.to_dict(orient="records"),
        "table": pivot.to_dict(orient="records"),
        "shifts": shift_dict,
        "leaves": leave_dict,
        "statuses": status_dict,
    }
    return result


def fill_shifts(start: date, end: date):
    registrars = Registrar.objects.exclude(finish__lte=start).select_related("user")
    registrars = list(map(mapper.registrar_from_db, registrars))

    leaves = Leave.objects.filter(date__range=[start, end]).select_related("registrar", "registrar__user")
    leaves = list(map(mapper.leave_from_db, leaves))

    statuses = (
        Status.objects.filter(Q(end__gte=start) | Q(start__lte=end))
        .annotate(username=F("registrar__user__username"))
        .select_related("registrar", "registrar__user")
    )
    statuses = list(map(mapper.status_from_db, statuses))

    shifts_in_db = Shift.objects.filter(date__range=[start - timedelta(days=7), end]).select_related(
        "registrar", "registrar__user"
    )
    filled = list(map(mapper.shift_from_db, shifts_in_db))
    unfilled = generate_shifts(SingleOnCallRoster, start, end, filled)

    assigner = AutoAssigner(registrars=registrars, unfilled=unfilled, filled=filled, leaves=leaves, statuses=statuses)
    result = assigner.fill_roster()
    result = filter_shifts_by_date_range(result, start, end)
    return result


def group_shifts_by_date_and_type(start: date, end: date, shifts):
    """
    Group shifts by date and type. If the shift is outside the date range, it is ignored.
    """
    result = {
        day: {shiftType.value: [] for shiftType in ShiftType} for day in daterange(start, end + timedelta(days=1))
    }

    for shift in shifts:
        result[shift.date][shift.type].append(shift)

    result = dict(sorted(result.items(), key=lambda item: item[0]))
    return result


def breakdown_before_and_after(shifts):
    result = {}
    for shift in shifts:
        shift_type = DetailedShiftType.from_shift(shift).value

        if shift.registrar is None:
            continue

        if result.get(shift.registrar.username):
            result[shift.registrar.username][shift_type] += 1
        else:
            registrar = {shift_type.value: 0 for shift_type in DetailedShiftType}
            registrar[shift_type] = 1
            result[shift.registrar.username] = registrar
    return result


def shifts_table(shifts):
    shifts = [mapper.shift_to_dict(shift) for shift in shifts]
    df = DataFrame(shifts)
    pivot = df.pivot_table(index="date", columns="type", values="username", aggfunc="first")
    pivot.reset_index(inplace=True)
    pivot.fillna("", inplace=True)
    pivot["date"] = pivot.date.astype("str")
    return pivot.to_dict(orient="records")


def retrieve_workload_breakdown(start: date = None, end: date = None):
    start, end = default_start_and_end(start, end)

    registrars = Registrar.objects.exclude(start=None)
    shifts = Shift.objects.filter(
        date__range=[start, end],
        type__in=[ShiftType.LONG, ShiftType.NIGHT],
        extra_duty=False,
    ).annotate(
        type_=Case(
            When(
                Q(type=ShiftType.LONG) & Q(date__iso_week_day__in=[Weekday.SAT, Weekday.SUN]),
                then=Value("WEEKEND"),
            ),
            When(
                Q(type=ShiftType.NIGHT)
                & Q(
                    date__iso_week_day__in=[
                        Weekday.FRI,
                        Weekday.SAT,
                        Weekday.SUN,
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
        workload["LONG"] * 1 + workload["NIGHT"] * 7 + workload["WEEKEND"] * 4 + workload["WKD NIGHT"] * 5
    )
    workload = workload.merge(df_registrars, left_index=True, right_on="id", how="left")
    workload.drop(["id"], axis=1, inplace=True)
    return workload


def generate_buddy_shifts(start, end):
    pass


def save_assignments(assignments):
    pass
