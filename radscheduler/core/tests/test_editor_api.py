from datetime import date

import pytest

from radscheduler.core.models import Leave, Settings, Shift, Status
from radscheduler.roster.models import LeaveType, ShiftType, StatusType

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
        assert {r["name"] for r in roster["registrars"]} == {r.user.name for r in juniors_db}
        assert roster["shifts"] == [
            {"id": shift.pk, "date": "2024-12-23", "type": "LONG", "registrar": juniors_db[0].pk, "extra_duty": False}
        ]
        [returned] = roster["leaves"]
        assert returned["id"] == leave.pk
        assert returned["registrar"] == juniors_db[1].pk
        assert (returned["type"], returned["portion"]) == ("ANNUAL", "ALL")
        assert (returned["reg_approved"], returned["dot_approved"], returned["cancelled"]) == (None, None, False)
        assert (returned["reg_decided_by"], returned["printed"], returned["microster"]) == (None, False, False)

    def test_statuses_in_the_window(self, app, staff, juniors_db):
        exam = Status.objects.create(
            registrar=juniors_db[0], type=StatusType.PRE_EXAM, start=date(2024, 12, 1), end=date(2024, 12, 20)
        )
        Status.objects.create(
            registrar=juniors_db[1], type=StatusType.BUDDY, start=date(2025, 3, 1), end=date(2025, 3, 31)
        )

        roster = app.get("/api/editor/roster", {"week": "2024-12-25"}, user=staff).json

        assert roster["statuses"] == [
            {
                "id": exam.pk,
                "registrar": juniors_db[0].pk,
                "type": "PREEXAM",
                "start": "2024-12-01",
                "end": "2024-12-20",
                "weekdays": [],
                "shift_types": [],
                "comment": "",
            }
        ]

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

    def test_delete_returns_the_deleted_shift(self, app, staff, shift):
        deleted = app.delete(f"/api/editor/shifts/{shift.pk}", user=staff, status=200).json

        assert (deleted["id"], deleted["type"]) == (shift.pk, "LONG")
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

    def test_the_director_makes_only_their_own_decision(self, app, director, leave):
        url = f"/api/editor/leaves/{leave.pk}"

        changed = app.patch_json(url, {"dot_approved": True}, user=director).json
        assert changed["dot_approved"] is True

        app.patch_json(url, {"reg_approved": True}, user=director, status=403)
        body = {"ids": [leave.pk], "reg_approved": True, "dot_approved": True}
        app.patch_json("/api/editor/leaves", body, user=director, status=403)
        leave.refresh_from_db()
        assert (leave.reg_approved, leave.dot_approved) == (None, True)

    def test_office_staff_decide_nothing(self, app, office_staff, leave):
        url = f"/api/editor/leaves/{leave.pk}"
        app.patch_json(url, {"dot_approved": True}, user=office_staff, status=403)
        app.patch_json(url, {"reg_approved": True}, user=office_staff, status=403)
        assert app.patch_json(url, {"microster": True}, user=office_staff).json["microster"] is True

    def test_unknown_leave(self, app, staff):
        app.patch_json("/api/editor/leaves/999999", {"cancelled": True}, user=staff, status=404)

    def test_records_who_decided_and_when(self, app, staff, leave):
        url = f"/api/editor/leaves/{leave.pk}"

        changed = app.patch_json(url, {"reg_approved": True}, user=staff).json
        assert changed["reg_decided_by"] == (staff.name or staff.username)
        assert changed["reg_decided_at"] is not None
        assert changed["dot_decided_by"] is None

        changed = app.patch_json(url, {"reg_approved": None}, user=staff).json
        assert (changed["reg_decided_by"], changed["reg_decided_at"]) == (None, None)

    def test_microster(self, app, staff, leave):
        changed = app.patch_json(f"/api/editor/leaves/{leave.pk}", {"microster": True}, user=staff).json
        assert changed["microster"] is True

    def test_decide_several_days_at_once(self, app, staff, juniors_db):
        days = [
            Leave.objects.create(date=date(2024, 12, d), type=LeaveType.ANNUAL, registrar=juniors_db[0])
            for d in (16, 17, 18)
        ]
        other = Leave.objects.create(date=date(2024, 12, 16), type=LeaveType.ANNUAL, registrar=juniors_db[1])

        body = {"ids": [leave.pk for leave in days], "reg_approved": True}
        changed = app.patch_json("/api/editor/leaves", body, user=staff).json

        assert [leave["date"] for leave in changed] == ["2024-12-16", "2024-12-17", "2024-12-18"]
        assert all(leave["reg_approved"] and leave["reg_decided_by"] for leave in changed)
        other.refresh_from_db()
        assert other.reg_approved is None


