"""
The roster as the landing page draws it: a month at a time, in weeks from the Monday on or before its first
day to the Sunday on or after its last, each day holding the shifts and leave registrars can see. A
registrar's own roster ("mine") holds only their days, with who else is on call beside each of their on-call
shifts; the department's holds everyone's, narrowed by year and by what to show, and a busy day folds its
days off and leave into a line ("2 off · 9 on leave") so on-call cover stays in view.

Only the published days carry anything, as in the calendar feeds: past the publish range the page says so
rather than drawing an empty roster.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.db.models import Q

from radscheduler.core.labels import SHIFT_SHORT
from radscheduler.core.leave_requests import in_training
from radscheduler.core.models import Leave, Registrar, Settings, Shift
from radscheduler.roster import LeaveType, ShiftType, canterbury_holidays
from radscheduler.roster.models import SHIFT_HOURS

# A day in the department's roster shows this many days off and leave as chips; more fold into a line.
FOLD_OVER = 2

# On-call shifts in the order of the day, then the days off that follow them.
ON_CALL = (ShiftType.HELP, ShiftType.LONG, ShiftType.SWING, ShiftType.NIGHT)
OFF_DUTY = (ShiftType.RDO, ShiftType.SLEEP)
SHIFT_ORDER = {shift_type: i for i, shift_type in enumerate(ON_CALL + OFF_DUTY)}
LEAVE_ORDER = {leave_type: i for i, leave_type in enumerate(LeaveType.values)}

# What the department's roster can show: on-call shifts, days off (RDO and sleep days) and leave.
SHOW = ("oncall", "off", "leave")
# The choices the page offers, by the value it sends: everything, or what to show only.
SHOW_CHOICES = {
    "": ("Everything", SHOW),
    "oncall": ("On call only", ("oncall",)),
    "oncall-leave": ("On call and leave", ("oncall", "leave")),
    "oncall-off": ("On call and days off", ("oncall", "off")),
    "leave": ("Leave only", ("leave",)),
    "off": ("Days off only", ("off",)),
}


@dataclass(frozen=True)
class Filters:
    """The department roster's filters: registrar years to keep (all when empty) and what to show."""

    years: tuple[int, ...] = ()
    show: tuple[str, ...] = SHOW


@dataclass
class Chip:
    """A shift or a day of leave as the roster draws it."""

    kind: str  # "oncall", "off" or "leave", as in SHOW
    type: str  # the ShiftType or LeaveType value
    registrar: int
    name: str  # short, for the chip
    full_name: str
    label: str  # the type as the chip names it
    type_label: str  # the type in full: "Long day", "Annual leave"
    title: str  # the whole of it, for a tooltip
    extra: bool = False
    state: str = ""  # leave: "approved", "partial" (one of two decisions made) or "pending"
    portion: str = "ALL"
    # Folded into its day's line, shown as a chip only for the registrar being followed.
    folded: bool = False


@dataclass
class Day:
    date: date
    today: bool
    weekend: bool
    holiday: str | None
    published: bool
    # In the weeks drawn but not the month: the days either side of it.
    outside: bool = False
    chips: list[Chip] = field(default_factory=list)
    # The department's roster: the days off and leave folded into a line, when there are more than FOLD_OVER.
    folded: list[Chip] = field(default_factory=list)
    # A registrar's own roster: who else is on call on a day they are.
    mates: list[Chip] = field(default_factory=list)

    @property
    def off_count(self) -> int:
        return sum(chip.kind == "off" for chip in self.folded)

    @property
    def leave_count(self) -> int:
        return sum(chip.kind == "leave" for chip in self.folded)

    @property
    def waiting_count(self) -> int:
        return sum(chip.kind == "leave" and chip.state != "approved" for chip in self.folded)


