"""
Leave requests for the approval page: the days of leave grouped the way registrars asked for them, each with
the stretch of roster around it that shows whether it can be given. The page opens on an overview of them,
filtered and sorted, and draws the roster for those it is asked to review.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncSecond
from django.utils import timezone

from radscheduler.core.models import Leave, Registrar, Shift
from radscheduler.core.service import cover_rule, roster_violations
from radscheduler.roster import canterbury_holidays
from radscheduler.roster.models import LeaveType, Weekday
from radscheduler.roster.utils import daterange

# Days added within this long of each other belong to one request, as in the editor's "whole request".
TOGETHER = timedelta(minutes=2)
# The roster shown either side of a request: enough for the weekend next to it.
MARGIN = timedelta(days=2)
# Decided requests are those with a decision this recent.
DECIDED_SINCE = timedelta(days=30)
# How far either side of the days found to look for the rest of their requests.
REACH = timedelta(days=31)
# Earlier leave years shown beside a request's own: a registrar's five years of training.
EARLIER_YEARS = 5
# Requests drawn with their roster at once, for review; the overview lists the rest a page at a time.
REVIEW_LIMIT = 50
OVERVIEW_LIMIT = 100
# A day with this share of the roster on leave or more is busy, as on the page's darkest step.
BUSY = 0.3
# Leave added this many to the second was loaded in bulk (the move from the old system), so carries the time it
# was loaded rather than when it was asked for.
BULK = 50

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


def weight(portion: str) -> float:
    """A day of leave counts as one, or a half for a morning or an afternoon."""
    return 1 if portion == "ALL" else 0.5


def first_monday_of_february(year: int) -> date:
    first = date(year, 2, 1)
    return first + timedelta(days=-first.weekday() % 7)


def leave_year_start(day: date) -> date:
    """
    The start of the leave year `day` falls in. Registrars' leave is counted from the first Monday of
    February, when the training year begins.
    """
    start = first_monday_of_february(day.year)
    return start if day >= start else first_monday_of_february(day.year - 1)


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


def in_training():
    """The registrars the page lists leave for: those who haven't finished training."""
    return Registrar.objects.filter(Q(finish__isnull=True) | Q(finish__gte=timezone.localdate()))


def waits_on(days: list[Leave], approver: str | None) -> bool:
    """Whether a request has a day waiting for `approver`'s decision ("reg" or "dot"), or anyone's for None."""
    if approver is None:
        return any(map(needs_decision, days))
    return any(is_active(leave) and getattr(leave, f"{approver}_approved") is None for leave in days)


def waiting_count(approver: str | None) -> int:
    """
    How many requests of registrars in training have a day waiting for `approver`'s decision ("reg" or "dot"),
    or anyone's for None, counted as the page does.
    """
    decision = {f"{approver}_approved__isnull": True} if approver else {}
    seeds = list(Leave.objects.filter(WAITING, registrar__in=in_training(), **decision))
    return sum(waits_on(days, approver) for days in requests_with(seeds))


def request_status(days: list[Leave]) -> str:
    """
    Where a request stands as a whole: "waiting" while any day needs a decision, then "approved" if any day was
    approved by both, "declined" if none was, and "cancelled" if every day was.
    """
    if all(leave.cancelled for leave in days):
        return "cancelled"
    if any(map(needs_decision, days)):
        return "waiting"
    if any(is_active(leave) and leave.reg_approved and leave.dot_approved for leave in days):
        return "approved"
    return "declined"


STATUSES = ("mine", "waiting", "approved", "declined", "cancelled", "any")
SORTS = ("leave", "leave-desc", "asked-desc", "asked", "decided-desc", "registrar", "length-desc")


@dataclass(frozen=True)
class Filters:
    """
    Which requests to list and in what order. `status` is one of `STATUSES`, "mine" meaning those with a day
    waiting for `approver`; the dates keep requests with any day between them; `years` and `types` keep any
    of theirs, and nothing given keeps all.
    """

    status: str = "waiting"
    approver: str | None = None
    start: date | None = None
    end: date | None = None
    years: tuple[int, ...] = ()
    types: tuple[str, ...] = ()
    registrar: int | None = None
    sort: str = "leave"


def asked(days: list[Leave]):
    return min(leave.created for leave in days)


def bulk_loads() -> set:
    """The seconds in which leave was loaded in bulk, rather than asked for."""
    rows = (
        Leave.objects.annotate(second=TruncSecond("created"))
        .values("second")
        .annotate(n=Count("id"))
        .filter(n__gte=BULK)
        .values_list("second", flat=True)
    )
    return set(rows)


