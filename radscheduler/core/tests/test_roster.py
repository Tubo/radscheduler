from datetime import date

import pytest
from django.urls import reverse
from freezegun import freeze_time

from radscheduler.core import roster_weeks
from radscheduler.core.models import Leave, Registrar, Settings, Shift
from radscheduler.roster.models import LeaveType, ShiftType
from radscheduler.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

# A Wednesday in October 2026, whose calendar runs from Monday 28 September to Sunday 1 November.
TODAY = date(2026, 10, 14)


def registrar(username, name, start=date(2025, 2, 2), **kwargs):
    return Registrar.objects.create(user=UserFactory(username=username, name=name), start=start, **kwargs)


@pytest.fixture
def team(db):
    return {
        "rachel": registrar("rachelb", "Rachel Brown"),
        "ed": registrar("edh", "Ed Hart", start=date(2024, 2, 2)),
        "mo": registrar("mog", "Mo Gray", start=date(2023, 2, 2)),
    }


def chips_of(roster, day):
    return [(chip.type, chip.name) for week in roster["weeks"] for d in week.days if d.date == day for chip in d.chips]


def day_of(roster, day):
    return next(d for week in roster["weeks"] for d in week.days if d.date == day)


class TestShortNames:
    def test_first_name_and_initial_or_the_whole_name_where_two_would_share_one(self, db):
        a = registrar("a", "Will Gillespie")
        b = registrar("b", "Will Grant")
        c = registrar("c", "Anthony (Wai Kit) Lau")
        d = registrar("d", "Moritz")

        assert roster_weeks.short_names([a, b, c, d]) == {
            a.pk: "Will Gillespie",
            b.pk: "Will Grant",
            c.pk: "Anthony L.",
            d.pk: "Moritz",
        }

    def test_a_username_stands_in_for_a_missing_name(self, db):
        a = registrar("kelly", "")

        assert roster_weeks.short_names([a]) == {a.pk: "kelly"}


