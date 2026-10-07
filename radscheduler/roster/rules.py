"""
Roster rules from the registrars' collective agreement, plus the department's own rules.

Each rule takes one registrar's timeline and returns the violations it finds. Rules work on
the hours of each duty (see `SHIFT_HOURS`), so the agreement's hour and calendar-day limits
can be written the way the agreement states them. A timeline includes the ordinary weekdays
the registrar works between rostered shifts, which the roster doesn't store.

A contract is a tuple of rules with their parameters and clause numbers bound. Most
differences between agreements are numbers, so a new contract reuses the same rules.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import partial
from itertools import groupby, pairwise

from radscheduler.roster.canterbury import canterbury_holidays
from radscheduler.roster.models import (
    Leave,
    LeaveType,
    OrdinaryDay,
    Registrar,
    Shift,
    ShiftType,
    Status,
    StatusType,
    Weekday,
)
from radscheduler.roster.utils import daterange

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
    """One registrar's shifts, leave, statuses and ordinary days, with shifts sorted by start."""

    registrar: Registrar
    shifts: list[Shift]
    leaves: list[Leave] = field(default_factory=list)
    statuses: list[Status] = field(default_factory=list)
    ordinary_days: list[OrdinaryDay] = field(default_factory=list)

    @property
    def rostered(self) -> list[Shift]:
        """Rostered shifts that are periods of duty."""
        return [shift for shift in self.shifts if shift.is_duty]

    @property
    def duties(self) -> list[Shift | OrdinaryDay]:
        """All periods of duty, rostered or ordinary, sorted by start."""
        return sorted(self.rostered + self.ordinary_days, key=lambda duty: duty.start)

    @property
    def long_days(self) -> list[Shift]:
        return [shift for shift in self.rostered if shift.hours > LONG_DAY_HOURS]

    @property
    def night_blocks(self) -> list[list[Shift]]:
        """Runs of night duties on consecutive dates."""
        blocks = []
        for night in (shift for shift in self.rostered if shift.type == ShiftType.NIGHT):
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


def days_on_duty(duty: Shift | OrdinaryDay) -> list[date]:
    """Calendar days a duty touches; a night also counts the morning it finishes."""
    last = (duty.end - timedelta(microseconds=1)).date()
    return daterange(duty.date, last + timedelta(days=1))


def busy_periods(duties, *, days: int, measure: Callable[[list], float], limit: float):
    """
    Slide a `days`-long window over `duties` (sorted by date) and find where `measure(window)` exceeds `limit`.
    Overlapping windows are merged, so one busy stretch is reported once. Yields (duties, peak measure).
    """
    periods = []
    for first in sorted({duty.date for duty in duties}):
        window = [duty for duty in duties if first <= duty.date < first + timedelta(days=days)]
        value = measure(window)
        if value <= limit:
            continue
        if periods and first <= periods[-1][0][-1].date:
            merged, peak = periods[-1]
            periods[-1] = (merged + [duty for duty in window if duty not in merged], max(peak, value))
        else:
            periods.append((window, value))
    yield from periods


# Contract rules


def one_duty_per_day(t: Timeline, *, clause: str) -> Iterable[Violation]:
    """Only one period of rostered duty a day. A night that ends on the day another starts is fine."""
    for day, duties in groupby(t.rostered, key=lambda shift: shift.date):
        duties = list(duties)
        if len(duties) > 1:
            names = " and ".join(ShiftType(shift.type).label.lower() for shift in duties)
            yield t.violation("one_duty_per_day", clause, [day], f"Rostered for a {names} on {fmt(day)}.")


def max_long_days(t: Timeline, *, limit=2, days=7, clause: str) -> Iterable[Violation]:
    """No more than `limit` long days (duties over 10 hours) in any `days` consecutive days."""
    long_days = t.long_days
    for period, peak in busy_periods(long_days, days=days, measure=lambda w: len({d.date for d in w}), limit=limit):
        yield t.violation(
            "max_long_days",
            clause,
            [shift.date for shift in period],
            f"{peak} long days within {days} days between {fmt(period[0].date)} and {fmt(period[-1].date)}; "
            f"the limit is {limit}.",
        )


