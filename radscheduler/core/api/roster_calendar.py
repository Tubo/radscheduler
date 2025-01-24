from datetime import date
from typing import List

import holidays
from ninja import Field, ModelSchema, Router, Schema

import radscheduler.core.models as orm
import radscheduler.roster as domain

router = Router()


class FullCalendarSchema(Schema):
    id: int = None
    start: date
    title: str
    allDay: bool = True
    event_type: str


class FullCalendarShiftSchema(FullCalendarSchema, ModelSchema):
    start: date = Field(..., alias="date")
    event_type: str = "shift"

    class Meta:
        model = orm.Shift
        fields = ["id"]

    @staticmethod
    def resolve_title(shift):
        shift_type = domain.ShiftType(shift.type).name
        return f"{shift_type}: {shift.registrar.user.username}" + (" (extra)" if shift.extra_duty else "")


class FullCalendarLeaveSchema(FullCalendarSchema, ModelSchema):
    start: date = Field(..., alias="date")
    event_type: str = "leave"

    @staticmethod
    def resolve_title(leave):
        leave_name = domain.LeaveType(leave.type).name
        approved = leave.reg_approved and leave.dot_approved
        portion = f"({leave.portion})" if leave.portion != "ALL" else ""
        tbc = "(TBC)" if not approved else ""
        return f"{leave_name.capitalize()} {portion}: {leave.registrar.user.username} {tbc}"

    class Meta:
        model = orm.Leave
        fields = ["id"]


class FullCalendarHolidaySchema(FullCalendarSchema):
    event_type: str = "holiday"


@router.get("/shifts", response=List[FullCalendarShiftSchema])
def shift_events(request, start: date, end: date):
    shifts = orm.Shift.objects.filter(date__gte=start, date__lte=end, registrar__isnull=False).select_related(
        "registrar", "registrar__user"
    )
    return list(shifts)


@router.get("/leaves", response=List[FullCalendarLeaveSchema])
def leave_events(request, start: date, end: date):
    leaves = (
        orm.Leave.objects.filter(date__gte=start, date__lte=end)
        .exclude(reg_approved=False, dot_approved=False, cancelled=True)
        .select_related("registrar", "registrar__user")
    )
    return list(leaves)


@router.get("/holidays", response=List[FullCalendarHolidaySchema])
def holiday_events(request, start: date, end: date):
    cant_holidays = holidays.country_holidays("NZ", subdiv="CAN", years=[start.year, end.year])
    return [{"start": date, "title": name} for date, name in cant_holidays.items()]
