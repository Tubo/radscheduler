from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta

from django.db.models import F, OuterRef, Q, Subquery
from django.db.models.functions import Now

from radscheduler.core import domain_mapper
from radscheduler.core.models import Leave, Registrar, Settings, Shift, Status
from radscheduler.roster import canterbury_holidays, rules
from radscheduler.roster.models import DetailedShiftType, ShiftType, Weekday
from radscheduler.roster.utils import daterange

# The department's cover: what each day needs filled. Each requirement lists the shift types that meet it.
# A public holiday is staffed like a weekend.
COVER = {
    "weekday": [["SWING"], ["NIGHT"]],
    "weekend": [["SWING", "LONG"], ["NIGHT"]],
    "holiday": [["SWING", "LONG"], ["NIGHT"]],
}

# On-call load per shift, from the department's workload formula: a block of 4 weekday nights weighs 7,
# a weekend of long days 6, a block of 3 weekend nights 5, and the total is divided by 10. Swing days
# take a long day's weight, since both add the same evening to an ordinary day. Help desk, RDO and sleep
# days carry no on-call load, and extra duties don't count.
WORKLOAD_WEIGHTS = {
    ("LONG", False): 1,
    ("LONG", True): 6 / 2,
    ("SWING", False): 1,
    ("SWING", True): 6 / 2,
    ("NIGHT", False): 7 / 4,
    ("NIGHT", True): 5 / 3,
}
WORKLOAD_WEEKS = 26
# How far either side of a checked range the contract checks look, so limits over 7 or 14 days see the
# shifts just outside it.
CHECK_MARGIN = timedelta(days=14)


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
    (active ones and anyone with a shift or leave in the window), their shifts, leave and statuses, public
    holidays, the published date range, and the checks: contract rule breaks and each registrar's workload.
    """
    start, end = calculate_3_week_range(week)
    dates = daterange(start, end)
    window = [dates[0], dates[-1]]
    shifts = list(Shift.objects.filter(date__range=window).order_by("date", "pk"))
    leaves = list(
        Leave.objects.filter(date__range=window)
        .select_related("reg_decided_by", "dot_decided_by")
        .order_by("date", "pk")
    )
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
        "statuses": list(
            Status.objects.filter(start__lte=window[1], end__gte=window[0]).order_by("registrar_id", "start")
        ),
        "holidays": [{"date": day, "name": canterbury_holidays[day]} for day in dates if day in canterbury_holidays],
        "published": settings and {"start": settings.publish_start_date, "end": settings.publish_end_date},
        "checks": editor_checks(week),
    }


def editor_checks(week: date) -> dict:
    """
    The roster's rule breaks in the editor's three weeks around `week`, apart from those a department variance
    covers, and everyone's workload up to its end.
    """
    start, end = calculate_3_week_range(week)
    last = end - timedelta(days=1)
    violations = roster_violations(start, last)
    return {
        "violations": [v for v in violations if not v.variance],
        "variances": [v for v in violations if v.variance],
        "workload": workload(last),
    }


def roster_violations(
    start: date, end: date, registrar_id: int | None = None, without_leave: Iterable[int] = ()
) -> list[rules.Violation]:
    """
    Contract and department rule breaks that touch any day from `start` to `end`, for everyone or for one
    registrar, as if the leave in `without_leave` hadn't been asked for. Leave that is cancelled or declined
    doesn't count; leave still waiting for approval does, so a clash shows before it is approved.
    """
    around = [start - CHECK_MARGIN, end + CHECK_MARGIN]
    whose = Q(registrar_id=registrar_id) if registrar_id else Q()
    shifts, leaves, statuses = domain_mapper.roster_from_db(
        Shift.objects.filter(whose, date__range=around, registrar__isnull=False),
        Leave.objects.filter(whose, date__range=around, cancelled=False)
        .exclude(reg_approved=False)
        .exclude(dot_approved=False)
        .exclude(pk__in=list(without_leave)),
        Status.objects.filter(whose, start__lte=around[1], end__gte=around[0]),
    )
    violations = rules.check_roster(shifts, leaves, statuses, period=(start, end))
    touching = [v for v in violations if any(start <= day <= end for day in v.dates)]
    return sorted(touching, key=lambda v: (v.dates[0], v.registrar.username, v.rule))


def shift_load(shift: Shift) -> float:
    """A shift's weight in the workload formula; nights from Friday to Sunday are weekend nights."""
    weekend_from = Weekday.FRI if shift.type == ShiftType.NIGHT else Weekday.SAT
    return WORKLOAD_WEIGHTS.get((shift.type, shift.date.weekday() >= weekend_from), 0)