class TestDepartmentRoster:
    def test_a_day_runs_in_the_order_of_the_day_then_days_off_then_leave(self, team):
        day = date(2026, 10, 14)
        Shift.objects.create(date=day, type=ShiftType.NIGHT, registrar=team["ed"])
        Shift.objects.create(date=day, type=ShiftType.SWING, registrar=team["rachel"])
        Shift.objects.create(date=day, type=ShiftType.RDO, registrar=team["mo"])
        Leave.objects.create(date=day, type=LeaveType.ANNUAL, registrar=registrar("kate", "Kate Ito"))

        roster = roster_weeks.build(TODAY, TODAY)

        assert chips_of(roster, day) == [
            ("SWING", "Rachel B."),
            ("NIGHT", "Ed H."),
            ("RDO", "Mo G."),
            ("ANNUAL", "Kate I."),
        ]

    def test_leave_shows_whether_it_is_decided_and_leaves_out_declined_and_cancelled(self, team):
        day = date(2026, 10, 15)
        Leave.objects.create(date=day, type=LeaveType.ANNUAL, registrar=team["rachel"])
        Leave.objects.create(date=day, type=LeaveType.EDU, registrar=team["ed"], reg_approved=True, dot_approved=True)
        Leave.objects.create(date=day, type=LeaveType.CONF, registrar=team["mo"], reg_approved=True)
        Leave.objects.create(
            date=date(2026, 10, 16), type=LeaveType.ANNUAL, registrar=team["rachel"], reg_approved=False
        )
        Leave.objects.create(date=date(2026, 10, 16), type=LeaveType.ANNUAL, registrar=team["ed"], cancelled=True)

        roster = roster_weeks.build(TODAY, TODAY)

        assert [(c.type, c.state) for c in day_of(roster, day).chips] == [
            ("ANNUAL", "pending"),
            ("EDU", "approved"),
            ("CONF", "partial"),
        ]
        assert day_of(roster, date(2026, 10, 16)).chips == []

    def test_days_marks_today_weekends_and_holidays(self, team):
        roster = roster_weeks.build(TODAY, TODAY)

        assert day_of(roster, TODAY).today
        assert day_of(roster, date(2026, 10, 17)).weekend
        assert day_of(roster, date(2026, 10, 26)).holiday == "Labour Day"

    def test_a_month_runs_from_the_monday_before_its_first_to_the_sunday_after_its_last(self, team):
        roster = roster_weeks.build(TODAY, TODAY)

        days = [day for week in roster["weeks"] for day in week.days]
        assert (days[0].date, days[-1].date, len(roster["weeks"])) == (date(2026, 9, 28), date(2026, 11, 1), 5)
        assert [day.date for day in days if day.outside] == [
            date(2026, 9, 28),
            date(2026, 9, 29),
            date(2026, 9, 30),
            date(2026, 11, 1),
        ]

    def test_a_busy_day_folds_its_days_off_and_leave_into_a_line(self, team):
        day = date(2026, 10, 14)
        Shift.objects.create(date=day, type=ShiftType.SWING, registrar=team["rachel"])
        Shift.objects.create(date=day, type=ShiftType.RDO, registrar=team["ed"])
        Leave.objects.create(date=day, type=LeaveType.ANNUAL, registrar=team["mo"])
        Leave.objects.create(date=day, type=LeaveType.EDU, registrar=registrar("kate", "Kate Ito"))
        quiet = date(2026, 10, 15)
        Shift.objects.create(date=quiet, type=ShiftType.RDO, registrar=team["ed"])
        Leave.objects.create(date=quiet, type=LeaveType.ANNUAL, registrar=team["mo"])

        roster = roster_weeks.build(TODAY, TODAY)

        busy = day_of(roster, day)
        assert [(chip.type, chip.folded) for chip in busy.chips] == [
            ("SWING", False),
            ("RDO", True),
            ("ANNUAL", True),
            ("EDU", True),
        ]
        assert (busy.off_count, busy.leave_count, busy.waiting_count) == (1, 2, 2)
        assert day_of(roster, quiet).folded == []

    def test_a_registrars_own_roster_never_folds(self, team):
        day = date(2026, 10, 14)
        for registrar_ in team.values():
            Shift.objects.create(date=day, type=ShiftType.RDO, registrar=registrar_)
        Leave.objects.create(date=day, type=LeaveType.ANNUAL, registrar=team["rachel"])

        roster = roster_weeks.build(TODAY, TODAY, mine=team["rachel"])

        assert day_of(roster, day).folded == []

    def test_nothing_past_the_published_roster_shows_and_the_months_stop_there(self, team):
        Settings.objects.create(publish_start_date=date(2026, 10, 1), publish_end_date=date(2026, 10, 20))
        Shift.objects.create(date=date(2026, 10, 20), type=ShiftType.SWING, registrar=team["rachel"])
        Shift.objects.create(date=date(2026, 10, 21), type=ShiftType.SWING, registrar=team["rachel"])

        october = roster_weeks.build(TODAY, TODAY)
        november = roster_weeks.build(date(2026, 11, 1), TODAY)

        assert chips_of(october, date(2026, 10, 20)) == [("SWING", "Rachel B.")]
        assert chips_of(october, date(2026, 10, 21)) == []
        assert not day_of(october, date(2026, 10, 21)).published
        # Nothing before October, and a phone runs on no further; a desktop may step into November, to be told.
        assert (october["prev"], october["next"], october["next_page"]) == (None, None, date(2026, 11, 1))
        assert (november["unpublished"], november["next_page"]) == (True, None)

    def test_years_and_what_to_show_narrow_it(self, team):
        day = date(2026, 10, 14)
        Shift.objects.create(date=day, type=ShiftType.SWING, registrar=team["rachel"])
        Shift.objects.create(date=day, type=ShiftType.SLEEP, registrar=team["ed"])
        Leave.objects.create(date=day, type=LeaveType.ANNUAL, registrar=team["mo"])
        rachels_year = Registrar.objects.get(pk=team["rachel"].pk).year

        with freeze_time(TODAY):
            by_year = roster_weeks.build(TODAY, TODAY, filters=roster_weeks.Filters(years=(rachels_year,)))
        no_leave = roster_weeks.build(TODAY, TODAY, filters=roster_weeks.Filters(show=("oncall", "off")))

        assert chips_of(by_year, day) == [("SWING", "Rachel B.")]
        assert chips_of(no_leave, day) == [("SWING", "Rachel B."), ("SLEEP", "Ed H.")]