class TestChecks:
    def test_a_shift_on_leave(self, app, staff, juniors_db):
        Leave.objects.create(date=date(2024, 12, 17), type=LeaveType.ANNUAL, registrar=juniors_db[0])
        Shift.objects.create(date=date(2024, 12, 17), type=ShiftType.NIGHT, registrar=juniors_db[0])

        checks = app.get("/api/editor/roster", {"week": "2024-12-25"}, user=staff).json["checks"]

        assert {
            "rule": "not_on_leave",
            "clause": None,
            "registrar": juniors_db[0].pk,
            "dates": ["2024-12-17"],
            "message": "Rostered on Tue 17 Dec while on leave (annual).",
            "variance": None,
        } in checks["violations"]

    def test_declined_leave_does_not_clash(self, app, staff, juniors_db):
        Leave.objects.create(
            date=date(2024, 12, 17), type=LeaveType.ANNUAL, registrar=juniors_db[0], reg_approved=False
        )
        Shift.objects.create(date=date(2024, 12, 17), type=ShiftType.NIGHT, registrar=juniors_db[0])

        checks = app.get("/api/editor/roster/checks", {"week": "2024-12-25"}, user=staff).json

        assert not [v for v in checks["violations"] if v["rule"] == "not_on_leave"]

    def test_contract_clause(self, app, staff, juniors_db):
        Shift.objects.create(date=date(2024, 12, 17), type=ShiftType.LONG, registrar=juniors_db[0])
        Shift.objects.create(date=date(2024, 12, 17), type=ShiftType.NIGHT, registrar=juniors_db[0])

        checks = app.get("/api/editor/roster/checks", {"week": "2024-12-25"}, user=staff).json

        [clash] = [v for v in checks["violations"] if v["rule"] == "one_duty_per_day"]
        assert (clash["clause"], clash["dates"]) == ("STONZ 17.2.5", ["2024-12-17"])

    def test_an_agreed_variance_is_kept_apart(self, app, staff, juniors_db):
        # A weekend of long days after a full week, with both RDOs the week after
        for day, shift_type in ((14, ShiftType.LONG), (15, ShiftType.LONG), (19, ShiftType.RDO), (20, ShiftType.RDO)):
            Shift.objects.create(date=date(2024, 12, day), type=shift_type, registrar=juniors_db[0])

        checks = app.get("/api/editor/roster/checks", {"week": "2024-12-11"}, user=staff).json

        assert checks["violations"] == []
        [variance] = checks["variances"]
        assert (variance["clause"], variance["variance"] is not None) == ("STONZ 17.1.2", True)

        Settings.objects.create(publish_start_date=date(2024, 11, 1), publish_end_date=date(2024, 11, 30))
        preview = app.get("/api/editor/published/preview", {"start": "2024-11-01", "end": "2024-12-31"}, user=staff)
        assert preview.json["violations"] == []

    def test_breaks_outside_the_window_are_left_out(self, app, staff, juniors_db):
        Shift.objects.create(date=date(2024, 11, 5), type=ShiftType.LONG, registrar=juniors_db[0])
        Shift.objects.create(date=date(2024, 11, 5), type=ShiftType.NIGHT, registrar=juniors_db[0])

        checks = app.get("/api/editor/roster/checks", {"week": "2024-12-25"}, user=staff).json

        assert checks["violations"] == []

    def test_workload_over_26_weeks(self, app, staff, juniors_db):
        erika, will = juniors_db[0], juniors_db[1]
        Shift.objects.create(date=date(2024, 12, 17), type=ShiftType.LONG, registrar=erika)  # Tue: 1
        Shift.objects.create(date=date(2024, 12, 21), type=ShiftType.LONG, registrar=erika)  # Sat: 3
        Shift.objects.create(date=date(2024, 12, 20), type=ShiftType.NIGHT, registrar=erika)  # Fri night: 5/3
        Shift.objects.create(date=date(2024, 9, 3), type=ShiftType.NIGHT, registrar=erika)  # Tue night: 7/4
        Shift.objects.create(date=date(2024, 12, 18), type=ShiftType.RDO, registrar=erika)  # no load
        Shift.objects.create(date=date(2024, 12, 19), type=ShiftType.LONG, registrar=erika, extra_duty=True)
        Shift.objects.create(date=date(2024, 5, 1), type=ShiftType.LONG, registrar=will)  # over 26 weeks ago

        checks = app.get("/api/editor/roster/checks", {"week": "2024-12-25"}, user=staff).json

        assert checks["workload"] == [{"registrar": erika.pk, "load": round((1 + 3 + 5 / 3 + 7 / 4) / 10, 1)}]


