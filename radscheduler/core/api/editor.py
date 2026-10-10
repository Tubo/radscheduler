"""
JSON API for the roster editor. Staff only; changes need the CSRF token.
"""

from datetime import date, datetime

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Router, Schema, Status
from ninja.errors import HttpError
from ninja.security import SessionAuth

from radscheduler.core import leave_requests, service
from radscheduler.core.models import Leave, Registrar, Shift
from radscheduler.core.roles import leave_approvers
from radscheduler.roster.models import LeaveType, ShiftType, StatusType


class StaffAuth(SessionAuth):
    def authenticate(self, request, key):
        user = super().authenticate(request, key)
        return user if user and user.is_staff else None


router = Router(auth=StaffAuth())


class RegistrarOut(Schema):
    id: int
    username: str = Field(..., alias="user.username")
    # The full name, or the username for an account without one.
    name: str
    year: int | None

    @staticmethod
    def resolve_name(registrar):
        return registrar.user.name or registrar.user.username


class StatusOut(Schema):
    id: int
    registrar: int = Field(..., alias="registrar_id")
    type: StatusType
    start: date
    end: date
    # Empty means every weekday, or every shift type.
    weekdays: list[int]
    shift_types: list[ShiftType]
    comment: str


class ViolationOut(Schema):
    rule: str
    # The collective agreement's clause, or None for a department rule.
    clause: str | None
    registrar: int = Field(..., alias="registrar.id")
    dates: list[date]
    message: str
    # Why the department accepts this break, for one an agreed variance covers.
    variance: str | None


class WorkloadOut(Schema):
    registrar: int
    load: float


class ChecksOut(Schema):
    violations: list[ViolationOut]
    # Breaks of the contract that a department variance covers, shown apart from the rest.
    variances: list[ViolationOut]
    workload: list[WorkloadOut]


class ShiftOut(Schema):
    id: int
    date: date
    type: ShiftType
    # None for an extra duty posted but not yet given to anyone.
    registrar: int | None = Field(..., alias="registrar_id")
    extra_duty: bool


class LeaveOut(Schema):
    id: int
    date: date
    type: LeaveType
    portion: str
    registrar: int = Field(..., alias="registrar_id")
    comment: str
    reg_approved: bool | None
    dot_approved: bool | None
    # Who made each decision and when; None while waiting, or for decisions made before they were recorded.
    reg_decided_by: str | None
    reg_decided_at: datetime | None
    dot_decided_by: str | None
    dot_decided_at: datetime | None
    printed: bool
    microster: bool
    cancelled: bool
    created: datetime
    last_edited: datetime

    # In the department's time zone, so the editor can show them as they are.
    @staticmethod
    def resolve_created(leave):
        return timezone.localtime(leave.created)

    @staticmethod
    def resolve_last_edited(leave):
        return timezone.localtime(leave.last_edited)

    @staticmethod
    def resolve_reg_decided_by(leave):
        return leave.reg_decided_by and (leave.reg_decided_by.name or leave.reg_decided_by.username)

    @staticmethod
    def resolve_dot_decided_by(leave):
        return leave.dot_decided_by and (leave.dot_decided_by.name or leave.dot_decided_by.username)

    @staticmethod
    def resolve_reg_decided_at(leave):
        return leave.reg_decided_at and timezone.localtime(leave.reg_decided_at)

    @staticmethod
    def resolve_dot_decided_at(leave):
        return leave.dot_decided_at and timezone.localtime(leave.dot_decided_at)


class HolidayOut(Schema):
    date: date
    name: str


class PublishedRange(Schema):
    start: date
    end: date


class RosterOut(Schema):
    week: date
    prev: date
    next: date
    today: date
    dates: list[date]
    registrars: list[RegistrarOut]
    shifts: list[ShiftOut]
    leaves: list[LeaveOut]
    statuses: list[StatusOut]
    holidays: list[HolidayOut]
    published: PublishedRange | None
    checks: ChecksOut


class GapOut(Schema):
    date: date
    # Each requirement nobody is rostered for, as the shift types that would meet it.
    needs: list[list[ShiftType]]


class PreviewOut(Schema):
    shifts_shown: int
    leave_shown: int
    shifts_hidden: int
    leave_hidden: int
    # About the days registrars would start seeing.
    gaps: list[GapOut]
    violations: list[ViolationOut]
    leave_waiting: int
    # The last day checked for gaps and rule breaks, when the range was too long to check it all.
    checked_to: date | None


class AwayOut(Schema):
    """Someone else's leave on a day next to a request: approved, or still waiting for a decision."""

    registrar: int
    date: date
    type: LeaveType
    portion: str
    approved: bool


class RequestDayOut(Schema):
    date: date
    # Registrars on the roster that day, to weigh how many are away against.
    registrars: int
    # Whether anyone is rostered that day yet; until then its cover can't be judged.
    rostered: bool
    # Cover the leave would take away: the registrar is the only one rostered for it.
    lost: list[list[ShiftType]]
    # Cover nobody is rostered for, leave or not.
    short: list[list[ShiftType]]