class TestMyRoster:
    def test_only_their_days_with_who_else_is_on_call_beside_theirs(self, team):
        Shift.objects.create(date=date(2026, 10, 14), type=ShiftType.SWING, registrar=team["rachel"])
        Shift.objects.create(date=date(2026, 10, 14), type=ShiftType.NIGHT, registrar=team["ed"])
        Shift.objects.create(date=date(2026, 10, 14), type=ShiftType.RDO, registrar=team["mo"])
        Shift.objects.create(date=date(2026, 10, 15), type=ShiftType.NIGHT, registrar=team["ed"])
        Leave.objects.create(date=date(2026, 10, 15), type=LeaveType.ANNUAL, registrar=team["rachel"])
        Leave.objects.create(date=date(2026, 10, 15), type=LeaveType.ANNUAL, registrar=team["mo"])

        roster = roster_weeks.build(TODAY, TODAY, mine=team["rachel"])

        wednesday, thursday = day_of(roster, date(2026, 10, 14)), day_of(roster, date(2026, 10, 15))
        assert [chip.type for chip in wednesday.chips] == ["SWING"]
        assert [(mate.type, mate.name) for mate in wednesday.mates] == [("NIGHT", "Ed H.")]
        assert [chip.type for chip in thursday.chips] == ["ANNUAL"]
        assert thursday.mates == []

    def test_their_next_on_call_shift_in_the_published_roster(self, team):
        Settings.objects.create(publish_start_date=date(2026, 10, 1), publish_end_date=date(2026, 10, 31))
        Shift.objects.create(date=date(2026, 10, 13), type=ShiftType.LONG, registrar=team["rachel"])
        Shift.objects.create(date=date(2026, 10, 16), type=ShiftType.RDO, registrar=team["rachel"])
        Shift.objects.create(date=date(2026, 10, 17), type=ShiftType.LONG, registrar=team["rachel"])
        Shift.objects.create(date=date(2026, 11, 7), type=ShiftType.LONG, registrar=team["ed"])

        assert roster_weeks.next_on_call(team["rachel"], TODAY).date == date(2026, 10, 17)
        assert roster_weeks.next_on_call(team["ed"], TODAY) is None


def test_the_key_gives_each_shifts_hours():
    key = {item["type"]: item["hours"] for item in roster_weeks.shift_key()}

    assert key == {
        "HELP": "8am–12pm",
        "LONG": "8am–11pm",
        "SWING": "12pm–10pm",
        "NIGHT": "10pm–8am",
        "RDO": "",
        "SLEEP": "",
    }