class TestPublished:
    def test_set_and_change_the_published_range(self, app, staff):
        body = {"start": "2025-01-01", "end": "2025-06-30"}
        assert app.put_json("/api/editor/published", body, user=staff).json == body

        body = {"start": "2025-02-01", "end": "2025-12-31"}
        app.put_json("/api/editor/published", body, user=staff)
        settings = Settings.objects.get()
        assert (settings.publish_start_date, settings.publish_end_date) == (date(2025, 2, 1), date(2025, 12, 31))

    def test_start_after_end_is_rejected(self, app, staff):
        Settings.objects.create(publish_start_date=date(2025, 1, 1), publish_end_date=date(2025, 6, 30))

        body = {"start": "2025-07-01", "end": "2025-06-30"}
        response = app.put_json("/api/editor/published", body, user=staff, status=422)

        assert "start" in response.json["detail"]
        assert Settings.objects.get().publish_start_date == date(2025, 1, 1)


class TestUnassignedShifts:
    def test_roster_includes_shifts_without_a_registrar(self, app, staff):
        open_shift = Shift.objects.create(date=CHRISTMAS, type=ShiftType.LONG, extra_duty=True)

        roster = app.get("/api/editor/roster", {"week": "2024-12-25"}, user=staff).json

        assert {"id": open_shift.pk, "date": "2024-12-25", "type": "LONG", "registrar": None, "extra_duty": True} in (
            roster["shifts"]
        )


class TestLeaveRequests:
    def test_waiting_requests_with_their_roster(self, app, director, juniors_db):
        for day in (16, 17):
            Leave.objects.create(date=date(2024, 12, day), type=LeaveType.ANNUAL, registrar=juniors_db[0])

        body = app.get("/api/editor/leave-requests", user=director).json

        [request] = body["requests"]
        assert [leave["date"] for leave in request["leaves"]] == ["2024-12-16", "2024-12-17"]
        assert request["dates"][0] == "2024-12-14" and request["dates"][-1] == "2024-12-19"
        # Nobody is rostered, so nothing is lost by the leave and everything is short
        assert (request["days"][2]["lost"], request["days"][2]["short"]) == ([], [["SWING"], ["NIGHT"]])
        assert [r["name"] for r in body["registrars"]] == [juniors_db[0].user.name or juniors_db[0].user.username]
        assert body["total"] == 1
        assert app.get("/api/editor/leave-requests", {"status": "approved"}, user=director).json["requests"] == []

    def test_the_overview_filters_and_counts(self, app, director, juniors_db):
        erika, will = juniors_db[0], juniors_db[1]
        Leave.objects.create(date=date(2024, 12, 16), type=LeaveType.ANNUAL, registrar=erika)
        Leave.objects.create(date=date(2024, 12, 17), type=LeaveType.EDU, registrar=will)

        body = app.get("/api/editor/leave-requests/overview", {"types": "EDU"}, user=director).json

        assert body["total"] == 1
        [row] = body["rows"]
        assert (row["registrar"], row["status"], row["days"]) == (will.pk, "waiting", 1)
        # Still waiting, so it comes with the checks behind its verdict
        assert row["checks"]["days"] == 1 and row["checks"]["breaks"] == 0
        # The Director's own decision waits on both requests
        assert app.get("/api/editor/leave-requests/counts", user=director).json == {"mine": 2, "all": 2}

    def test_one_request_for_the_shelf(self, app, director, juniors_db):
        first, second = (
            Leave.objects.create(date=date(2024, 12, day), type=LeaveType.ANNUAL, registrar=juniors_db[0])
            for day in (16, 17)
        )

        body = app.get(f"/api/editor/leave-requests/{second.pk}", user=director).json

        [request] = body["requests"]
        assert [leave["id"] for leave in request["leaves"]] == [first.pk, second.pk]
        assert request["asked"] is not None
        app.get(f"/api/editor/leave-requests/{second.pk + 1000}", user=director, status=404)

    def test_the_overview_refuses_filters_it_does_not_know(self, app, director, juniors_db):
        app.get("/api/editor/leave-requests/overview", {"status": "lost"}, user=director, status=422)
        app.get("/api/editor/leave-requests/overview", {"types": "HOLIDAY"}, user=director, status=422)
        app.get("/api/editor/leave-requests/overview", {"years": "two"}, user=director, status=422)

    def test_registrars_cannot_list_them(self, app, juniors_db):
        app.get("/api/editor/leave-requests", user=juniors_db[0].user, status=401)