class LeaveTallyOut(Schema):
    type: LeaveType
    # Days of this type in the year, a half day counting 0.5: approved by both, still waiting, and the request's own.
    approved: float
    waiting: float
    request: float


class LeaveYearOut(Schema):
    # A leave year runs from the first Monday of February to the day before the next.
    start: date
    end: date
    # A year the request falls in, rather than an earlier one.
    lead: bool
    types: list[LeaveTallyOut]


class LeaveRequestOut(Schema):
    registrar: int
    # When it was asked for; None for leave loaded in bulk from the old system, whose asking wasn't recorded.
    asked: datetime | None
    # The days asked for together, in order.
    leaves: list[LeaveOut]
    # The roster shown with it: the request and a couple of days either side.
    dates: list[date]
    # The registrar's own shifts and other leave on those dates.
    shifts: list[ShiftOut]
    other_leave: list[LeaveOut]
    away: list[AwayOut]
    days: list[RequestDayOut]
    # The registrar's rule breaks touching those dates: those the leave causes, and those already there.
    violations: list[ViolationOut]
    existing_violations: list[ViolationOut]
    # The registrar's leave by year: the years the request falls in, then earlier ones, latest first.
    years: list[LeaveYearOut]


class LeaveRequestsOut(Schema):
    requests: list[LeaveRequestOut]
    registrars: list[RegistrarOut]
    holidays: list[HolidayOut]
    # How many requests match, when only the first of them are drawn.
    total: int


class RequestChecksOut(Schema):
    """What a waiting request's verdict turns on."""

    # Rule breaks the leave would cause, and shifts of cover it would lose.
    breaks: int
    lost: int
    # Days asked for, and how many of them aren't rostered yet, so can't be checked.
    days: int
    unrostered: int
    # The busiest of those days: how many on leave, this request included, of how many on the roster.
    away: float
    roster: int


class RequestRowOut(Schema):
    """A request in the overview, keyed by its first day's id."""

    key: int
    registrar: int
    type: LeaveType
    portion: str
    start: date
    end: date
    # Days asked for, a half day counting 0.5.
    days: float
    # None for leave loaded in bulk from the old system, whose asking wasn't recorded.
    asked: datetime | None
    # The latest decision on any of its days.
    decided: datetime | None
    # "waiting", "approved", "declined" or "cancelled".
    status: str
    leaves: list[LeaveOut]
    comment: str
    # For a request still waiting only.
    checks: RequestChecksOut | None


class LeaveOverviewOut(Schema):
    rows: list[RequestRowOut]
    # How many requests match, of which `rows` is a page.
    total: int
    # The registrars in training, for the filters and the rows.
    registrars: list[RegistrarOut]


class WaitingCountsOut(Schema):
    # Requests waiting on this user's own decision (None if they decide none), and on anyone's.
    mine: int | None
    all: int


class ShiftTallyOut(Schema):
    type: ShiftType
    # The registrar's own count.
    count: int
    # Across their peers in the period; None when it has none.
    mean: float | None
    median: float | None
    min: int | None
    max: int | None


class ShiftPeriodOut(Schema):
    # "3 months", "6 months", the calendar year, or "Training"; both ends included.
    name: str
    start: date
    end: date
    # How many registrars the figures compare with: those in training throughout the period, or for
    # "Training", those in training today, each over their own training so far.
    peers: int
    # The shift types the registrar or any of their peers worked in any of the periods, the same in each.
    shifts: list[ShiftTallyOut]


class ShiftCountsOut(Schema):
    registrar: int
    periods: list[ShiftPeriodOut]


class ErrorOut(Schema):
    detail: str


class ShiftIn(Schema):
    date: date
    type: ShiftType
    registrar: int
    extra_duty: bool = False


class ShiftPatch(Schema):
    type: ShiftType = None
    extra_duty: bool = None


class LeavePatch(Schema):
    reg_approved: bool | None = None
    dot_approved: bool | None = None
    microster: bool = None
    cancelled: bool = None


class LeavesPatch(LeavePatch):
    """The same change to several days of leave, e.g. approving a whole request."""

    ids: list[int]


@router.get("/roster", response=RosterOut)
def get_roster(request, week: date):
    return service.editor_roster(week)


def request_filters(request, status, start, end, years, types, registrar, sort) -> leave_requests.Filters:
    """The overview's filters from the query: `years` and `types` comma-separated, empty for all."""
    if status not in leave_requests.STATUSES:
        raise HttpError(422, f"Unknown status: {status}")
    if sort not in leave_requests.SORTS:
        raise HttpError(422, f"Unknown sort: {sort}")
    try:
        year_list = tuple(int(year) for year in years.split(",") if year)
    except ValueError as error:
        raise HttpError(422, "Years must be numbers") from error
    type_list = tuple(t for t in types.split(",") if t)
    if not set(type_list) <= set(LeaveType.values):
        raise HttpError(422, f"Unknown leave type in: {types}")
    approvers = leave_approvers(request.user)
    return leave_requests.Filters(
        status=status,
        approver=approvers[0] if approvers else None,
        start=start,
        end=end,
        years=year_list,
        types=type_list,
        registrar=registrar,
        sort=sort,
    )


