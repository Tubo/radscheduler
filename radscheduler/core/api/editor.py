"""
JSON API for the roster editor. Staff only; changes need the CSRF token.
"""

from datetime import date, datetime

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from ninja import Field, Router, Schema, Status
from ninja.security import SessionAuth

from radscheduler.core import service
from radscheduler.core.models import Leave, Registrar, Shift
from radscheduler.roster.models import LeaveType, ShiftType


class StaffAuth(SessionAuth):
    def authenticate(self, request, key):
        user = super().authenticate(request, key)
        return user if user and user.is_staff else None


router = Router(auth=StaffAuth())


class RegistrarOut(Schema):
    id: int
    username: str = Field(..., alias="user.username")
    year: int | None


class ShiftOut(Schema):
    id: int
    date: date
    type: ShiftType
    registrar: int = Field(..., alias="registrar_id")
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
    cancelled: bool
    created: datetime
    last_edited: datetime


class HolidayOut(Schema):
    date: date
    name: str


class PublishedOut(Schema):
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
    holidays: list[HolidayOut]
    published: PublishedOut | None


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
    cancelled: bool = None


@router.get("/roster", response=RosterOut)
def roster(request, week: date):
    return service.editor_roster(week)


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


@router.delete("/shifts/{shift_id}", response={204: None})
def delete_shift(request, shift_id: int):
    get_object_or_404(Shift, pk=shift_id).delete()
    response = HttpResponse(status=204)
    del response["Content-Type"]
    return response


@router.patch("/leaves/{leave_id}", response=LeaveOut)
def change_leave(request, leave_id: int, payload: LeavePatch):
    leave = get_object_or_404(Leave, pk=leave_id)
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(leave, field, value)
    leave.save()
    return leave
