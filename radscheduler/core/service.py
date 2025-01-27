from datetime import date, timedelta

from django.db import IntegrityError
from django.db.models import Case, F, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Now
from pandas import DataFrame, concat

from radscheduler.core import domain_mapper
from radscheduler.core.models import Leave, Registrar, Shift, Status
from radscheduler.roster import LeaveType, ShiftType, SingleOnCallRoster, StatusType, Weekday, canterbury_holidays
from radscheduler.roster.assigner import AutoAssigner
from radscheduler.roster.generator import generate_shifts, merge_shifts
from radscheduler.roster.models import DetailedShiftType
from radscheduler.roster.utils import daterange, filter_shifts_by_date_range
from radscheduler.roster.validators import validate_roster


def calculate_3_week_range(someday: date):
    """
    Given a date, return the start and end of the 3-week period that contains that date.
    """
    first_day_of_week = someday - timedelta(days=someday.weekday())
    start = first_day_of_week - timedelta(days=7)
    end = first_day_of_week + timedelta(days=14)
    return start, end


def _merge_shifts_and_leaves(shifts, leaves, start, end):
    # Get all active registrars
    active_registrars = get_active_registrars(start, end).all()
    active_registrars_ids = set(reg.id for reg in active_registrars)

    # Get all registrars in the shifts and leaves
    registrar_ids = set(shift.registrar.id for shift in shifts) | set(leave.registrar.id for leave in leaves)

    # Retrieve all registrars if the active registrars are not a superset of the registrars in the shifts and leaves
    if not active_registrars_ids.issuperset(registrar_ids):
        active_registrars = Registrar.objects.filter(id__in=registrar_ids | active_registrars_ids).select_related(
            "user"
        )

    # Create a dictionary of shifts and leaves for each date and for each registrar:
    events = {registrar: {} for registrar in registrar_ids}
    for shift in shifts:
        if shift.date not in events[shift.registrar_id]:
            events[shift.registrar_id][shift.date] = {"shifts": [], "leaves": []}
        events[shift.registrar_id][shift.date]["shifts"].append(shift)

    for leave in leaves:
        if leave.date not in events[leave.registrar_id]:
            events[leave.registrar_id][leave.date] = {"shifts": [], "leaves": []}
        events[leave.registrar_id][leave.date]["leaves"].append(leave)

    registrars = {reg.id: reg for reg in sorted(active_registrars, key=lambda reg: (reg.year, reg.user.username))}
    return registrars, events


def get_events(someday: date, shift_types, leave_types):
    """
    Retrieve all events in the given date range.
    """
    start, end = calculate_3_week_range(someday)
    shifts = Shift.objects.filter(date__range=[start, end], type__in=shift_types).select_related(
        "registrar", "registrar__user"
    )
    leaves = Leave.objects.filter(date__range=[start, end], type__in=leave_types).select_related(
        "registrar", "registrar__user"
    )
    # Get all dates in the range
    dates = daterange(start, end)

    # Merge shifts and leaves into a single list grouped by registrar
    registrars, events = _merge_shifts_and_leaves(shifts, leaves, start, end)
    return registrars, dates, events


def default_start_and_end(start, end):
    if not (start and end):
        start = date.today() - timedelta(days=14 * 2)
        end = date.today() + timedelta(days=31)
    elif start and not end:
        end = date.today() + timedelta(days=31 * 6)
    elif not start and end:
        start = date.today() - timedelta(days=31 * 3)
    return (start, end)


def get_active_registrars(start: date = None, end: date = None):
    """
    Given a date range, return all registrars who are active during that period.
    Active registrars are those that have not finished training yet.
    """
    if not (start and end):
        start, end = default_start_and_end(start, end)
    registrars = Registrar.objects.exclude(start=None).annotate(days=(Now() - F("start")))
    registrars = registrars.exclude(Q(finish__lt=start) | Q(start__gt=end))
    registrars = registrars.order_by("user__username")
    registrars = registrars.select_related("user")
    return registrars


