from datetime import date, timedelta

import pytest
from django.urls import reverse

from radscheduler.core.models import Leave, Shift, ShiftInterest
from radscheduler.roster.models import LeaveType, ShiftType

pytestmark = pytest.mark.django_db


def test_index(django_app):
    resp = django_app.get("/")
    assert resp.status_code == 200, "Should return a 200 status code"


class TestLeaves:
    def test_page(self):
        # Go to leave page
        # Sees a form and a list of leaves
        # fills the form
        # submits the form
        # sees the form and the new leave in the list
        pass

    def test_form(self, app, juniors_db):
        app.set_user(juniors_db[0].user)
        form = app.get(reverse("leave_page")).form
        r = form.submit()
        assert "required" in r

    def test_inline_form(self, app, juniors_db):
        pass


class TestAccess:
    def ordinary_user_cannot_access_roster_generation(self):
        # Cannot see the button on the menu
        # Cannot access the page
        pass


class TestRosterGeneration:
    def test_generate_empty_schedule(self, app, juniors_db):
        pass


class TestSettingsView:
    """Tests for the settings view Unpoly layer behavior."""

    def test_settings_redirects_to_editor_on_direct_access(self, app, admin_user):
        """When accessing settings URL directly (browser refresh), redirect to editor."""
        app.set_user(admin_user)
        resp = app.get(reverse("settings"))
        assert resp.status_code == 302
        assert resp.location == reverse("editor")

    def test_settings_renders_form_when_accessed_via_unpoly_layer(self, app, admin_user):
        """When accessing settings via Unpoly layer, render the settings form."""
        app.set_user(admin_user)
        resp = app.get(reverse("settings"), headers={"X-Up-Mode": "modal"})
        assert resp.status_code == 200
        assert "Publication Settings" in resp.text

    def test_settings_redirects_when_unpoly_mode_is_root(self, app, admin_user):
        """When X-Up-Mode is 'root', treat as direct access and redirect."""
        app.set_user(admin_user)
        resp = app.get(reverse("settings"), headers={"X-Up-Mode": "root"})
        assert resp.status_code == 302
        assert resp.location == reverse("editor")


def next_weekday(days_ahead):
    day = date.today() + timedelta(days=days_ahead)
    while day.weekday() > 4:
        day += timedelta(days=1)
    return day


class TestLeaveOwnership:
    """Registrars can only see and change their own leave."""

    @pytest.fixture
    def others_leave(self, juniors_db):
        return Leave.objects.create(date=next_weekday(14), type=LeaveType.ANNUAL, registrar=juniors_db[1])

    def test_cannot_view_others_leave_row(self, app, juniors_db, others_leave):
        app.set_user(juniors_db[0].user)
        assert app.get(reverse("leave_row", args=[others_leave.pk]), expect_errors=True).status_code == 404

    def test_cannot_open_others_leave_form(self, app, juniors_db, others_leave):
        app.set_user(juniors_db[0].user)
        assert app.get(reverse("leave_form_inline", args=[others_leave.pk]), expect_errors=True).status_code == 404

    def test_cannot_edit_others_leave(self, app, juniors_db, others_leave):
        app.set_user(juniors_db[0].user)
        params = {"date": others_leave.date.isoformat(), "type": LeaveType.SICK, "portion": "ALL", "comment": "x"}
        resp = app.post(reverse("leave_form_inline", args=[others_leave.pk]), params, expect_errors=True)
        assert resp.status_code == 404
        others_leave.refresh_from_db()
        assert others_leave.type == LeaveType.ANNUAL

    def test_cannot_delete_others_leave(self, app, juniors_db, others_leave):
        app.set_user(juniors_db[0].user)
        resp = app.post(reverse("leave_delete", args=[others_leave.pk]), expect_errors=True)
        assert resp.status_code == 404
        assert Leave.objects.filter(pk=others_leave.pk).exists()

    def test_can_delete_own_leave(self, app, juniors_db, others_leave):
        app.set_user(juniors_db[1].user)
        app.post(reverse("leave_delete", args=[others_leave.pk]))
        assert not Leave.objects.filter(pk=others_leave.pk).exists()

    def test_new_leave_is_always_for_the_signed_in_registrar(self, app, juniors_db):
        # The form carries a hidden registrar field; tampering with it must not create leave for someone else.
        app.set_user(juniors_db[0].user)
        day = next_weekday(14)
        params = {"date": day.isoformat(), "type": LeaveType.ANNUAL, "portion": "ALL", "registrar": juniors_db[1].pk}
        app.post(reverse("leave_page"), params)
        assert Leave.objects.get(date=day).registrar == juniors_db[0]