def workload(end: date) -> list[dict]:
    """Each registrar's on-call load over the `WORKLOAD_WEEKS` weeks up to `end`, for those with any."""
    since = end - timedelta(weeks=WORKLOAD_WEEKS) + timedelta(days=1)
    shifts = Shift.objects.filter(date__range=[since, end], registrar__isnull=False, extra_duty=False)
    loads: dict[int, float] = defaultdict(float)
    for shift in shifts.only("date", "type", "registrar_id"):
        loads[shift.registrar_id] += shift_load(shift)
    return [{"registrar": pk, "load": round(load / 10, 1)} for pk, load in sorted(loads.items())]


def cover_rule(day: date) -> list[list[str]]:
    if day in canterbury_holidays:
        return COVER["holiday"]
    return COVER["weekend" if day.weekday() >= Weekday.SAT else "weekday"]


def cover_gaps(days: list[date]) -> list[dict]:
    """The cover requirements nobody is rostered for on each of `days`: [{"date", "needs": [[types]]}]."""
    if not days:
        return []
    rostered = defaultdict(set)
    for shift in Shift.objects.filter(date__range=[min(days), max(days)], registrar__isnull=False):
        rostered[shift.date].add(shift.type)
    gaps = []
    for day in days:
        needs = [types for types in cover_rule(day) if not rostered[day] & set(types)]
        if needs:
            gaps.append({"date": day, "needs": needs})
    return gaps


# The most newly published days the preview checks for gaps and rule breaks. A date box being typed into
# passes through years like 0002, so a request can span centuries; the counts stay exact, the checks stop here.
PREVIEW_CHECK_DAYS = 366


def newly_published_days(start: date, end: date, settings: Settings | None, limit: int) -> tuple[list[date], bool]:
    """
    Up to `limit` days, in order, that are in start..end but not in the current published range, and whether
    there were more.
    """
    if settings:
        spans = [
            (start, min(end, settings.publish_start_date - timedelta(days=1))),
            (max(start, settings.publish_end_date + timedelta(days=1)), end),
        ]
    else:
        spans = [(start, end)]
    days = []
    for first, last in spans:
        day = first
        while day <= last:
            if len(days) == limit:
                return days, True
            days.append(day)
            day += timedelta(days=1)
    return days, False


def publish_preview(start: date, end: date) -> dict:
    """
    How many shifts and leave registrars would start or stop seeing if the published range became
    start..end, and the state of the days they would start seeing: cover gaps, rule breaks and leave still
    waiting for a decision. Only assigned shifts and leave that isn't cancelled count, and rule breaks a
    department variance covers don't. Gaps and rule breaks are checked for the first `PREVIEW_CHECK_DAYS` of
    those days; `checked_to` names the last one checked when the rest weren't.
    """
    settings = Settings.objects.first()
    new = Q(date__range=[start, end])
    current = Q(date__range=[settings.publish_start_date, settings.publish_end_date]) if settings else Q(pk__in=[])
    shifts = Shift.objects.exclude(registrar=None)
    leaves = Leave.objects.exclude(cancelled=True)
    shown, more = newly_published_days(start, end, settings, PREVIEW_CHECK_DAYS)
    checked = set(shown)
    violations = roster_violations(shown[0], shown[-1]) if shown else []
    return {
        "shifts_shown": shifts.filter(new & ~current).count(),
        "leave_shown": leaves.filter(new & ~current).count(),
        "shifts_hidden": shifts.filter(current & ~new).count(),
        "leave_hidden": leaves.filter(current & ~new).count(),
        "gaps": cover_gaps(shown),
        "violations": [v for v in violations if not v.variance and checked.intersection(v.dates)],
        "leave_waiting": leaves.filter(new & ~current)
        .exclude(reg_approved=False)
        .exclude(dot_approved=False)
        .exclude(reg_approved=True, dot_approved=True)
        .count(),
        "checked_to": shown[-1] if more else None,
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