def max_hours(t: Timeline, *, limit: int, days: int, clause: str) -> Iterable[Violation]:
    """No more than `limit` hours on duty, ordinary days included, in any `days` consecutive days."""
    for period, peak in busy_periods(t.duties, days=days, measure=lambda w: sum(d.hours for d in w), limit=limit):
        yield t.violation(
            "max_hours",
            clause,
            [duty.date for duty in period],
            f"Up to {peak:g} hours on duty within {days} days between {fmt(period[0].date)} and "
            f"{fmt(period[-1].date)}; the limit is {limit}.",
        )


def max_consecutive_days(t: Timeline, *, limit=12, clause: str) -> Iterable[Violation]:
    """
    No more than `limit` consecutive days on duty, ordinary days included.

    Simplified: STONZ 17.3.1 asks for a 48-hour break after the run; this only checks the run's length.
    """
    worked = sorted({day for duty in t.duties for day in days_on_duty(duty)})
    runs = []
    for day in worked:
        if runs and day - runs[-1][-1] == timedelta(days=1):
            runs[-1].append(day)
        else:
            runs.append([day])
    for run in runs:
        if len(run) > limit:
            yield t.violation(
                "max_consecutive_days",
                clause,
                run,
                f"On duty {len(run)} days in a row from {fmt(run[0])} to {fmt(run[-1])}; the limit is {limit}.",
            )


def every_second_weekend_free(t: Timeline, *, clause: str) -> Iterable[Violation]:
    """
    At least every second weekend completely free from duty.

    Not modelled: STONZ 17.3.7, which allows two weekends in a row once every 5 to 6 weekends.
    """
    worked = sorted({saturday for shift in t.rostered if (saturday := weekend_of(shift))})
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
    for previous, shift in pairwise(t.duties):
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
    for shift in t.rostered:
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
        rostered = [shift for shift in t.rostered if shift.date == leave.date]
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
        clashes = [shift for shift in t.rostered if shift.start < day_end and shift.end > day_start]
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
            shift.date for shift in t.rostered if status.start <= shift.date <= status.end and status.not_oncall(shift)
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
    partial(max_hours, limit=72, days=7, clause="STONZ 17.1.2"),
    partial(max_hours, limit=140, days=14, clause="STONZ 17.1.4"),
    partial(one_duty_per_day, clause="STONZ 17.2.5"),
    partial(max_long_days, limit=2, days=7, clause="STONZ 17.2.2"),
    partial(max_consecutive_days, limit=12, clause="STONZ 17.3.1"),
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


def infer_ordinary_days(t: Timeline, start: date, end: date) -> list[OrdinaryDay]:
    """
    The weekdays from `start` to `end` the registrar works ordinary hours: employed, not a public holiday,
    no rostered shift of any kind (an RDO or sleep day is a day off), not on leave, and not a part-time
    non-working day.
    """
    rostered = {shift.date for shift in t.shifts}
    on_leave = {leave.date for leave in t.leaves}
    finish = t.registrar.finish or end

    def part_time_off(day):
        return any(
            status.type == StatusType.PART_TIME
            and not status.shift_types
            and status.start <= day <= status.end
            and (not status.weekdays or day.weekday() in status.weekdays)
            for status in t.statuses
        )

    return [
        OrdinaryDay(day)
        for day in daterange(max(start, t.registrar.start), min(end, finish) + timedelta(days=1))
        if day.weekday() < Weekday.SAT
        and day not in canterbury_holidays
        and day not in rostered
        and day not in on_leave
        and not part_time_off(day)
    ]


def check_roster(
    shifts: Iterable[Shift],
    leaves: Iterable[Leave] = (),
    statuses: Iterable[Status] = (),
    rules: Iterable[Rule] = STONZ + DEPARTMENT,
    period: tuple[date, date] | None = None,
) -> list[Violation]:
    """
    Check every registrar on the roster against `rules`. Unassigned shifts are ignored.

    Ordinary days are filled in from `period` (first and last day, inclusive), which defaults to the dates the
    shifts cover. Pass shifts from a week or two either side of the period, so limits that look back or ahead
    see them.
    """
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

    if timelines and period is None:
        dates = [shift.date for timeline in timelines.values() for shift in timeline.shifts]
        period = (min(dates), max(dates))
    for timeline in timelines.values():
        timeline.ordinary_days = infer_ordinary_days(timeline, *period)

    rules = list(rules)
    return [violation for timeline in timelines.values() for rule in rules for violation in rule(timeline)]
