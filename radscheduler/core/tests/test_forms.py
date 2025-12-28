from freezegun import freeze_time

from ..forms import LeaveForm


class TestLeaveForm:
    def test_no_leave_for_past(self):
        with freeze_time("2023-11-18"):
            form = LeaveForm(data={"date": "2023-11-17", "type": "ANNUAL", "portion": "ALL"})
            assert form.is_valid() is False, form.errors
            assert form.errors["date"] == ["Unable to apply for leave in the past"]

    def test_allow_create_leave_for_public_holiday(self):
        with freeze_time("2023-11-14"):
            form = LeaveForm(data={"date": "2023-11-17", "type": "ANNUAL", "portion": "ALL"})
            # Allow leave on weekends and public holidays for oncall planning
            assert form.is_valid(), form.errors

    def test_no_leave_for_weekend(self):
        with freeze_time("2023-11-17"):
            # Do not allow leave on weekends and public holidays for oncall planning
            form = LeaveForm(data={"date": "2023-11-18", "type": "ANNUAL", "portion": "ALL"})
            assert not form.is_valid(), form.errors
            # Error message must include "is a weekend"
            assert "is a weekend" in form.errors["date"][0]

