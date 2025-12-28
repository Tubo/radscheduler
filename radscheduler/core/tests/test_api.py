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


class TestCalendarAPIPublishDateFiltering:
    """Tests that the calendar API respects publish date settings."""

    def test_shift_events_clamps_to_publish_date_range(self, rf, juniors_db):
        """Calendar API should clamp shifts to the publish date range."""
        from django.test import RequestFactory

        # Create settings with a limited publish date range
        orm.Settings.objects.create(
            publish_start_date=date(2023, 6, 1), publish_end_date=date(2023, 6, 30)
        )

        reg = juniors_db[0]
        # Create shifts: before, during, and after the publish range
        orm.Shift.objects.create(
            date=date(2023, 5, 31), type=domain.ShiftType.LONG, registrar=reg
        )
        orm.Shift.objects.create(
            date=date(2023, 6, 15), type=domain.ShiftType.LONG, registrar=reg
        )
        orm.Shift.objects.create(
            date=date(2023, 7, 1), type=domain.ShiftType.LONG, registrar=reg
        )

        # Request a wide date range
        request = rf.get(
            "/api/calendar/shifts", {"start": "2023-05-01", "end": "2023-07-31"}
        )
        result = shift_events(request, start=date(2023, 5, 1), end=date(2023, 7, 31))

        # Only the shift within the publish range should be returned
        assert len(result) == 1
        assert result[0].date == date(2023, 6, 15)

    def test_leave_events_clamps_to_publish_date_range(self, rf, juniors_db):
        """Calendar API should clamp leaves to the publish date range."""
        from django.test import RequestFactory

        # Create settings with a limited publish date range
        orm.Settings.objects.create(
            publish_start_date=date(2023, 6, 1), publish_end_date=date(2023, 6, 30)
        )

        reg = juniors_db[0]
        # Create leaves: before, during, and after the publish range
        orm.Leave.objects.create(
            date=date(2023, 5, 31),
            type=domain.LeaveType.ANNUAL,
            registrar=reg,
            reg_approved=True,
            dot_approved=True,
        )
        orm.Leave.objects.create(
            date=date(2023, 6, 15),
            type=domain.LeaveType.ANNUAL,
            registrar=reg,
            reg_approved=True,
            dot_approved=True,
        )
        orm.Leave.objects.create(
            date=date(2023, 7, 1),
            type=domain.LeaveType.ANNUAL,
            registrar=reg,
            reg_approved=True,
            dot_approved=True,
        )

        # Request a wide date range
        request = rf.get(
            "/api/calendar/leaves", {"start": "2023-05-01", "end": "2023-07-31"}
        )
        result = leave_events(request, start=date(2023, 5, 1), end=date(2023, 7, 31))

        # Only the leave within the publish range should be returned
        assert len(result) == 1
        assert result[0].date == date(2023, 6, 15)

    def test_shift_events_returns_all_when_no_settings(self, rf, juniors_db):
        """Calendar API should return all shifts if no settings exist."""
        reg = juniors_db[0]
        # Create shifts on various dates
        orm.Shift.objects.create(
            date=date(2023, 5, 31), type=domain.ShiftType.LONG, registrar=reg
        )
        orm.Shift.objects.create(
            date=date(2023, 6, 15), type=domain.ShiftType.LONG, registrar=reg
        )
        orm.Shift.objects.create(
            date=date(2023, 7, 1), type=domain.ShiftType.LONG, registrar=reg
        )

        # Request a wide date range
        request = rf.get(
            "/api/calendar/shifts", {"start": "2023-05-01", "end": "2023-07-31"}
        )
        result = shift_events(request, start=date(2023, 5, 1), end=date(2023, 7, 31))

        # All shifts within the requested range should be returned
        assert len(result) == 3