@freeze_time(TODAY)
class TestPage:
    def test_visitors_see_the_department_roster_with_chips_that_follow_a_registrar(self, app, team):
        Shift.objects.create(date=TODAY, type=ShiftType.SWING, registrar=team["rachel"])

        page = app.get(reverse("home")).html

        assert page.select_one("h1").text.strip() == "Roster"
        chip = page.select_one(".rb-chip")
        assert " ".join(chip.text.split()) == "Swing Rachel B."
        assert f"follow={team['rachel'].pk}" in chip["href"]
        assert page.select_one(".rb-views") is None

    def test_registrars_open_on_their_own_roster_and_the_choice_is_remembered(self, app, team):
        user = team["rachel"].user
        Shift.objects.create(date=date(2026, 10, 17), type=ShiftType.LONG, registrar=team["rachel"])

        mine = app.get(reverse("home"), user=user).html
        app.get(reverse("home"), {"view": "dept"}, user=user)
        again = app.get(reverse("home"), user=user).html

        assert mine.select_one("h1").text.strip() == "My roster"
        assert " ".join(mine.select_one(".rb-lead").text.split()) == "Next on call: Long day, Sat 17 Oct in 3 days"
        assert again.select_one("h1").text.strip() == "Roster"

    def test_anyone_without_a_roster_of_their_own_gets_the_departments(self, app, admin_user):
        page = app.get(reverse("home"), {"view": "mine"}, user=admin_user).html

        assert page.select_one("h1").text.strip() == "Roster"

    def test_following_a_registrar_rings_their_chips_and_steps_back_the_rest(self, app, team):
        Shift.objects.create(date=TODAY, type=ShiftType.SWING, registrar=team["rachel"])
        Shift.objects.create(date=TODAY, type=ShiftType.NIGHT, registrar=team["ed"])
        ed = team["ed"].pk

        page = app.get(reverse("home"), {"view": "dept", "follow": ed}).html

        style = page.select_one("#rb-follow-css").text
        assert f'.rb-chip[data-r]:not([data-r="{ed}"])' in style
        assert f'.rb-chip[data-r="{ed}"].is-folded' in style
        assert [c.get("aria-describedby") for c in page.select(".rb-chip")] == [None, "rb-following-name"]
        assert " ".join(page.select_one(".rb-following-text").text.split()) == "Following Ed Hart:"
        assert page.select_one(".rb-following-count").text == "1 on call in October"
        # Its own chip stops following them, and the months either side keep following them.
        assert "follow=" not in page.select(".rb-chip")[1]["href"]

    def test_filters_narrow_the_department_roster_and_can_be_cleared(self, app, team):
        Shift.objects.create(date=TODAY, type=ShiftType.SWING, registrar=team["rachel"])
        Leave.objects.create(date=TODAY, type=LeaveType.ANNUAL, registrar=team["ed"])

        page = app.get(reverse("home"), {"view": "dept", "show": "leave"}).html

        assert [c.text.split()[0] for c in page.select(".rb-chip")] == ["Annual"]
        assert "is-narrowing" in page.select_one("select[name=show]")["class"]
        assert page.select_one(".rb-clear").text == "Clear"
        assert page.select_one(".rb-count").text == "1"

    def test_the_filters_are_grey_until_they_narrow_the_roster(self, app, team):
        page = app.get(reverse("home"), {"view": "dept"}).html

        assert page.select_one("input[name=year][value='']").has_attr("checked")
        assert page.select_one(".is-narrowing") is None
        assert page.select_one(".rb-clear") is None

    def test_months_page_on_a_wide_screen_and_keep_the_choices(self, app, team):
        Shift.objects.create(date=date(2026, 12, 1), type=ShiftType.SWING, registrar=team["rachel"])
        Shift.objects.create(date=date(2026, 9, 1), type=ShiftType.SWING, registrar=team["rachel"])

        page = app.get(reverse("home"), {"view": "dept", "follow": team["ed"].pk, "show": "oncall"}).html

        prev, next_ = page.select_one("a.rb-prev"), page.select_one("a.rb-next")
        assert "month=2026-09" in prev["href"] and "month=2026-11" in next_["href"]
        assert f"follow={team['ed'].pk}" in next_["href"] and "show=oncall" in next_["href"]
        assert next_["up-target"] == "#rb-main"
        assert page.select_one(".rb-monthtitle").text == "October 2026"

    def test_on_a_phone_the_next_month_runs_on_under_this_one(self, app, team):
        Shift.objects.create(date=date(2026, 12, 1), type=ShiftType.SWING, registrar=team["rachel"])

        later = app.get(reverse("home")).html.select_one(".rb-later")

        assert "month=2026-11" in later["href"]
        assert later.text == "Show November"

    def test_the_end_of_the_published_roster_is_said_rather_than_left_blank(self, app, team):
        Settings.objects.create(publish_start_date=date(2026, 10, 12), publish_end_date=date(2026, 10, 20))

        page = app.get(reverse("home")).html

        assert page.select_one(".rb-later") is None
        assert "it runs to Tue 20 Oct" in " ".join(page.select_one("#rb-end").text.split())
        assert page.select_one("a.rb-prev") is None
        assert len(page.select(".rb-day.is-unpublished")) == 35 - 9

    def test_a_month_with_nothing_published_says_so(self, app, team):
        Settings.objects.create(publish_start_date=date(2026, 10, 12), publish_end_date=date(2026, 10, 20))

        page = app.get(reverse("home"), {"month": "2026-11"}).html

        assert " ".join(page.select_one(".rb-note").text.split()) == (
            "Nothing is published for November 2026 yet. The roster runs to Tue 20 Oct."
        )
        assert page.select_one("a.rb-next") is None

    def test_old_addresses_by_week_open_that_weeks_month(self, app, team):
        page = app.get(reverse("home"), {"from": "2026-11-16"}).html

        assert page.select_one(".rb-monthtitle").text == "November 2026"
