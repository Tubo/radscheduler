from collections import defaultdict
from datetime import date, timedelta

from django.db.models import F, OuterRef, Q, Subquery
from django.db.models.functions import Now

from radscheduler.core.models import Leave, Registrar, Settings, Shift
from radscheduler.roster import canterbury_holidays
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


def editor_roster(week: date) -> dict:
    """
    Everything the roster editor shows for the three weeks around `week`: the registrars on the roster
    (active ones and anyone with a shift or leave in the window), their shifts and leave, public holidays
    and the published date range.
    """
    start, end = calculate_3_week_range(week)
    dates = daterange(start, end)
    window = [dates[0], dates[-1]]
    shifts = list(Shift.objects.filter(date__range=window).order_by("date", "pk"))
    leaves = list(Leave.objects.filter(date__range=window).order_by("date", "pk"))
    registrars, _ = _merge_shifts_and_leaves(shifts, leaves, get_active_registrars(start, end))
    settings = Settings.objects.first()
    return {
        "week": week,
        "prev": week - timedelta(weeks=1),
        "next": week + timedelta(weeks=1),
        "today": date.today(),
        "dates": dates,
        "registrars": list(registrars.values()),
        "shifts": shifts,
        "leaves": leaves,
        "holidays": [{"date": day, "name": canterbury_holidays[day]} for day in dates if day in canterbury_holidays],
        "published": settings and {"start": settings.publish_start_date, "end": settings.publish_end_date},
    }


def publish_preview(start: date, end: date) -> dict:
    """
    How many shifts and leave registrars would start or stop seeing if the published range became
    start..end. Only assigned shifts and leave that isn't cancelled count.
    """
    settings = Settings.objects.first()
    new = Q(date__range=[start, end])
    current = Q(date__range=[settings.publish_start_date, settings.publish_end_date]) if settings else Q(pk__in=[])
    shifts = Shift.objects.exclude(registrar=None)
    leaves = Leave.objects.exclude(cancelled=True)
    return {
        "shifts_shown": shifts.filter(new & ~current).count(),
        "leave_shown": leaves.filter(new & ~current).count(),
        "shifts_hidden": shifts.filter(current & ~new).count(),
        "leave_hidden": leaves.filter(current & ~new).count(),
    }


def set_published(start: date, end: date) -> Settings:
    """Set the date range registrars can see. There is only ever one Settings row."""
    settings, _ = Settings.objects.update_or_create(
        singleton_id=1, defaults={"publish_start_date": start, "publish_end_date": end}
    )
    return settings


def add_shift(day: date, shift_type: str, registrar: Registrar, extra_duty: bool = False) -> Shift:
    return Shift.objects.create(
        date=day,
        type=shift_type,
        registrar=registrar,
        extra_duty=extra_duty,
        stat_day=day in canterbury_holidays,
    )


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
