"""
The leave requests page, driven in a real browser. Needs the built bundles: run `pnpm build` first.
"""

from datetime import date

import pytest
from django.contrib.auth.models import Group
from playwright.sync_api import Page, expect

from radscheduler.core.models import Leave, Registrar
from radscheduler.core.roles import DIRECTOR_OF_TRAINING
from radscheduler.functional_tests.conftest import sign_in
from radscheduler.roster.models import LeaveType
from radscheduler.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def requests(db):
    erika = Registrar.objects.create(user=UserFactory(username="erika", name="Erika Lee"), start=date(2022, 1, 1))
    will = Registrar.objects.create(user=UserFactory(username="will", name="Will Tane"), start=date(2022, 1, 1))
    days = [Leave.objects.create(date=date(2024, 12, d), type=LeaveType.ANNUAL, registrar=erika) for d in (16, 17)]
    Leave.objects.create(
        date=date(2024, 12, 16), type=LeaveType.EDU, registrar=will, reg_approved=True, dot_approved=True
    )
    return {"erika": erika, "will": will, "days": days}


def request_for(page: Page, name: str):
    return page.get_by_role("article", name=name)


def open_shelf(page: Page, what: str):
    """Open a request in place, on a shelf under its row in the overview."""
    page.get_by_role("button", name=what, exact=True).click()


ERIKAS = "Erika Lee's annual leave, Mon 16 – Tue 17 Dec 2024"


def decisions(days, approver):
    return [getattr(Leave.objects.get(pk=day.pk), f"{approver}_approved") for day in days]


def wait_for(check, page: Page):
    for _ in range(50):
        if check():
            return
        page.wait_for_timeout(100)
    assert check()


def test_the_director_approves_a_whole_request_and_can_undo_it(page: Page, live_server, real_bundles, requests):
    director = UserFactory(username="director", is_staff=True, password="password")
    # A live server empties the database between tests, groups from migrations included
    director.groups.add(Group.objects.get_or_create(name=DIRECTOR_OF_TRAINING)[0])
    sign_in(page, live_server, "director")

    page.goto(f"{live_server.url}/roster/leave/")
    open_shelf(page, ERIKAS)
    request = request_for(page, "Erika Lee")
    expect(request).to_contain_text("Annual leave · Mon 16 – Tue 17 Dec 2024 · 2 days")
    # The verdict, the leave Erika has had this year, and opened from the overview, her roster at once
    expect(request).to_contain_text("Up to 2 of 2 on leave")
    expect(request.get_by_role("table", name="Leave in 2024–25")).to_be_visible()
    expect(request.get_by_role("row", name="Annual")).to_contain_text("+2")
    expect(request.get_by_role("table", name="Roster around Erika Lee's leave")).to_be_visible()
    # The senior registrar's decision is theirs to make: shown, not offered
    expect(request.get_by_role("button", name="Approve Mon 16 Dec as Senior registrar")).to_have_count(0)

    request.get_by_role("button", name="Approve Erika Lee's annual leave").click()

    wait_for(lambda: decisions(requests["days"], "dot") == [True, True], page)
    assert decisions(requests["days"], "reg") == [None, None]
    expect(request).to_contain_text("You approved all 2 days.")
    expect(request).to_contain_text("Director of Training approved · waiting on the senior registrar.")
    # Nothing is left waiting on the Director, so the navbar's count goes
    expect(page.locator(".navbar-count")).to_have_count(0)

    page.get_by_role("button", name="Undo").click()
    wait_for(lambda: decisions(requests["days"], "dot") == [None, None], page)
    expect(request.get_by_role("button", name="Approve Erika Lee's annual leave")).to_be_visible()


def test_the_senior_registrar_decides_day_by_day(page: Page, live_server, real_bundles, requests):
    UserFactory(username="chief", is_staff=True, password="password")
    sign_in(page, live_server, "chief")

    page.goto(f"{live_server.url}/roster/leave/")
    open_shelf(page, ERIKAS)
    request = request_for(page, "Erika Lee")
    request.get_by_role("button", name="Decline Tue 17 Dec as Senior registrar").click()

    wait_for(lambda: decisions(requests["days"], "reg") == [None, False], page)
    expect(request).to_contain_text("1 day declined, 1 waiting")
    # A day's decision can be undone too
    expect(page.get_by_text("Declined Tue 17 Dec of Erika Lee's annual leave as senior registrar.")).to_be_visible()
    # Only the day still waiting is left for the request's buttons
    expect(request.get_by_role("button", name="Approve the 1 waiting day of Erika Lee's annual leave")).to_be_visible()

    # Who else is away: Erika herself and Will on the Monday
    monday = "2 on leave of 2 on the roster, 1 still waiting on Mon 16 Dec. Show who."
    request.get_by_role("button", name=monday).click()
    names = request.locator(".lr-daynames")
    expect(names).to_contain_text("Mon 16 Dec")
    expect(names.locator(".lr-daygroup", has_text="This request")).to_contain_text("Erika Lee")
    expect(names.locator(".lr-daygroup", has_text="Approved")).to_contain_text("Will Tane (Edu)")

    # In approval mode, j moves to the request, and with focus in it a approves what is waiting there
    page.get_by_role("button", name="Review it").click()
    request = request_for(page, "Erika Lee")
    expect(request).to_be_visible()
    page.locator("h1").click()
    page.keyboard.press("j")
    expect(request).to_be_focused()
    page.keyboard.press("a")
    wait_for(lambda: decisions(requests["days"], "reg") == [True, False], page)
    expect(request).to_contain_text("You approved 1 day and declined 1.")


def test_the_overview_filters_and_approves_requests_together(page: Page, live_server, real_bundles, requests):
    # A roster of seven, so two away on the Monday isn't a busy day
    for n in range(5):
        Registrar.objects.create(user=UserFactory(username=f"reg{n}"), start=date(2022, 1, 1))
    UserFactory(username="chief", is_staff=True, password="password")
    sign_in(page, live_server, "chief")

    page.goto(f"{live_server.url}/roster/leave/")
    table = page.get_by_role("table")
    # What waits on the senior registrar: Erika's leave, not Will's, which both have approved
    expect(table.get_by_role("button", name=ERIKAS, exact=True)).to_be_visible()
    expect(table).not_to_contain_text("Will Tane")

    page.get_by_role("button", name="Any status").click()
    page.get_by_role("button", name="Education", exact=True).click()
    expect(page.get_by_text("1 request", exact=True)).to_be_visible()
    expect(table).to_contain_text("Will Tane")
    # The filters are kept in the address
    expect(page).to_have_url(f"{live_server.url}/roster/leave/?status=any&types=EDU")

    page.get_by_role("button", name="Clear filters").click()
    # Nobody is rostered yet, so nothing stands against Erika's leave
    page.get_by_role("checkbox", name=f"Tick {ERIKAS} to approve").check()
    page.get_by_role("button", name="Approve 1 request").click()
    wait_for(lambda: decisions(requests["days"], "reg") == [True, True], page)
    expect(page.get_by_text("Approved 1 request (2 days) as senior registrar.")).to_be_visible()

    page.get_by_role("button", name="Undo").click()
    wait_for(lambda: decisions(requests["days"], "reg") == [None, None], page)
