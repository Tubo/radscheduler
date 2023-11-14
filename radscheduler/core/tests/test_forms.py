from freezegun import freeze_time

from ..forms import LeaveForm, ShiftFormSet


class TestLeaveForm:
    def test_no_leave_for_past(self):
        with freeze_time("2023-11-18"):
            form = LeaveForm(data={"date": "2023-11-17", "type": "ANNUAL", "portion": "ALL"})
            assert form.is_valid() is False, form.errors
            assert form.errors["date"] == ["Unable to apply for leave in the past"]

    def test_no_leave_for_public_holiday(self):
        with freeze_time("2023-11-14"):
            form = LeaveForm(data={"date": "2023-11-17", "type": "ANNUAL", "portion": "ALL"})
            assert not form.is_valid(), form.errors
            assert form.errors["date"] == ["No need to apply for public holiday leave"]

    def test_no_leave_for_weekend(self):
        with freeze_time("2023-11-17"):
            form = LeaveForm(data={"date": "2023-11-18", "type": "ANNUAL", "portion": "ALL"})
            assert not form.is_valid(), form.errors
            assert form.errors["date"] == ["No need to apply for weekend leave"]

    def test_no_leave_if_existing(self):
        with freeze_time("2023-11-17"):
            form = LeaveForm(data={"date": "2023-11-18", "type": "ANNUAL", "portion": "ALL"})
            assert not form.is_valid(), form.errors
            assert form.errors["date"] == ["No need to apply for weekend leave"]


class TestShiftFormSet:
    def test_form_submission(self):
        formset = ShiftFormSet()

    def test_form_submission_starting_non_0(self):
        formset = ShiftFormSet()