def asked_at(days: list[Leave], bulk: set):
    """When a request was asked for, or None for leave loaded in bulk, whose asking wasn't recorded."""
    first = asked(days)
    return None if first.replace(microsecond=0) in bulk else first


def request_of(pk: int) -> list[Leave] | None:
    """
    The whole request a day of leave belongs to, grouped as the overview groups it: cancelled days apart from
    the rest.
    """
    leave = Leave.objects.filter(pk=pk).first()
    if leave is None:
        return None
    rows = Leave.objects.filter(
        registrar_id=leave.registrar_id,
        cancelled=leave.cancelled,
        date__range=[leave.date - REACH, leave.date + REACH],
    ).select_related("reg_decided_by", "dot_decided_by")
    return next((days for days in group_requests(rows) if any(day.pk == pk for day in days)), None)


def length(days: list[Leave]) -> float:
    """Days asked for, a half day counting 0.5: those still taken, or all of them for a cancelled request."""
    taken = [leave for leave in days if is_active(leave)] or days
    return sum(weight(leave.portion) for leave in taken)


def find_requests(filters: Filters) -> list[list[Leave]]:
    """The requests of registrars in training that match `filters`, in its order."""
    registrars = in_training()
    if filters.years:
        registrars = registrars.filter(year__in=filters.years)
    if filters.registrar:
        registrars = registrars.filter(pk=filters.registrar)
    names = {r.pk: (r.user.name or r.user.username).lower() for r in registrars.select_related("user")}
    leaves = Leave.objects.filter(registrar_id__in=names)
    if filters.types:
        leaves = leaves.filter(type__in=filters.types)
    # Wide enough to take in the whole of a request that starts or ends within the dates.
    if filters.start:
        leaves = leaves.filter(date__gte=filters.start - REACH)
    if filters.end:
        leaves = leaves.filter(date__lte=filters.end + REACH)
    rows = list(leaves.select_related("reg_decided_by", "dot_decided_by"))
    # Cancelled days make requests of their own, so the rest group as the review does.
    requests = group_requests([leave for leave in rows if not leave.cancelled])
    requests += group_requests([leave for leave in rows if leave.cancelled])

    def matches(days: list[Leave]) -> bool:
        if filters.start and days[-1].date < filters.start or filters.end and days[0].date > filters.end:
            return False
        if filters.status == "mine":
            return filters.approver is not None and waits_on(days, filters.approver)
        return filters.status == "any" or request_status(days) == filters.status

    found = [days for days in requests if matches(days)]
    first = {"leave": lambda days: (days[0].date, days[0].registrar_id)}
    keys = {
        "leave": first["leave"],
        "leave-desc": first["leave"],
        "asked": asked,
        "asked-desc": asked,
        "decided-desc": lambda days: max(map(last_decided, days)),
        "registrar": lambda days: (names[days[0].registrar_id], days[0].date),
        "length-desc": lambda days: (length(days), -days[0].date.toordinal()),
    }
    found.sort(key=keys.get(filters.sort, first["leave"]), reverse=filters.sort.endswith("-desc"))
    return found


def leave_years(days: list[Leave], history: list[tuple]) -> list[dict]:
    """
    The registrar's leave by year and type, in days: the years the request falls in first, then up to
    `EARLIER_YEARS` before them, latest first. Each type counts the days approved by both, those still
    waiting, and the request's own, which are kept apart from the rest. Declined and cancelled leave doesn't
    count. `history` is the registrar's other leave as (pk, date, type, portion, reg_approved, dot_approved).
    """
    ids = {leave.pk for leave in days}
    lead = sorted({leave_year_start(leave.date) for leave in days})
    since = first_monday_of_february(lead[0].year - EARLIER_YEARS)
    tally = defaultdict(lambda: defaultdict(lambda: {"approved": 0, "waiting": 0, "request": 0}))
    for pk, day, type_, portion, reg, dot in history:
        start = leave_year_start(day)
        if pk not in ids and since <= start <= lead[-1]:
            tally[start][type_]["approved" if reg and dot else "waiting"] += weight(portion)
    for leave in filter(is_active, days):
        tally[leave_year_start(leave.date)][leave.type]["request"] += weight(leave.portion)

    order = list(LeaveType)
    earlier = sorted((start for start in tally if start < lead[0]), reverse=True)
    return [
        {
            "start": start,
            "end": first_monday_of_february(start.year + 1) - timedelta(days=1),
            "lead": start in lead,
            "types": [{"type": t, **tally[start][t]} for t in sorted(tally[start], key=order.index)],
        }
        for start in [*lead, *earlier]
    ]


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
    return describe(requests)


