"""
Roster rules from the registrars' collective agreement, plus the department's own rules.

Each rule takes one registrar's timeline and returns the violations it finds. Rules work on
the hours of each duty (see `SHIFT_HOURS`), so the agreement's hour and calendar-day limits
can be written the way the agreement states them.

A contract is a tuple of rules with their parameters and clause numbers bound. Most
differences between agreements are numbers, so a new contract reuses the same rules.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import partial
from itertools import groupby, pairwise

from radscheduler.roster.models import Leave, LeaveType, Registrar, Shift, ShiftType, Status, StatusType, Weekday

LONG_DAY_HOURS = 10


@dataclass(frozen=True)
class Violation:
    rule: str
    clause: str | None  # None for department rules
    registrar: Registrar = field(compare=False)
    dates: tuple[date, ...]
    message: str


@dataclass
class Timeline:
    """One registrar's shifts, leave and statuses, with shifts sorted by start."""

    registrar: Registrar
    shifts: list[Shift]
    leaves: list[Leave] = field(default_factory=list)
    statuses: list[Status] = field(default_factory=list)

    @property
    def duties(self) -> list[Shift]:
        return [shift for shift in self.shifts if shift.is_duty]

    @property
    def long_days(self) -> list[Shift]:
        return [shift for shift in self.duties if shift.hours > LONG_DAY_HOURS]

    @property
    def night_blocks(self) -> list[list[Shift]]:
        """Runs of night duties on consecutive dates."""
        blocks = []
        for night in (shift for shift in self.duties if shift.type == ShiftType.NIGHT):
            if blocks and night.date - blocks[-1][-1].date == timedelta(days=1):
                blocks[-1].append(night)
            else:
                blocks.append([night])
        return blocks

    def violation(self, rule, clause, dates, message) -> Violation:
        return Violation(rule, clause, self.registrar, tuple(sorted(set(dates))), message)


Rule = Callable[[Timeline], Iterable[Violation]]


def weekend_of(shift: Shift) -> date | None:
    """
    The Saturday of the weekend a duty falls in, or None if it is a weekday duty.

    A weekend starts when Friday's day duty finishes, so a Friday night is part of it (STONZ 21.4.2).
    """
    saturday = shift.date + timedelta(days=Weekday.SAT - shift.date.weekday())
    weekend_start = datetime.combine(saturday - timedelta(days=1), time(22))
    weekend_end = datetime.combine(saturday + timedelta(days=2), time(0))
    if shift.start < weekend_end and shift.end > weekend_start:
        return saturday
    return None


def _start(shift: Shift) -> datetime:
    return shift.start if shift.is_duty else datetime.combine(shift.date, time(0))


def fmt(day: date) -> str:
    return day.strftime("%a %-d %b")


# Contract rules


def one_duty_per_day(t: Timeline, *, clause: str) -> Iterable[Violation]:
    """Only one period of rostered duty a day. A night that ends on the day another starts is fine."""
    for day, duties in groupby(t.duties, key=lambda shift: shift.date):
        duties = list(duties)
        if len(duties) > 1:
            names = " and ".join(ShiftType(shift.type).label.lower() for shift in duties)
            yield t.violation("one_duty_per_day", clause, [day], f"Rostered for a {names} on {fmt(day)}.")


def max_long_days(t: Timeline, *, limit=2, days=7, clause: str) -> Iterable[Violation]:
    """No more than `limit` long days (duties over 10 hours) in any `days` consecutive days."""
    long_dates = sorted({shift.date for shift in t.long_days})
    reported = set()
    for first in long_dates:
        window = {day for day in long_dates if first <= day < first + timedelta(days=days)}
        if len(window) > limit and not window <= reported:
            reported |= window
            yield t.violation(
                "max_long_days",
                clause,
                window,
                f"{len(window)} long days in {days} days from {fmt(first)}; the limit is {limit}.",
            )


def every_second_weekend_free(t: Timeline, *, clause: str) -> Iterable[Violation]:
    """
    At least every second weekend completely free from duty.

    Not modelled: STONZ 17.3.7, which allows two weekends in a row once every 5 to 6 weekends.
    """
    worked = sorted({saturday for shift in t.duties if (saturday := weekend_of(shift))})
    for previous, saturday in pairwise(worked):
        if saturday - previous == timedelta(days=7):
            yield t.violation(
                "every_second_weekend_free",
                clause,
                [previous, saturday],
                f"Works the weekends of {fmt(previous)} and {fmt(saturday)}; every second weekend must be free.",
            )


