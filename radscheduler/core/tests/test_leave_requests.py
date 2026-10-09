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

from radscheduler.core.leave_requests import group_requests, leave_requests
from radscheduler.core.models import Leave, Shift
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

        assert leave_requests(decided=False) == {"requests": [], "registrars": [], "holidays": []}


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