@router.get("/leave-requests", response=LeaveRequestsOut)
def get_leave_requests(
    request,
    status: str = "waiting",
    start: date | None = None,
    end: date | None = None,
    years: str = "",
    types: str = "",
    registrar: int | None = None,
    sort: str = "leave",
):
    """
    The leave requests that match the overview's filters, each with the roster around it: the first of them,
    with how many match. "mine" means those waiting on this user's decision.
    """
    filters = request_filters(request, status, start, end, years, types, registrar, sort)
    return leave_requests.matching_requests(filters)


@router.get("/leave-requests/overview", response=LeaveOverviewOut)
def get_leave_overview(
    request,
    status: str = "waiting",
    start: date | None = None,
    end: date | None = None,
    years: str = "",
    types: str = "",
    registrar: int | None = None,
    sort: str = "leave",
    offset: int = 0,
):
    """A page of the leave requests of registrars in training that match the filters, a row each."""
    filters = request_filters(request, status, start, end, years, types, registrar, sort)
    return leave_requests.overview(filters, offset=max(0, offset))


@router.get("/leave-requests/counts", response=WaitingCountsOut)
def get_leave_counts(request):
    """How many requests wait on this user's decision, and on anyone's: the navbar's count and the filters'."""
    approvers = leave_approvers(request.user)
    return {
        "mine": leave_requests.waiting_count(approvers[0]) if approvers else None,
        "all": leave_requests.waiting_count(None),
    }


# After the fixed paths, which a key would otherwise swallow.
@router.get("/leave-requests/{key}", response=LeaveRequestsOut)
def get_leave_request(request, key: int):
    """One request, by any of its days' ids, with the roster around it: for the overview's shelf."""
    days = leave_requests.request_of(key)
    if days is None:
        raise HttpError(404, "No such leave")
    return leave_requests.describe([days])


@router.get("/roster/checks", response=ChecksOut)
def get_checks(request, week: date):
    """The rule breaks and workload alone, for refreshing them after a change."""
    return service.editor_checks(week)


@router.get("/registrars/{registrar_id}/shift-counts", response=ShiftCountsOut)
def get_shift_counts(request, registrar_id: int):
    """How many shifts a registrar has worked recently and over their training, for their name's popover."""
    registrar = get_object_or_404(Registrar, pk=registrar_id)
    return service.shift_counts(registrar, timezone.localdate())


@router.post("/shifts", response={201: ShiftOut})
def add_shift(request, payload: ShiftIn):
    registrar = get_object_or_404(Registrar, pk=payload.registrar)
    return Status(201, service.add_shift(payload.date, payload.type, registrar, payload.extra_duty))


@router.patch("/shifts/{shift_id}", response=ShiftOut)
def change_shift(request, shift_id: int, payload: ShiftPatch):
    shift = get_object_or_404(Shift, pk=shift_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(shift, field, value)
    shift.save()
    return shift


# Returns the deleted shift rather than an empty 204: the generated Elm client decodes every response body.
@router.delete("/shifts/{shift_id}", response=ShiftOut)
def delete_shift(request, shift_id: int):
    shift = get_object_or_404(Shift, pk=shift_id)
    deleted = ShiftOut.from_orm(shift)
    shift.delete()
    return deleted


def check_leave_decisions(changes: dict, user) -> None:
    """Refuse a decision the user may not make, e.g. the Director of Training's on the senior registrar's."""
    approvers = leave_approvers(user)
    for approver in ("reg", "dot"):
        if f"{approver}_approved" in changes and approver not in approvers:
            raise HttpError(403, "You can't make this decision on leave.")


def apply_leave_patch(leave: Leave, changes: dict, user) -> Leave:
    for field, value in changes.items():
        if field in ("reg_approved", "dot_approved"):
            leave.decide(field.removesuffix("_approved"), value, user)
        else:
            setattr(leave, field, value)
    leave.save()
    return leave


@router.patch("/leaves/{leave_id}", response=LeaveOut)
def change_leave(request, leave_id: int, payload: LeavePatch):
    leave = get_object_or_404(Leave, pk=leave_id)
    changes = payload.dict(exclude_unset=True)
    check_leave_decisions(changes, request.user)
    return apply_leave_patch(leave, changes, request.user)


@router.patch("/leaves", response=list[LeaveOut])
def change_leaves(request, payload: LeavesPatch):
    changes = payload.dict(exclude_unset=True, exclude={"ids"})
    check_leave_decisions(changes, request.user)
    leaves = Leave.objects.filter(pk__in=payload.ids).order_by("date")
    with transaction.atomic():
        return [apply_leave_patch(leave, changes, request.user) for leave in leaves]


@router.get("/published/preview", response=PreviewOut)
def preview_published(request, start: date, end: date):
    return service.publish_preview(start, end)


@router.put("/published", response={200: PublishedRange, 422: ErrorOut})
def set_published(request, payload: PublishedRange):
    if payload.start > payload.end:
        return Status(422, {"detail": "The start of the published range must be on or before its end."})
    settings = service.set_published(payload.start, payload.end)
    return {"start": settings.publish_start_date, "end": settings.publish_end_date}