@dataclass
class Week:
    monday: date
    days: list[Day]


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def add_months(month: date, n: int) -> date:
    """The first of the month `n` months after `month`'s (before, for a negative `n`)."""
    index = month.year * 12 + month.month - 1 + n
    return date(index // 12, index % 12 + 1, 1)


def month_end(month: date) -> date:
    return add_months(month, 1) - timedelta(days=1)


def publish_range() -> tuple[date | None, date | None]:
    """The days registrars can see, or (None, None) when nothing limits them."""
    settings = Settings.objects.first()
    return (settings.publish_start_date, settings.publish_end_date) if settings else (None, None)


def full_name(registrar: Registrar) -> str:
    return registrar.user.name or registrar.user.username


def short_names(registrars) -> dict[int, str]:
    """
    Each registrar's name as a chip shows it: the first name and the initial of the last ("Rachel B."),
    or the whole name where two registrars would share the short one, or where there is only one word.
    """
    short = {}
    for registrar in registrars:
        words = full_name(registrar).split()
        short[registrar.pk] = f"{words[0]} {words[-1][0]}." if len(words) > 1 else full_name(registrar)
    taken = {}
    for pk, name in short.items():
        taken.setdefault(name, []).append(pk)
    by_pk = {registrar.pk: registrar for registrar in registrars}
    for pks in taken.values():
        if len(pks) > 1:
            for pk in pks:
                short[pk] = full_name(by_pk[pk])
    return short


def leave_state(leave: Leave) -> str:
    if leave.reg_approved and leave.dot_approved:
        return "approved"
    if leave.reg_approved or leave.dot_approved:
        return "partial"
    return "pending"


LEAVE_STATE_WORDS = {
    "approved": "approved",
    "partial": "approved by one, waiting on the other",
    "pending": "waiting for approval",
}
PORTION_WORDS = {"AM": "morning", "PM": "afternoon"}


def shift_chip(shift: Shift, names: dict[int, str]) -> Chip:
    registrar = shift.registrar
    kind = "off" if shift.type in OFF_DUTY else "oncall"
    title = f"{ShiftType(shift.type).label}: {full_name(registrar)}"
    if shift.extra_duty:
        title += " (extra duty)"
    return Chip(
        kind=kind,
        type=shift.type,
        registrar=registrar.pk,
        name=names[registrar.pk],
        full_name=full_name(registrar),
        label=SHIFT_SHORT[shift.type],
        type_label=ShiftType(shift.type).label,
        title=title,
        extra=shift.extra_duty,
    )


def leave_chip(leave: Leave, names: dict[int, str]) -> Chip:
    registrar = leave.registrar
    state = leave_state(leave)
    label = LeaveType(leave.type).label
    title = f"{label} leave"
    if leave.portion in PORTION_WORDS:
        title += f", {PORTION_WORDS[leave.portion]}"
    title += f": {full_name(registrar)} ({LEAVE_STATE_WORDS[state]})"
    return Chip(
        kind="leave",
        type=leave.type,
        registrar=registrar.pk,
        name=names[registrar.pk],
        full_name=full_name(registrar),
        label=label,
        type_label=f"{label} leave",
        title=title,
        state=state,
        portion=leave.portion,
    )


def chip_order(chip: Chip):
    if chip.kind == "leave":
        return (len(SHIFT_ORDER), LEAVE_ORDER.get(chip.type, 0), chip.name)
    return (SHIFT_ORDER[chip.type], 0, chip.name)


def registrars_in_years(years: tuple[int, ...]) -> set[int]:
    return set(in_training().filter(year__in=years).values_list("pk", flat=True))


def has_shifts(**lookups) -> bool:
    return Shift.objects.filter(registrar__isnull=False, **lookups).exists()


def build(month: date, today: date, mine: Registrar | None = None, filters: Filters = Filters()) -> dict:
    """
    The weeks of `month`'s calendar. With `mine`, only that registrar's days; otherwise the department's,
    narrowed by `filters`, each busy day's days off and leave folded into a line.
    """
    month = first_of_month(month)
    last = month_end(month)
    start = monday(month)
    end = monday(last) + timedelta(days=6)
    published_from, published_to = publish_range()

    def is_published(day: date) -> bool:
        return (published_from is None or day >= published_from) and (published_to is None or day <= published_to)

    # What can be seen of these weeks: the published days among them.
    seen_from = max(start, published_from) if published_from else start
    seen_to = min(end, published_to) if published_to else end

    shifts = Shift.objects.none()
    leaves = Leave.objects.none()
    if seen_from <= seen_to:
        shifts = Shift.objects.filter(date__range=[seen_from, seen_to], registrar__isnull=False).select_related(
            "registrar__user"
        )
        leaves = (
            Leave.objects.filter(date__range=[seen_from, seen_to])
            .exclude(Q(reg_approved=False) | Q(dot_approved=False) | Q(cancelled=True))
            .select_related("registrar__user")
        )
        if mine:
            leaves = leaves.filter(registrar=mine)
    shifts, leaves = list(shifts), list(leaves)

    names = short_names(
        {s.registrar for s in shifts} | {leave.registrar for leave in leaves} | ({mine} if mine else set())
    )
    keep = registrars_in_years(filters.years) if filters.years and not mine else None

    by_day: dict[date, list[Chip]] = {}
    mates_by_day: dict[date, list[Chip]] = {}
    for shift in shifts:
        chip = shift_chip(shift, names)
        if mine:
            if shift.registrar_id == mine.pk:
                by_day.setdefault(shift.date, []).append(chip)
            elif chip.kind == "oncall":
                mates_by_day.setdefault(shift.date, []).append(chip)
        elif chip.kind in filters.show and (keep is None or chip.registrar in keep):
            by_day.setdefault(shift.date, []).append(chip)
    if mine or "leave" in filters.show:
        for leave in leaves:
            if keep is None or leave.registrar_id in keep:
                by_day.setdefault(leave.date, []).append(leave_chip(leave, names))

    weeks = []
    week_start = start
    while week_start <= end:
        days = []
        for d in range(7):
            day = week_start + timedelta(days=d)
            chips = sorted(by_day.get(day, []), key=chip_order)
            on_call = any(chip.kind == "oncall" for chip in chips)
            rest = [chip for chip in chips if chip.kind != "oncall"]
            folded = rest if not mine and len(rest) > FOLD_OVER else []
            for chip in folded:
                chip.folded = True
            days.append(
                Day(
                    date=day,
                    today=day == today,
                    weekend=day.weekday() >= 5,
                    holiday=canterbury_holidays.get(day),
                    published=is_published(day),
                    outside=day.month != month.month,
                    chips=chips,
                    folded=folded,
                    mates=sorted(mates_by_day.get(day, []), key=chip_order) if mine and on_call else [],
                )
            )
        weeks.append(Week(monday=week_start, days=days))
        week_start += timedelta(weeks=1)

    # The months either side, while there is published roster in them to see. Phones run on into the next
    # month only while it has published days; a desktop can step one month past them, to be told so.
    if published_from or published_to:
        has_earlier = published_from is None or month > published_from
        has_later = published_to is None or last < published_to
    else:
        has_earlier = has_shifts(date__lt=month)
        has_later = has_shifts(date__gt=last)
    unpublished = bool((published_to and month > published_to) or (published_from and last < published_from))

    return {
        "month": month,
        "weeks": weeks,
        "prev": add_months(month, -1) if has_earlier else None,
        "next": add_months(month, 1) if has_later else None,
        # Past the published roster, a desktop may still step on into the first month with nothing in it.
        "next_page": add_months(month, 1) if has_later or not (unpublished or published_to is None) else None,
        "unpublished": unpublished,
        "published_from": published_from,
        "published_to": published_to,
        "empty": not any(day.chips for week in weeks for day in week.days if not day.outside),
    }


def next_on_call(registrar: Registrar, today: date) -> Shift | None:
    """The registrar's next on-call shift from today, within the published roster."""
    _, published_to = publish_range()
    shifts = Shift.objects.filter(registrar=registrar, date__gte=today, type__in=ON_CALL)
    if published_to:
        shifts = shifts.filter(date__lte=published_to)
    return shifts.order_by("date").first()


def people() -> list[dict]:
    """The registrars in training, by year and then name, for following one of them."""
    registrars = sorted(in_training().select_related("user"), key=lambda r: (r.year, full_name(r).lower()))
    return [{"id": r.pk, "name": full_name(r), "year": r.year} for r in registrars]


def clock(t) -> str:
    """A time of day as the department says it: "8am", "12pm", "10pm"."""
    return f"{t.hour % 12 or 12}{'am' if t.hour < 12 else 'pm'}"


def shift_key() -> list[dict]:
    """Each shift type, its name and its hours, for the page's key."""
    key = []
    for shift_type in ON_CALL + OFF_DUTY:
        hours = ""
        if shift_type in SHIFT_HOURS:
            start, length = SHIFT_HOURS[shift_type]
            end = (datetime.combine(date.today(), start) + length).time()
            hours = f"{clock(start)}–{clock(end)}"
        key.append(
            {
                "type": shift_type,
                "short": SHIFT_SHORT[shift_type],
                "label": ShiftType(shift_type).label,
                "hours": hours,
            }
        )
    return key
