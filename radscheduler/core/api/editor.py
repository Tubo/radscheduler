"""
JSON API for the roster editor. Staff only; changes need the CSRF token.
"""

from datetime import date, datetime

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, Router, Schema, Status
from ninja.security import SessionAuth

from radscheduler.core import service
from radscheduler.core.models import Leave, Registrar, Shift
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


@router.get("/roster/checks", response=ChecksOut)
def get_checks(request, week: date):
    """The rule breaks and workload alone, for refreshing them after a change."""
    return service.editor_checks(week)


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
    return apply_leave_patch(leave, payload.dict(exclude_unset=True), request.user)


@router.patch("/leaves", response=list[LeaveOut])
def change_leaves(request, payload: LeavesPatch):
    changes = payload.dict(exclude_unset=True, exclude={"ids"})
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