class TestShiftInterestOwnership:
    """Registrars can only change their own extra-duty interests."""

    @pytest.fixture
    def extra_shift(self):
        return Shift.objects.create(date=next_weekday(20), type=ShiftType.LONG, extra_duty=True)

    @pytest.fixture
    def others_interest(self, juniors_db, extra_shift):
        return ShiftInterest.objects.create(shift=extra_shift, registrar=juniors_db[1], comment="original")

    def test_cannot_edit_others_interest(self, app, juniors_db, others_interest):
        app.set_user(juniors_db[0].user)
        resp = app.post(reverse("extra_interest", args=[others_interest.pk]), {"comment": "x"}, expect_errors=True)
        assert resp.status_code == 404
        others_interest.refresh_from_db()
        assert others_interest.comment == "original"

    def test_cannot_delete_others_interest(self, app, juniors_db, others_interest):
        app.set_user(juniors_db[0].user)
        resp = app.delete(reverse("extra_interest", args=[others_interest.pk]), expect_errors=True)
        assert resp.status_code == 404
        assert ShiftInterest.objects.filter(pk=others_interest.pk).exists()

    def test_can_delete_own_interest(self, app, juniors_db, others_interest):
        app.set_user(juniors_db[1].user)
        app.delete(reverse("extra_interest", args=[others_interest.pk]))
        assert not ShiftInterest.objects.filter(pk=others_interest.pk).exists()

    def test_cannot_register_interest_in_a_normal_shift(self, app, juniors_db):
        shift = Shift.objects.create(date=next_weekday(20), type=ShiftType.LONG, extra_duty=False)
        app.set_user(juniors_db[0].user)
        resp = app.post(reverse("extra_interests"), {"shift_id": shift.pk}, expect_errors=True)
        assert resp.status_code == 404
        assert not ShiftInterest.objects.exists()


class TestSaveExtraDutyWinner:
    @pytest.fixture
    def extra_shift(self):
        return Shift.objects.create(date=next_weekday(20), type=ShiftType.LONG, extra_duty=True)

    def test_staff_saves_winner(self, app, admin_user, juniors_db, extra_shift):
        app.set_user(admin_user)
        resp = app.post(reverse("extra_save_registrar", args=[extra_shift.pk]), {"registrar": juniors_db[0].pk})
        assert resp.status_code == 302
        assert resp.location == reverse("extra_edit_page")
        extra_shift.refresh_from_db()
        assert extra_shift.registrar == juniors_db[0]

    def test_winner_shows_on_editor_page(self, app, admin_user, juniors_db, extra_shift):
        app.set_user(admin_user)
        page = app.post(
            reverse("extra_save_registrar", args=[extra_shift.pk]), {"registrar": juniors_db[0].pk}
        ).follow()
        row = page.html.find(id=f"extra-edit-{extra_shift.pk}")
        assert row.find(class_="fw-bold").text == juniors_db[0].user.username

    def test_missing_registrar_leaves_shift_unassigned(self, app, admin_user, extra_shift):
        app.set_user(admin_user)
        resp = app.post(reverse("extra_save_registrar", args=[extra_shift.pk]), {"registrar": ""})
        assert resp.status_code == 302
        extra_shift.refresh_from_db()
        assert extra_shift.registrar is None

    def test_only_extra_duty_shifts(self, app, admin_user, juniors_db):
        shift = Shift.objects.create(date=next_weekday(20), type=ShiftType.LONG, extra_duty=False)
        app.set_user(admin_user)
        resp = app.post(
            reverse("extra_save_registrar", args=[shift.pk]), {"registrar": juniors_db[0].pk}, expect_errors=True
        )
        assert resp.status_code == 404

    def test_registrar_cannot_save_winner(self, app, juniors_db, extra_shift):
        app.set_user(juniors_db[0].user)
        resp = app.post(reverse("extra_save_registrar", args=[extra_shift.pk]), {"registrar": juniors_db[0].pk})
        assert resp.status_code == 302
        assert "login" in resp.location
        extra_shift.refresh_from_db()
        assert extra_shift.registrar is None
