"""
Tests for iCal feed views.

These feeds are accessed by calendar applications (Google Calendar, Apple Calendar, etc.)
and must be fast to avoid timeouts. The main optimizations tested here:
- Limited date range (30 days history instead of 180)
- Query optimization with select_related and only()
- Server-side caching (15 minutes) to reduce DB load
"""

from datetime import date, timedelta

import pytest
from django.core.cache import cache
from django.urls import reverse

from radscheduler.core.models import Leave, Shift
from radscheduler.roster.models import LeaveType, ShiftType

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test to avoid stale cached responses."""
    cache.clear()
    yield
    cache.clear()


class TestShiftFeed:
    def test_returns_ical_content_type(self, app, juniors_db):
        """Feed should return iCalendar content type."""
        resp = app.get(reverse("ical_shifts"))
        assert resp.status_code == 200
        assert "text/calendar" in resp.content_type

    def test_has_cache_control_header(self, app, juniors_db):
        """Feed should have Cache-Control header for client-side caching."""
        resp = app.get(reverse("ical_shifts"))
        # cache_page sets max-age header
        assert "max-age" in resp.headers.get("Cache-Control", "")

    def test_returns_valid_ical_format(self, app, juniors_db):
        """Feed should return valid iCalendar format with VCALENDAR wrapper."""
        # Create a shift within range
        Shift.objects.create(
            date=date.today(),
            type=ShiftType.LONG,
            registrar=juniors_db[0],
        )
        resp = app.get(reverse("ical_shifts"))
        content = resp.content.decode("utf-8")
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content

    def test_includes_shifts_within_30_days(self, app, juniors_db):
        """Shifts within last 30 days should be included."""
        registrar = juniors_db[0]
        shift = Shift.objects.create(
            date=date.today() - timedelta(days=15),
            type=ShiftType.LONG,
            registrar=registrar,
        )
        resp = app.get(reverse("ical_shifts"))
        content = resp.content.decode("utf-8")
        assert registrar.user.username in content
        assert f"shift_{shift.id}" in content

    def test_excludes_shifts_older_than_30_days(self, app, juniors_db):
        """Shifts older than 30 days should be excluded for performance."""
        registrar = juniors_db[0]
        old_shift = Shift.objects.create(
            date=date.today() - timedelta(days=60),
            type=ShiftType.LONG,
            registrar=registrar,
        )
        resp = app.get(reverse("ical_shifts"))
        content = resp.content.decode("utf-8")
        assert f"shift_{old_shift.id}" not in content

    def test_excludes_unassigned_shifts(self, app, juniors_db):
        """Shifts without a registrar should not appear in feed."""
        Shift.objects.create(
            date=date.today(),
            type=ShiftType.LONG,
            registrar=None,
        )
        resp = app.get(reverse("ical_shifts"))
        content = resp.content.decode("utf-8")
        # Should have calendar structure but no VEVENT for unassigned shift
        assert "BEGIN:VCALENDAR" in content
        assert "BEGIN:VEVENT" not in content

    def test_includes_future_shifts(self, app, juniors_db):
        """Future shifts should be included."""
        registrar = juniors_db[0]
        shift = Shift.objects.create(
            date=date.today() + timedelta(days=30),
            type=ShiftType.LONG,
            registrar=registrar,
        )
        resp = app.get(reverse("ical_shifts"))
        content = resp.content.decode("utf-8")
        assert f"shift_{shift.id}" in content

    def test_extra_duty_marked_in_title(self, app, juniors_db):
        """Extra duty shifts should be marked in the title."""
        registrar = juniors_db[0]
        Shift.objects.create(
            date=date.today(),
            type=ShiftType.LONG,
            registrar=registrar,
            extra_duty=True,
        )
        resp = app.get(reverse("ical_shifts"))
        content = resp.content.decode("utf-8")
        assert "(extra)" in content


class TestLeaveFeed:
    def test_returns_ical_content_type(self, app, juniors_db):
        """Feed should return iCalendar content type."""
        resp = app.get(reverse("ical_leaves"))
        assert resp.status_code == 200
        assert "text/calendar" in resp.content_type

    def test_has_cache_control_header(self, app, juniors_db):
        """Feed should have Cache-Control header for client-side caching."""
        resp = app.get(reverse("ical_leaves"))
        # cache_page sets max-age header
        assert "max-age" in resp.headers.get("Cache-Control", "")

    def test_returns_valid_ical_format(self, app, juniors_db):
        """Feed should return valid iCalendar format."""
        Leave.objects.create(
            date=date.today(),
            type=LeaveType.ANNUAL,
            registrar=juniors_db[0],
        )
        resp = app.get(reverse("ical_leaves"))
        content = resp.content.decode("utf-8")
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content

    def test_includes_leaves_within_30_days(self, app, juniors_db):
        """Leaves within last 30 days should be included."""
        registrar = juniors_db[0]
        leave = Leave.objects.create(
            date=date.today() - timedelta(days=15),
            type=LeaveType.ANNUAL,
            registrar=registrar,
        )
        resp = app.get(reverse("ical_leaves"))
        content = resp.content.decode("utf-8")
        assert registrar.user.username in content
        assert f"leave_{leave.id}" in content

    def test_excludes_leaves_older_than_30_days(self, app, juniors_db):
        """Leaves older than 30 days should be excluded for performance."""
        registrar = juniors_db[0]
        old_leave = Leave.objects.create(
            date=date.today() - timedelta(days=60),
            type=LeaveType.ANNUAL,
            registrar=registrar,
        )
        resp = app.get(reverse("ical_leaves"))
        content = resp.content.decode("utf-8")
        assert f"leave_{old_leave.id}" not in content

    def test_excludes_cancelled_leaves(self, app, juniors_db):
        """Cancelled leaves should not appear in feed."""
        leave = Leave.objects.create(
            date=date.today(),
            type=LeaveType.ANNUAL,
            registrar=juniors_db[0],
            cancelled=True,
        )
        resp = app.get(reverse("ical_leaves"))
        content = resp.content.decode("utf-8")
        assert f"leave_{leave.id}" not in content

    def test_includes_future_leaves(self, app, juniors_db):
        """Future leaves should be included."""
        registrar = juniors_db[0]
        leave = Leave.objects.create(
            date=date.today() + timedelta(days=30),
            type=LeaveType.ANNUAL,
            registrar=registrar,
        )
        resp = app.get(reverse("ical_leaves"))
        content = resp.content.decode("utf-8")
        assert f"leave_{leave.id}" in content

    def test_partial_day_shown_in_title(self, app, juniors_db):
        """Partial day leaves should show AM/PM in title."""
        registrar = juniors_db[0]
        Leave.objects.create(
            date=date.today(),
            type=LeaveType.ANNUAL,
            registrar=registrar,
            portion="AM",
        )
        resp = app.get(reverse("ical_leaves"))
        content = resp.content.decode("utf-8")
        assert "(AM)" in content
