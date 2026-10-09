"""
Leave requests for the approval page: the days of leave grouped the way registrars asked for them, each with
the stretch of roster around it that shows whether it can be given.
"""

from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone

from radscheduler.core.models import Leave, Registrar, Shift
from radscheduler.core.service import cover_rule, roster_violations
from radscheduler.roster import canterbury_holidays
from radscheduler.roster.models import Weekday
from radscheduler.roster.utils import daterange

# Days added within this long of each other belong to one request, as in the editor's "whole request".
TOGETHER = timedelta(minutes=2)
# The roster shown either side of a request: enough for the weekend next to it.
MARGIN = timedelta(days=2)
# Decided requests are those with a decision this recent.
DECIDED_SINCE = timedelta(days=30)
# How far either side of the days found to look for the rest of their requests.
REACH = timedelta(days=31)

WAITING = (
    Q(cancelled=False)
    & ~Q(reg_approved=False)
    & ~Q(dot_approved=False)
    & (Q(reg_approved__isnull=True) | Q(dot_approved__isnull=True))
)


def is_working_day(day: date) -> bool:
    return day.weekday() < Weekday.SAT and day not in canterbury_holidays


def is_active(leave: Leave) -> bool:
    """Leave that takes the registrar off the roster: not cancelled or declined."""
    return not leave.cancelled and leave.reg_approved is not False and leave.dot_approved is not False


def needs_decision(leave: Leave) -> bool:
    return is_active(leave) and (leave.reg_approved is None or leave.dot_approved is None)


def group_requests(leaves) -> list[list[Leave]]:
    """
    Days of leave grouped into requests: the same registrar, type and half of the day, added together, on
    working days with only weekends and public holidays between them.
    """
    requests = []
    for leave in sorted(leaves, key=lambda day: (day.registrar_id, day.type, day.portion, day.date)):
        if requests:
            last = requests[-1][-1]
            same = (last.registrar_id, last.type, last.portion) == (leave.registrar_id, leave.type, leave.portion)
            between = daterange(last.date + timedelta(days=1), leave.date)
            if same and abs(leave.created - last.created) < TOGETHER and not any(map(is_working_day, between)):
                requests[-1].append(leave)
                continue
        requests.append([leave])
    return requests


def last_decided(leave: Leave):
    """When the leave was last decided; for decisions made before that was kept, when it was last changed."""
    return max(filter(None, (leave.reg_decided_at, leave.dot_decided_at)), default=leave.last_edited)


def requests_with(seeds: list[Leave]) -> list[list[Leave]]:
    """The whole requests that the days in `seeds` belong to."""
    if not seeds:
        return []
    ids = {leave.pk for leave in seeds}
    rows = Leave.objects.filter(
        cancelled=False,
        registrar_id__in={leave.registrar_id for leave in seeds},
        date__range=[
            min(leave.date for leave in seeds) - REACH,
            max(leave.date for leave in seeds) + REACH,
        ],
    ).select_related("reg_decided_by", "dot_decided_by")
    return [days for days in group_requests(rows) if any(leave.pk in ids for leave in days)]


