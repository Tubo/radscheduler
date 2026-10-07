from collections import defaultdict
from datetime import date, timedelta

from django.db.models import F, OuterRef, Q, Subquery
from django.db.models.functions import Now

from radscheduler.core.models import Leave, Registrar, Shift
from radscheduler.roster.models import DetailedShiftType
from radscheduler.roster.utils import daterange


def calculate_3_week_range(someday: date):
    """
    Given a date, return the start and end of the 3-week period that contains that date.
    """
    first_day_of_week = someday - timedelta(days=someday.weekday())
    start = first_day_of_week - timedelta(days=7)
    end = first_day_of_week + timedelta(days=14)
    return start, end


def _merge_shifts_and_leaves(shifts, leaves, active_registrars):
    # Get all active registrars
    active_registrars_ids = {reg.id for reg in active_registrars}
    registrars_in_shifts = {shift.registrar_id for shift in shifts}
    registrars_in_leaves = {leave.registrar_id for leave in leaves}
    needed_registrars_ids = registrars_in_shifts | registrars_in_leaves | active_registrars_ids
    regs_qs = (
        Registrar.objects.filter(id__in=needed_registrars_ids)
        .select_related("user")
        .order_by("-year", "user__username")
    )
    registrars = {reg.id: reg for reg in regs_qs}

    # Create a dictionary of shifts and leaves for each date and for each registrar:
    events = defaultdict(lambda: defaultdict(lambda: {"shifts": [], "leaves": []}))

    for s in shifts:
        events[s.registrar_id][s.date]["shifts"].append(s)

    for leave in leaves:
        events[leave.registrar_id][leave.date]["leaves"].append(leave)

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
    active_registrars = get_active_registrars(start, end)
    # Merge shifts and leaves into a single list grouped by registrar
    registrars, events = _merge_shifts_and_leaves(shifts, leaves, active_registrars)
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