def matching_requests(filters: Filters, limit: int = REVIEW_LIMIT) -> dict:
    """The first `limit` requests that match `filters`, each with its roster as `leave_requests` gives it."""
    requests = find_requests(filters)
    return {**describe(requests[:limit]), "total": len(requests)}


def describe(requests: list[list[Leave]]) -> dict:
    """
    Each request with the roster around it, the registrars they name and the holidays in it; `total` counts
    them, and `matching_requests` replaces it with all that match.
    """
    if not requests:
        return {"requests": [], "registrars": [], "holidays": [], "total": 0}

    window = [min(days[0].date for days in requests) - MARGIN, max(days[-1].date for days in requests) + MARGIN]
    bulk = bulk_loads()
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
    # Each registrar's leave over the years, for counting what they've had.
    history = defaultdict(list)
    for registrar_id, *row in (
        Leave.objects.filter(
            registrar_id__in={days[0].registrar_id for days in requests},
            cancelled=False,
            date__gte=first_monday_of_february(window[0].year - EARLIER_YEARS - 1),
        )
        .exclude(reg_approved=False)
        .exclude(dot_approved=False)
        .values_list("registrar_id", "pk", "date", "type", "portion", "reg_approved", "dot_approved")
    ):
        history[registrar_id].append(tuple(row))

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
                "asked": asked_at(days, bulk),
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
                "years": leave_years(days, history[registrar_id]),
            }
        )

    registrars = Registrar.objects.filter(pk__in=seen).select_related("user").order_by("-year", "user__username")
    return {
        "requests": out,
        "total": len(out),
        "registrars": list(registrars),
        "holidays": [
            {"date": day, "name": canterbury_holidays[day]}
            for day in daterange(window[0], window[1] + timedelta(days=1))
            if day in canterbury_holidays
        ],
    }


def checks(described: dict) -> dict:
    """
    What a request's verdict turns on, from its roster as `describe` gives it: the rule breaks it causes, the
    cover it loses, the days asked for and how many of them aren't rostered yet, and the busiest of them, as
    those on leave out of the registrars on the roster.
    """
    asked_days = sorted({leave.date for leave in described["leaves"] if is_active(leave)})
    days = {day["date"]: day for day in described["days"]}
    mine = defaultdict(float)
    for leave in described["leaves"]:
        if is_active(leave):
            mine[leave.date] += weight(leave.portion)
    away = defaultdict(float)
    for other in described["away"]:
        away[other["date"]] += weight(other["portion"])
    peak = max(
        ((away[day] + mine[day], days[day]["registrars"]) for day in asked_days),
        key=lambda pair: pair[0] / max(1, pair[1]),
        default=(0, 0),
    )
    return {
        "breaks": len(described["violations"]),
        "lost": sum(len(days[day]["lost"]) for day in asked_days),
        "days": len(asked_days),
        "unrostered": sum(not days[day]["rostered"] for day in asked_days),
        "away": peak[0],
        "roster": peak[1],
    }


def overview(filters: Filters, offset: int = 0, limit: int = OVERVIEW_LIMIT) -> dict:
    """
    A page of the requests that match `filters`, a row each: who, what and when, where it stands, and for
    those still waiting, the checks behind their verdict. With the registrars in training, for the filters.
    """
    requests = find_requests(filters)
    page = requests[offset : offset + limit]
    bulk = bulk_loads()
    waiting = [days for days in page if any(map(needs_decision, days))]
    checked = {}
    if waiting:
        for described in describe(waiting)["requests"]:
            checked[described["leaves"][0].pk] = checks(described)
    rows = [
        {
            "key": days[0].pk,
            "registrar": days[0].registrar_id,
            "type": days[0].type,
            "portion": days[0].portion,
            "start": days[0].date,
            "end": days[-1].date,
            "days": length(days),
            "asked": asked_at(days, bulk),
            "decided": max(
                filter(None, (d for leave in days for d in (leave.reg_decided_at, leave.dot_decided_at))), default=None
            ),
            "status": request_status(days),
            "leaves": days,
            "comment": " / ".join(dict.fromkeys(c for c in (leave.comment.strip() for leave in days) if c)),
            "checks": checked.get(days[0].pk),
        }
        for days in page
    ]
    registrars = in_training().select_related("user").order_by("-year", "user__username")
    return {"rows": rows, "total": len(requests), "registrars": list(registrars)}