def leave_requests(decided: bool) -> dict:
    """
    The requests still waiting for a decision, soonest first, or those with every day settled and a decision
    in the last `DECIDED_SINCE`, latest decision first. Each comes with the roster from `MARGIN` before it to
    `MARGIN` after: the registrar's own shifts and other leave, everyone else on leave, how many registrars are
    on the roster, the cover each day would lose if the leave were given and the cover already short, and the
    registrar's rule breaks, those the leave causes apart from those already there.
    """
    if decided:
        since = timezone.now() - DECIDED_SINCE
        unrecorded = Q(reg_decided_at__isnull=True, dot_decided_at__isnull=True, last_edited__gte=since)
        decisions = Q(reg_decided_at__gte=since) | Q(dot_decided_at__gte=since) | unrecorded
        seeds = Leave.objects.filter(decisions, cancelled=False).exclude(reg_approved=None, dot_approved=None)
        requests = [days for days in requests_with(list(seeds)) if not any(map(needs_decision, days))]
        requests.sort(key=lambda days: max(map(last_decided, days)), reverse=True)
    else:
        waiting = list(Leave.objects.filter(WAITING))
        requests = [days for days in requests_with(waiting) if any(map(needs_decision, days))]
        requests.sort(key=lambda days: (days[0].date, days[0].registrar_id))
    if not requests:
        return {"requests": [], "registrars": [], "holidays": []}

    window = [min(days[0].date for days in requests) - MARGIN, max(days[-1].date for days in requests) + MARGIN]
    leaves_by_date = defaultdict(list)
    for leave in (
        Leave.objects.filter(date__range=window, cancelled=False)
        .exclude(reg_approved=False)
        .exclude(dot_approved=False)
        .select_related("reg_decided_by", "dot_decided_by")
        .order_by("date", "pk")
    ):
        leaves_by_date[leave.date].append(leave)
    shifts_by_date = defaultdict(list)
    for shift in Shift.objects.filter(date__range=window, registrar__isnull=False).order_by("date", "pk"):
        shifts_by_date[shift.date].append(shift)
    employed = list(Registrar.objects.exclude(start=None).values_list("start", "finish"))

    def on_roster(day: date) -> int:
        return sum(start <= day and (finish is None or day <= finish) for start, finish in employed)

    out, seen = [], set()
    for days in requests:
        registrar_id = days[0].registrar_id
        ids = {leave.pk for leave in days}
        dates = daterange(days[0].date - MARGIN, days[-1].date + MARGIN + timedelta(days=1))
        # A day off in full takes the registrar's own shifts out of the cover.
        off = {leave.date for leave in days if is_active(leave) and leave.portion == "ALL"}
        others = [leave for day in dates for leave in leaves_by_date[day] if leave.registrar_id != registrar_id]
        seen |= {registrar_id} | {leave.registrar_id for leave in others}

        def cover(day: date) -> dict:
            """The cover this leave would lose that day, and the cover already short without it."""
            before = {s.type for s in shifts_by_date[day]}
            after = {s.type for s in shifts_by_date[day] if not (s.registrar_id == registrar_id and day in off)}
            rule = cover_rule(day)
            return {
                "lost": [types for types in rule if before & set(types) and not after & set(types)],
                "short": [types for types in rule if not before & set(types)],
            }

        # A break is the leave's doing if it goes away without the leave; the rest were there already.
        with_leave = [v for v in roster_violations(dates[0], dates[-1], registrar_id) if not v.variance]
        without = roster_violations(dates[0], dates[-1], registrar_id, without_leave=ids)
        out.append(
            {
                "registrar": registrar_id,
                "leaves": days,
                "dates": dates,
                "shifts": [s for day in dates for s in shifts_by_date[day] if s.registrar_id == registrar_id],
                "other_leave": [
                    leave
                    for day in dates
                    for leave in leaves_by_date[day]
                    if leave.registrar_id == registrar_id and leave.pk not in ids
                ],
                "away": [
                    {
                        "registrar": leave.registrar_id,
                        "date": leave.date,
                        "type": leave.type,
                        "portion": leave.portion,
                        "approved": bool(leave.reg_approved and leave.dot_approved),
                    }
                    for leave in others
                ],
                "days": [
                    {
                        "date": day,
                        "registrars": on_roster(day),
                        "rostered": bool(shifts_by_date[day]),
                        **cover(day),
                    }
                    for day in dates
                ],
                "violations": [v for v in with_leave if v not in without],
                "existing_violations": [v for v in with_leave if v in without],
            }
        )

    registrars = Registrar.objects.filter(pk__in=seen).select_related("user").order_by("-year", "user__username")
    return {
        "requests": out,
        "registrars": list(registrars),
        "holidays": [
            {"date": day, "name": canterbury_holidays[day]}
            for day in daterange(window[0], window[1] + timedelta(days=1))
            if day in canterbury_holidays
        ],
    }