def min_break_between_duties(t: Timeline, *, hours=8, clause: str) -> Iterable[Violation]:
    """At least `hours` off duty between two periods of duty. Two duties on one day are left to one_duty_per_day."""
    duties = sorted(t.duties, key=lambda shift: shift.start)
    for previous, shift in pairwise(duties):
        gap = max(shift.start - previous.end, timedelta(0))
        if gap < timedelta(hours=hours) and shift.date != previous.date:
            yield t.violation(
                "min_break_between_duties",
                clause,
                [previous.date, shift.date],
                f"Only {gap / timedelta(hours=1):g} hours off between the {fmt(previous.date)} and "
                f"{fmt(shift.date)} duties; the minimum is {hours}.",
            )


def post_night_recovery(t: Timeline, *, long_block=4, long_rest=2, short_rest=1, clause: str) -> Iterable[Violation]:
    """
    After a block of nights, the rest of the day the last night ends plus `long_rest` days off
    when the block has `long_block` nights or more, or `short_rest` days off for a shorter block.
    """
    for block in t.night_blocks:
        finished = block[-1].end
        rest_days = long_rest if len(block) >= long_block else short_rest
        free_until = datetime.combine(finished.date() + timedelta(days=rest_days + 1), time(0))
        clashes = [shift for shift in t.duties if finished <= shift.start < free_until]
        if clashes:
            yield t.violation(
                "post_night_recovery",
                clause,
                [shift.date for shift in clashes],
                f"Rostered on {', '.join(fmt(shift.date) for shift in clashes)} after {len(block)} nights "
                f"ending {fmt(finished.date())}; needs the rest of that day plus {rest_days} days off.",
            )


def no_weekend_next_to_leave(t: Timeline, *, clause: str) -> Iterable[Violation]:
    """
    Someone on leave on the Friday before or the Monday after a weekend cannot be rostered that weekend.

    Lieu days don't count (STONZ 21.4.5). Someone whose leave ends on the Friday can still be rostered for the
    Sunday night (STONZ 21.4.3). Other leave counts unless it is marked as allowing an abutting weekend.
    """
    leave_dates = {leave.date for leave in t.leaves if leave.no_abutting_weekend and leave.type != LeaveType.LIEU}
    weekends = {}
    for shift in t.duties:
        if saturday := weekend_of(shift):
            weekends.setdefault(saturday, []).append(shift)

    for saturday, duties in sorted(weekends.items()):
        friday, monday = saturday - timedelta(days=1), saturday + timedelta(days=2)
        if monday in leave_dates:
            clashes, leave_day = duties, monday
        elif friday in leave_dates:
            sunday = saturday + timedelta(days=1)
            clashes = [shift for shift in duties if not (shift.type == ShiftType.NIGHT and shift.date == sunday)]
            leave_day = friday
        else:
            continue
        if clashes:
            yield t.violation(
                "no_weekend_next_to_leave",
                clause,
                [shift.date for shift in clashes],
                f"Rostered on the weekend of {fmt(saturday)} next to leave on {fmt(leave_day)}.",
            )


def lieu_day_notice(t: Timeline, *, notice=14, long_notice=28, clause: str) -> Iterable[Violation]:
    """
    A lieu day needs `notice` days' notice, or `long_notice` days' if it falls on a long day,
    night or weekend duty the registrar is rostered for.
    """
    for leave in t.leaves:
        if leave.type != LeaveType.LIEU or leave.created is None:
            continue
        rostered = [shift for shift in t.duties if shift.date == leave.date]
        heavy = any(
            shift.hours > LONG_DAY_HOURS or shift.type == ShiftType.NIGHT or weekend_of(shift) for shift in rostered
        )
        required = long_notice if heavy else notice
        given = (leave.date - leave.created.date()).days
        if given < required:
            yield t.violation(
                "lieu_day_notice",
                clause,
                [leave.date],
                f"Lieu day on {fmt(leave.date)} was requested {given} days ahead; it needs {required} days' notice.",
            )


# Department rules


