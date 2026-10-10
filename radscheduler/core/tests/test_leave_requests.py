"""
Leave requests for the approval page. Dates are December 2024, when Christmas and Boxing Day fall on the
Wednesday and Thursday:

    Mon 16  23  30
    Tue 17  24
    Wed 18  25 (holiday)
    Thu 19  26 (holiday)
    Fri 20  27
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from radscheduler.core.leave_requests import (
    BULK,
    Filters,
    find_requests,
    group_requests,
    leave_requests,
    leave_year_start,
    overview,
    request_of,
    waiting_count,
)
from radscheduler.core.models import Leave, Registrar, Shift
from radscheduler.roster.models import LeaveType, ShiftType

pytestmark = pytest.mark.django_db


def dec(day):
    return date(2024, 12, day)


def ask(registrar, *days, type=LeaveType.ANNUAL, portion="ALL", minutes_later=0):
    leaves = [Leave.objects.create(date=dec(d), type=type, portion=portion, registrar=registrar) for d in days]
    if minutes_later:
        for leave in leaves:
            Leave.objects.filter(pk=leave.pk).update(created=leave.created + timedelta(minutes=minutes_later))
    return leaves


def dates(request):
    return [leave.date.day for leave in request]


class TestGrouping:
    def test_days_asked_together_across_weekends_and_holidays(self, juniors_db):
        erika = juniors_db[0]
        ask(erika, 20, 23, 24, 27)

        assert [dates(r) for r in group_requests(Leave.objects.all())] == [[20, 23, 24, 27]]

    def test_a_working_day_between_splits_a_request(self, juniors_db):
        ask(juniors_db[0], 16, 17, 19, 20)

        assert [dates(r) for r in group_requests(Leave.objects.all())] == [[16, 17], [19, 20]]

    def test_type_half_and_time_asked_keep_requests_apart(self, juniors_db):
        erika = juniors_db[0]
        ask(erika, 16, 17)
        ask(erika, 18, type=LeaveType.EDU)
        ask(erika, 19, portion="PM")
        ask(erika, 20, minutes_later=10)

        assert sorted(dates(r) for r in group_requests(Leave.objects.all())) == [[16, 17], [18], [19], [20]]


class TestLists:
    def test_waiting_lists_whole_requests_soonest_first(self, juniors_db, admin_user):
        erika, will = juniors_db[0], juniors_db[1]
        later = ask(erika, 23, 24)
        sooner = ask(will, 16)
        # Half decided: the chief registrar has approved one day
        later[0].decide("reg", True, admin_user)
        later[0].save()

        requests = leave_requests(decided=False)["requests"]

        assert [(r["registrar"], dates(r["leaves"])) for r in requests] == [(will.pk, [16]), (erika.pk, [23, 24])]
        assert sooner[0].pk == requests[0]["leaves"][0].pk

    def test_settled_requests_are_decided(self, juniors_db, admin_user):
        erika, will, kelly = juniors_db[0], juniors_db[1], juniors_db[2]
        for leave in ask(erika, 16, 17):
            leave.decide("reg", True, admin_user)
            leave.decide("dot", True, admin_user)
            leave.save()
        [declined] = ask(will, 18)
        declined.decide("reg", False, admin_user)
        declined.save()
        ask(kelly, 19)

        assert len(leave_requests(decided=False)["requests"]) == 1
        decided = leave_requests(decided=True)["requests"]
        # Latest decision first
        assert [r["registrar"] for r in decided] == [will.pk, erika.pk]

    def test_cancelled_leave_is_left_out(self, juniors_db):
        [leave] = ask(juniors_db[0], 16)
        Leave.objects.filter(pk=leave.pk).update(cancelled=True)

        assert leave_requests(decided=False) == {"requests": [], "registrars": [], "holidays": [], "total": 0}


class TestContext:
    def test_the_roster_around_a_request(self, juniors_db):
        erika, will, kelly = juniors_db[0], juniors_db[1], juniors_db[2]
        ask(erika, 23, 24)
        ask(will, 24, portion="AM")
        Shift.objects.create(date=dec(24), type=ShiftType.NIGHT, registrar=erika)
        Shift.objects.create(date=dec(23), type=ShiftType.NIGHT, registrar=kelly)
        Shift.objects.create(date=dec(23), type=ShiftType.SWING, registrar=kelly)

        result = leave_requests(decided=False)
        request = next(r for r in result["requests"] if r["registrar"] == erika.pk)

        # Two days either side, which takes in the weekend before and the holidays after
        assert [d.day for d in request["dates"]] == [21, 22, 23, 24, 25, 26]
        assert [(s.date.day, s.type) for s in request["shifts"]] == [(24, ShiftType.NIGHT)]
        assert [(a["registrar"], a["date"].day, a["portion"], a["approved"]) for a in request["away"]] == [
            (will.pk, 24, "AM", False)
        ]
        days = {d["date"].day: d for d in request["days"]}
        # Monday is covered. On Tuesday she is the only night, so her leave loses it; the swing was short anyway.
        assert (days[23]["lost"], days[23]["short"]) == ([], [])
        assert (days[24]["lost"], days[24]["short"]) == ([["NIGHT"]], [["SWING"]])
        assert days[24]["registrars"] == len(juniors_db)
        # Nobody is rostered on the weekend before, so its cover isn't judged
        assert (days[21]["rostered"], days[23]["rostered"]) == (False, True)
        assert "not_on_leave" in {v.rule for v in request["violations"]}
        assert request["existing_violations"] == []
        assert {h["date"].day for h in result["holidays"]} >= {25, 26}
        assert {r.pk for r in result["registrars"]} == {erika.pk, will.pk}

    def test_rule_breaks_the_leave_causes_apart_from_those_already_there(self, juniors_db):
        erika = juniors_db[0]
        # Two weekends running break every-second-weekend-free whatever happens
        for day in (14, 15, 21, 22):
            Shift.objects.create(date=dec(day), type=ShiftType.LONG, registrar=erika)
        ask(erika, 23)

        [request] = leave_requests(decided=False)["requests"]

        assert {v.rule for v in request["violations"]} == {"no_weekend_next_to_leave"}
        assert {v.rule for v in request["existing_violations"]} == {"every_second_weekend_free"}


class TestLeaveYears:
    """
    The leave year starts on the first Monday of February: Mon 3 Feb 2025, Mon 2 Feb 2026 and Mon 1 Feb 2027.
    """

    def test_the_leave_year_starts_on_the_first_monday_of_february(self):
        assert leave_year_start(date(2026, 2, 2)) == date(2026, 2, 2)
        assert leave_year_start(date(2026, 2, 1)) == date(2025, 2, 3)
        assert leave_year_start(date(2026, 10, 9)) == date(2026, 2, 2)
        assert leave_year_start(date(2027, 1, 31)) == date(2026, 2, 2)
        assert leave_year_start(date(2027, 2, 1)) == date(2027, 2, 1)

    def add(self, registrar, day, type=LeaveType.ANNUAL, portion="ALL", **decisions):
        return Leave.objects.create(date=day, type=type, portion=portion, registrar=registrar, **decisions)

    def test_each_year_counts_approved_and_waiting_days_by_type_apart_from_the_request(self, juniors_db):
        erika, will = juniors_db[0], juniors_db[1]
        approved = {"reg_approved": True, "dot_approved": True}
        # This leave year: approved annual and education days, a half day waiting, and leave that doesn't count.
        self.add(erika, date(2026, 3, 2), **approved)
        self.add(erika, date(2026, 3, 3), **approved)
        self.add(erika, date(2026, 5, 4), type=LeaveType.EDU, **approved)
        self.add(erika, date(2026, 6, 1), portion="AM", reg_approved=True)
        self.add(erika, date(2026, 6, 2), reg_approved=False)
        self.add(erika, date(2026, 6, 3), cancelled=True)
        self.add(will, date(2026, 3, 2), **approved)
        # The year before.
        self.add(erika, date(2025, 2, 3), **approved)
        self.add(erika, date(2026, 1, 30), type=LeaveType.SICK, **approved)
        # The request: two days in October 2026.
        self.add(erika, date(2026, 10, 12))
        self.add(erika, date(2026, 10, 13))

        requests = leave_requests(decided=False)["requests"]
        (request,) = [r for r in requests if r["leaves"][0].date == date(2026, 10, 12)]
        years = request["years"]

        assert [(y["start"], y["end"], y["lead"]) for y in years] == [
            (date(2026, 2, 2), date(2027, 1, 31), True),
            (date(2025, 2, 3), date(2026, 2, 1), False),
        ]
        assert years[0]["types"] == [
            {"type": LeaveType.ANNUAL, "approved": 2, "waiting": 0.5, "request": 2},
            {"type": LeaveType.EDU, "approved": 1, "waiting": 0, "request": 0},
        ]
        assert years[1]["types"] == [
            {"type": LeaveType.ANNUAL, "approved": 1, "waiting": 0, "request": 0},
            {"type": LeaveType.SICK, "approved": 1, "waiting": 0, "request": 0},
        ]

    def test_a_request_across_the_start_of_a_year_leads_with_both_years(self, juniors_db):
        erika = juniors_db[0]
        for day in (date(2027, 1, 28), date(2027, 1, 29), date(2027, 2, 1)):
            self.add(erika, day)

        (request,) = leave_requests(decided=False)["requests"]

        assert [(y["start"], y["lead"], y["types"][0]["request"]) for y in request["years"]] == [
            (date(2026, 2, 2), True, 2),
            (date(2027, 2, 1), True, 1),
        ]


class TestOverview:
    def keys(self, filters):
        return [(r[0].registrar.user.username, dates(r)) for r in find_requests(filters)]

    def test_status_follows_the_whole_request(self, juniors_db, admin_user):
        erika, will, kelly = juniors_db[0], juniors_db[1], juniors_db[2]
        for leave in ask(erika, 16, 17):
            leave.decide("reg", True, admin_user)
            leave.decide("dot", True, admin_user)
            leave.save()
        [declined] = ask(will, 18)
        declined.decide("dot", False, admin_user)
        declined.save()
        [cancelled] = ask(kelly, 19)
        Leave.objects.filter(pk=cancelled.pk).update(cancelled=True)
        [first, _] = ask(kelly, 23, 24, minutes_later=10)
        first = Leave.objects.get(pk=first.pk)
        first.decide("reg", True, admin_user)
        first.save()

        names = {r.pk: r.user.username for r in juniors_db}
        statuses = {
            status: [names[days[0].registrar_id] for days in find_requests(Filters(status=status, approver="reg"))]
            for status in ("approved", "declined", "cancelled", "waiting", "mine")
        }
        assert statuses == {
            "approved": [erika.user.username],
            "declined": [will.user.username],
            "cancelled": [kelly.user.username],
            "waiting": [kelly.user.username],
            # The chief registrar has decided Kelly's first day, but not her second
            "mine": [kelly.user.username],
        }
        assert len(find_requests(Filters(status="any"))) == 4

    def test_dates_keep_whole_requests_that_touch_them(self, juniors_db):
        erika, will = juniors_db[0], juniors_db[1]
        ask(erika, 16, 17)
        ask(will, 23, 24)

        assert self.keys(Filters(start=dec(17), end=dec(20))) == [(erika.user.username, [16, 17])]
        assert self.keys(Filters(start=dec(24))) == [(will.user.username, [23, 24])]

    def test_types_years_and_a_registrar(self, juniors_db):
        erika, will = juniors_db[0], juniors_db[1]
        ask(erika, 16)
        ask(will, 17, type=LeaveType.EDU)
        Registrar.objects.filter(pk=will.pk).update(start=date.today().replace(month=1, day=1))

        assert self.keys(Filters(types=("EDU",))) == [(will.user.username, [17])]
        assert self.keys(Filters(years=(1,))) == [(will.user.username, [17])]
        assert self.keys(Filters(registrar=erika.pk)) == [(erika.user.username, [16])]

    def test_registrars_who_have_finished_are_left_out(self, juniors_db):
        erika, will = juniors_db[0], juniors_db[1]
        ask(erika, 16)
        ask(will, 17)
        Registrar.objects.filter(pk=will.pk).update(finish=date.today() - timedelta(days=1))

        assert self.keys(Filters()) == [(erika.user.username, [16])]
        assert waiting_count(None) == 1

    def test_sorts(self, juniors_db):
        erika, will = juniors_db[0], juniors_db[1]
        ask(erika, 16, minutes_later=10)
        ask(will, 23, 24)

        assert [d for _, d in self.keys(Filters(sort="leave"))] == [[16], [23, 24]]
        assert [d for _, d in self.keys(Filters(sort="leave-desc"))] == [[23, 24], [16]]
        # Erika asked ten minutes after Will
        assert [d for _, d in self.keys(Filters(sort="asked-desc"))] == [[16], [23, 24]]
        assert [d for _, d in self.keys(Filters(sort="length-desc"))] == [[23, 24], [16]]

    def test_rows_check_what_still_waits(self, juniors_db, admin_user):
        erika, will = juniors_db[0], juniors_db[1]
        ask(erika, 16, 17)
        [settled] = ask(will, 18)
        settled.decide("reg", False, admin_user)
        settled.save()
        Shift.objects.create(date=dec(16), type=ShiftType.SWING, registrar=erika)

        rows = {row["registrar"]: row for row in overview(Filters(status="any"))["rows"]}

        assert rows[will.pk]["status"] == "declined" and rows[will.pk]["checks"] is None
        checks = rows[erika.pk]["checks"]
        # Erika is the only one rostered on the Monday, so her leave loses its swing; the Tuesday has no roster
        assert (checks["lost"], checks["days"], checks["unrostered"]) == (1, 2, 1)
        assert (checks["away"], checks["roster"]) == (1, len(juniors_db))


class TestAsked:
    def test_leave_loaded_in_bulk_has_no_asked_time(self, juniors_db):
        erika, will = juniors_db[0], juniors_db[1]
        ask(erika, 16)
        loaded = timezone.now().replace(microsecond=0) - timedelta(days=400)
        Leave.objects.bulk_create(
            Leave(date=date(2023, 1, 2) + timedelta(days=n), type=LeaveType.ANNUAL, registrar=will)
            for n in range(BULK)
        )
        Leave.objects.filter(registrar=will).update(created=loaded)

        rows = {row["registrar"]: row for row in overview(Filters(status="any"))["rows"]}

        assert rows[erika.pk]["asked"] is not None
        assert rows[will.pk]["asked"] is None


class TestRequestOf:
    def test_the_whole_request_from_any_day(self, juniors_db):
        first, second = ask(juniors_db[0], 16, 17)
        ask(juniors_db[0], 19)

        assert dates(request_of(second.pk)) == [16, 17]
        assert request_of(first.pk + 1000) is None

    def test_cancelled_days_are_a_request_of_their_own(self, juniors_db):
        first, second = ask(juniors_db[0], 16, 17)
        Leave.objects.filter(pk=second.pk).update(cancelled=True)

        assert dates(request_of(first.pk)) == [16]
        assert dates(request_of(second.pk)) == [17]
