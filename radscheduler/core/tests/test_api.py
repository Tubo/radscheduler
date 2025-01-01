from datetime import date

import radscheduler.core.models as orm
import radscheduler.roster.models as domain
from radscheduler.core.api.roster_calendar import *


class TestFullCalendarSchema:
    def test_shift_schema(self, juniors_db):
        shift = orm.Shift.objects.create(
            date=date(2021, 1, 1),
            type=domain.ShiftType.LONG,
            registrar=juniors_db[0],
        )
        serialized = FullCalendarShiftSchema.from_orm(shift).dict()
        assert serialized["id"] == shift.pk
        assert serialized["start"] == date(2021, 1, 1)
        assert "LONG" in serialized["title"]
        assert serialized["allDay"] is True
        assert serialized["event_type"] == "shift"

    def test_leave_schema(self, juniors_db):
        leave = orm.Leave.objects.create(
            date=date(2021, 1, 1),
            type=domain.LeaveType.ANNUAL,
            registrar=juniors_db[0],
        )
        serialized = FullCalendarLeaveSchema.from_orm(leave).dict()
        assert serialized["id"] == leave.pk
        assert serialized["start"] == date(2021, 1, 1)
        assert serialized["event_type"] == "leave"
        assert "Annual" in serialized["title"], serialized
        assert serialized["allDay"] is True

    def test_holiday_schema(self):
        cant_holidays = holidays.country_holidays("NZ", subdiv="CAN", years=2024)
        xmas_date = date(2024, 12, 25)
        xmas_title = cant_holidays.get(xmas_date)
        serialized = FullCalendarHolidaySchema(start=xmas_date, title=xmas_title).dict()
        assert serialized["id"] is None
        assert serialized["start"] == xmas_date
        assert serialized["event_type"] == "holiday"
        assert "Christmas" in serialized["title"], serialized
        assert serialized["allDay"] is True