def employed(t: Timeline) -> Iterable[Violation]:
    """Only rostered between the registrar's start and finish dates."""
    start, finish = t.registrar.start, t.registrar.finish
    outside = [shift.date for shift in t.shifts if shift.date < start or (finish and shift.date > finish)]
    if outside:
        yield t.violation("employed", None, outside, "Rostered outside their employment dates.")


def not_on_leave(t: Timeline) -> Iterable[Violation]:
    """No duty that overlaps a day of leave, including a night that ends on the morning of the leave."""
    for leave in t.leaves:
        day_start = datetime.combine(leave.date, time(0))
        day_end = day_start + timedelta(days=1)
        clashes = [shift for shift in t.duties if shift.start < day_end and shift.end > day_start]
        if clashes:
            yield t.violation(
                "not_on_leave",
                None,
                [leave.date],
                f"Rostered on {fmt(leave.date)} while on leave ({LeaveType(leave.type).label.lower()}).",
            )


def status_allows_duty(t: Timeline) -> Iterable[Violation]:
    """No duty that the registrar's status rules out, e.g. relievers, pre-exam, part-time days."""
    for status in t.statuses:
        clashes = [
            shift.date for shift in t.duties if status.start <= shift.date <= status.end and status.not_oncall(shift)
        ]
        if clashes:
            label = StatusType(status.type).label.lower()
            yield t.violation("status_allows_duty", None, clashes, f"Rostered while {label}.")


def no_back_to_back_long_days(t: Timeline) -> Iterable[Violation]:
    """No long days on consecutive dates, except a Saturday and Sunday worked as a pair."""
    long_days = t.long_days
    for previous, shift in pairwise(long_days):
        consecutive = shift.date - previous.date == timedelta(days=1)
        weekend_pair = previous.date.weekday() == Weekday.SAT
        if consecutive and not weekend_pair:
            yield t.violation(
                "no_back_to_back_long_days",
                None,
                [previous.date, shift.date],
                f"Long days on {fmt(previous.date)} and {fmt(shift.date)} back to back.",
            )


def no_long_day_before_weekend_nights(t: Timeline, *, days=5) -> Iterable[Violation]:
    """No long day in the `days` days before a block of weekend nights."""
    for block in t.night_blocks:
        weekend_nights = [night for night in block if weekend_of(night)]
        if not weekend_nights:
            continue
        first = weekend_nights[0].date
        clashes = [shift.date for shift in t.long_days if first - timedelta(days=days) <= shift.date < first]
        if clashes:
            yield t.violation(
                "no_long_day_before_weekend_nights",
                None,
                clashes,
                f"Long day within {days} days before weekend nights starting {fmt(first)}.",
            )


STONZ: tuple[Rule, ...] = (
    partial(one_duty_per_day, clause="STONZ 17.2.5"),
    partial(max_long_days, limit=2, days=7, clause="STONZ 17.2.2"),
    partial(every_second_weekend_free, clause="STONZ 17.3.5"),
    partial(min_break_between_duties, hours=8, clause="STONZ 17.4.2"),
    partial(post_night_recovery, long_block=4, long_rest=2, short_rest=1, clause="STONZ 17.4.6"),
    partial(no_weekend_next_to_leave, clause="STONZ 21.4"),
    partial(lieu_day_notice, notice=14, long_notice=28, clause="STONZ 24.1"),
)

DEPARTMENT: tuple[Rule, ...] = (
    employed,
    not_on_leave,
    status_allows_duty,
    no_back_to_back_long_days,
    no_long_day_before_weekend_nights,
)


def check_roster(
    shifts: Iterable[Shift],
    leaves: Iterable[Leave] = (),
    statuses: Iterable[Status] = (),
    rules: Iterable[Rule] = STONZ + DEPARTMENT,
) -> list[Violation]:
    """Check every registrar on the roster against `rules`. Unassigned shifts are ignored."""
    timelines: dict[str, Timeline] = {}
    for shift in sorted(shifts, key=_start):
        if shift.registrar is not None:
            timelines.setdefault(shift.registrar.username, Timeline(shift.registrar, [])).shifts.append(shift)
    for leave in leaves:
        if leave.registrar.username in timelines:
            timelines[leave.registrar.username].leaves.append(leave)
    for status in statuses:
        if status.registrar.username in timelines:
            timelines[status.registrar.username].statuses.append(status)

    rules = list(rules)
    return [violation for timeline in timelines.values() for rule in rules for violation in rule(timeline)]
