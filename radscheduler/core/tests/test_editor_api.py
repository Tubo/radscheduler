from datetime import date

import pytest

from radscheduler.core.models import Leave, Settings, Shift
from radscheduler.roster.models import LeaveType, ShiftType

pytestmark = pytest.mark.django_db

CHRISTMAS = date(2024, 12, 25)


@pytest.fixture
def staff(admin_user):
    return admin_user


@pytest.fixture
def shift(juniors_db):
    return Shift.objects.create(date=date(2024, 12, 23), type=ShiftType.LONG, registrar=juniors_db[0])


@pytest.fixture
def leave(juniors_db):
    return Leave.objects.create(date=date(2024, 12, 24), type=LeaveType.ANNUAL, registrar=juniors_db[1])


class TestAccess:
    def test_registrars_cannot_read_the_roster(self, app, juniors_db):
        app.get("/api/editor/roster", {"week": "2024-12-25"}, user=juniors_db[0].user, status=401)

    def test_signed_out_users_cannot_read_the_roster(self, app):
        app.get("/api/editor/roster", {"week": "2024-12-25"}, status=401)

    def test_changes_need_a_csrf_token(self, django_app_factory, staff, shift):
        strict = django_app_factory(csrf_checks=True)
        strict.delete(f"/api/editor/shifts/{shift.pk}", user=staff, status=403)
        assert Shift.objects.filter(pk=shift.pk).exists()


class TestRoster:
    def test_three_weeks_around_the_week_in_focus(self, app, staff):
        roster = app.get("/api/editor/roster", {"week": "2024-12-25"}, user=staff).json

        assert roster["week"] == "2024-12-25"
        assert roster["prev"] == "2024-12-18"
        assert roster["next"] == "2025-01-01"
        assert roster["dates"][0] == "2024-12-16"
        assert roster["dates"][-1] == "2025-01-05"
        assert len(roster["dates"]) == 21
        assert {"date": "2024-12-25", "name": "Christmas Day"} in roster["holidays"]

    def test_registrars_shifts_and_leave(self, app, staff, juniors_db, shift, leave):
        roster = app.get("/api/editor/roster", {"week": "2024-12-25"}, user=staff).json

        assert {r["username"] for r in roster["registrars"]} == {r.user.username for r in juniors_db}
        assert roster["shifts"] == [
            {"id": shift.pk, "date": "2024-12-23", "type": "LONG", "registrar": juniors_db[0].pk, "extra_duty": False}
        ]
        [returned] = roster["leaves"]
        assert returned["id"] == leave.pk
        assert returned["registrar"] == juniors_db[1].pk
        assert (returned["type"], returned["portion"]) == ("ANNUAL", "ALL")
        assert (returned["reg_approved"], returned["dot_approved"], returned["cancelled"]) == (None, None, False)

    def test_published_range(self, app, staff):
        assert app.get("/api/editor/roster", {"week": "2024-12-25"}, user=staff).json["published"] is None

        Settings.objects.create(publish_start_date=date(2024, 1, 1), publish_end_date=date(2024, 12, 31))
        roster = app.get("/api/editor/roster", {"week": "2024-12-25"}, user=staff).json
        assert roster["published"] == {"start": "2024-01-01", "end": "2024-12-31"}


class TestShifts:
    def test_add(self, app, staff, juniors_db):
        body = {"date": CHRISTMAS.isoformat(), "type": "NIGHT", "registrar": juniors_db[0].pk}
        created = app.post_json("/api/editor/shifts", body, user=staff, status=201).json

        shift = Shift.objects.get(pk=created["id"])
        assert (shift.date, shift.type, shift.registrar) == (CHRISTMAS, ShiftType.NIGHT, juniors_db[0])
        assert shift.stat_day, "Christmas is a stat day"
        assert created["extra_duty"] is False

    def test_add_for_unknown_registrar(self, app, staff):
        body = {"date": CHRISTMAS.isoformat(), "type": "NIGHT", "registrar": 999999}
        app.post_json("/api/editor/shifts", body, user=staff, status=404)

    def test_add_unknown_type(self, app, staff, juniors_db):
        body = {"date": CHRISTMAS.isoformat(), "type": "BRUNCH", "registrar": juniors_db[0].pk}
        app.post_json("/api/editor/shifts", body, user=staff, status=422)

    def test_change_type_and_extra_duty(self, app, staff, shift):
        changed = app.patch_json(f"/api/editor/shifts/{shift.pk}", {"type": "SWING"}, user=staff).json
        assert (changed["type"], changed["extra_duty"]) == ("SWING", False)

        changed = app.patch_json(f"/api/editor/shifts/{shift.pk}", {"extra_duty": True}, user=staff).json
        assert (changed["type"], changed["extra_duty"]) == ("SWING", True)

    def test_delete(self, app, staff, shift):
        app.delete(f"/api/editor/shifts/{shift.pk}", user=staff, status=204)
        assert not Shift.objects.filter(pk=shift.pk).exists()

        app.delete(f"/api/editor/shifts/{shift.pk}", user=staff, status=404)


class TestLeaves:
    def test_approve_decline_and_cancel(self, app, staff, leave):
        url = f"/api/editor/leaves/{leave.pk}"

        changed = app.patch_json(url, {"reg_approved": True}, user=staff).json
        assert (changed["reg_approved"], changed["dot_approved"]) == (True, None)

        changed = app.patch_json(url, {"dot_approved": False}, user=staff).json
        assert (changed["reg_approved"], changed["dot_approved"]) == (True, False)

        changed = app.patch_json(url, {"reg_approved": None, "cancelled": True}, user=staff).json
        assert (changed["reg_approved"], changed["cancelled"]) == (None, True)

        leave.refresh_from_db()
        assert (leave.reg_approved, leave.dot_approved, leave.cancelled) == (None, False, True)

    def test_unknown_leave(self, app, staff):
        app.patch_json("/api/editor/leaves/999999", {"cancelled": True}, user=staff, status=404)