class TestPublishPreview:
    def test_counts_what_registrars_gain_and_lose(self, app, staff, juniors_db):
        Settings.objects.create(publish_start_date=date(2025, 1, 1), publish_end_date=date(2025, 1, 31))
        Shift.objects.create(date=date(2025, 1, 10), type=ShiftType.LONG, registrar=juniors_db[0])
        Shift.objects.create(date=date(2025, 2, 10), type=ShiftType.LONG, registrar=juniors_db[0])
        Shift.objects.create(date=date(2025, 2, 11), type=ShiftType.NIGHT, registrar=juniors_db[1])
        Leave.objects.create(date=date(2025, 2, 12), type=LeaveType.ANNUAL, registrar=juniors_db[2])
        Leave.objects.create(date=date(2025, 2, 13), type=LeaveType.ANNUAL, registrar=juniors_db[2], cancelled=True)

        preview = app.get("/api/editor/published/preview", {"start": "2025-01-15", "end": "2025-02-28"}, user=staff)

        counts = ("shifts_shown", "leave_shown", "shifts_hidden", "leave_hidden")
        assert [preview.json[key] for key in counts] == [2, 1, 1, 0]

    def test_everything_is_new_when_nothing_is_published(self, app, staff, shift, leave):
        preview = app.get("/api/editor/published/preview", {"start": "2024-12-01", "end": "2024-12-31"}, user=staff)

        counts = ("shifts_shown", "leave_shown", "shifts_hidden", "leave_hidden")
        assert [preview.json[key] for key in counts] == [1, 1, 0, 0]

    def test_health_of_the_newly_published_days(self, app, staff, juniors_db):
        Settings.objects.create(publish_start_date=date(2024, 12, 1), publish_end_date=date(2024, 12, 23))
        for day in (24, 25, 26):
            Shift.objects.create(date=date(2024, 12, day), type=ShiftType.NIGHT, registrar=juniors_db[day - 24])
        Shift.objects.create(date=date(2024, 12, 24), type=ShiftType.SWING, registrar=juniors_db[3])
        Shift.objects.create(date=date(2024, 12, 25), type=ShiftType.LONG, registrar=juniors_db[3])
        Shift.objects.create(date=date(2024, 12, 26), type=ShiftType.LONG, registrar=juniors_db[3])
        Leave.objects.create(date=date(2024, 12, 24), type=LeaveType.ANNUAL, registrar=juniors_db[4])
        Leave.objects.create(date=date(2024, 12, 20), type=LeaveType.ANNUAL, registrar=juniors_db[4])

        preview = app.get("/api/editor/published/preview", {"start": "2024-12-01", "end": "2024-12-27"}, user=staff)

        # Christmas and Boxing Day are holidays, covered by a long day; the 27th has nobody.
        assert preview.json["gaps"] == [{"date": "2024-12-27", "needs": [["SWING"], ["NIGHT"]]}]
        rules = {(v["rule"], v["registrar"]) for v in preview.json["violations"]}
        assert ("no_back_to_back_long_days", juniors_db[3].pk) in rules
        assert preview.json["leave_waiting"] == 1

    def test_a_range_of_centuries_is_checked_only_a_year_ahead(self, app, staff, juniors_db):
        Settings.objects.create(publish_start_date=date(2024, 12, 1), publish_end_date=date(2024, 12, 31))
        Shift.objects.create(date=date(2025, 6, 2), type=ShiftType.LONG, registrar=juniors_db[0])

        # What a date box holds while "2026" is typed into it: year 0002.
        preview = app.get("/api/editor/published/preview", {"start": "2024-12-01", "end": "0002-12-31"}, user=staff)
        assert preview.json["checked_to"] is None  # start after end: nothing new

        preview = app.get("/api/editor/published/preview", {"start": "0002-01-01", "end": "2025-12-31"}, user=staff)

        assert preview.json["shifts_shown"] == 1  # the counts still cover the whole range
        assert preview.json["checked_to"] == "0003-01-01"  # 366 days on
        assert all(gap["date"] <= "0003-01-01" for gap in preview.json["gaps"])