def active_and_available_registrars(day):
    """
    Given a date, return all registrars who are active during that period and
    with their leave and status annotated.
    """
    registrars = (
        Registrar.objects.exclude(start=None)
        .exclude(Q(finish__lt=day) | Q(start__gt=day))
        .annotate(
            on_leave=Subquery(Leave.objects.filter(registrar=OuterRef("pk"), date=day).values("type")[:1]),
        )
    )
    registrars = registrars.order_by("user__username")
    registrars = registrars.select_related("user")
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

    shifts = Shift.objects.filter(date__range=[start, end], registrar__isnull=False)
    shift_dict = {shift.id: domain_mapper.shift_to_dict(shift) for shift in shifts}

    leaves = Leave.objects.filter(date__range=[start, end])
    leave_dict = {leave.id: domain_mapper.leave_to_dict(leave) for leave in leaves}

    statuses = Status.objects.exclude(Q(end__lt=start) | Q(start__gt=end))
    status_dict = [domain_mapper.status_to_dict(status) for status in statuses]

    registrars = get_active_registrars(start, end)
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
    registrars = list(map(domain_mapper.registrar_from_db, registrars))

    leaves = Leave.objects.filter(date__range=[start, end]).select_related("registrar", "registrar__user")
    leaves = list(map(domain_mapper.leave_from_db, leaves))

    statuses = (
        Status.objects.filter(Q(end__gte=start) | Q(start__lte=end))
        .annotate(username=F("registrar__user__username"))
        .select_related("registrar", "registrar__user")
    )
    statuses = list(map(domain_mapper.status_from_db, statuses))

    shifts_in_db = Shift.objects.filter(date__range=[start, end]).select_related("registrar", "registrar__user")
    filled = list(map(domain_mapper.shift_from_db, shifts_in_db))
    unfilled = generate_shifts(SingleOnCallRoster, start, end, filled)

    assigner = AutoAssigner(registrars=registrars, unfilled=unfilled, filled=filled, leaves=leaves, statuses=statuses)
    result = assigner.fill_roster()
    assert validate_roster(result, leaves, statuses)

    result = filter_shifts_by_date_range(result, start, end)
    return result


def group_shifts_by_date_and_type(start: date, end: date, shifts):
    """
    Group shifts by date and type. If the shift is outside the date range, it is ignored.
    """
    result = {
        day: {shiftType.value: [] for shiftType in ShiftType} | {"holiday": canterbury_holidays.get(day)}
        for day in daterange(start, end + timedelta(days=1))
    }

    for shift in shifts:
        result[shift.date][shift.type].append(shift)

    result = dict(sorted(result.items(), key=lambda item: item[0]))
    return result


def shifts_breakdown(shifts):
    result = {}
    for shift in shifts:
        if shift.extra_duty:
            # Extra duty shifts are not counted towards workload
            continue

        shift_type = DetailedShiftType.from_shift(shift).value

        if shift.registrar is None:
            continue

        if result.get(shift.registrar.username):
            result[shift.registrar.username][shift_type] += 1
        else:
            registrar = {shift_type.value: 0 for shift_type in DetailedShiftType}
            registrar[shift_type] = 1
            result[shift.registrar.username] = registrar

    for registrar, breakdown in result.items():
        workload = (
            breakdown["LONG"] * 1
            + breakdown["NIGHT"] * 7 / 4
            + breakdown["WEEKEND"] * 6 / 2
            + breakdown["WEEKEND_NIGHT"] * 5 / 3
        ) / 10
        breakdown["WORKLOAD"] = round(workload, 1)
    result = {k: v for k, v in sorted(result.items(), key=lambda item: item[1]["WORKLOAD"], reverse=True)}
    return result


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


def assign_reg_to_shift(shift, registrar):
    pass


def swap_shifts(shift, registrar):
    try:
        shift.registrar = registrar
        shift.save()
    except IntegrityError:
        conflict_shift = Shift.objects.get(date=shift.date, type=shift.type, registrar=registrar)
