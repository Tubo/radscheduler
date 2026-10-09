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
    request = request_for(page, "Erika Lee")
    expect(request).to_contain_text("Annual leave · Mon 16 – Tue 17 Dec 2024 · 2 days")
    # The Director sees the verdict first; the roster is there when asked for
    expect(request).to_contain_text("Up to 2 of 2 on leave")
    expect(request.get_by_role("table")).to_have_count(0)
    request.get_by_role("button", name="Show their roster").click()
    # The chief registrar's decision is theirs to make: shown, not offered
    expect(request.get_by_role("button", name="Approve Mon 16 Dec as Chief registrar")).to_have_count(0)

    request.get_by_role("button", name="Approve Erika Lee's annual leave").click()

    wait_for(lambda: decisions(requests["days"], "dot") == [True, True], page)
    assert decisions(requests["days"], "reg") == [None, None]
    expect(request).to_contain_text("You approved all 2 days.")
    expect(request).to_contain_text("Director of Training approved · waiting on the chief registrar.")

    page.get_by_role("button", name="Undo").click()
    wait_for(lambda: decisions(requests["days"], "dot") == [None, None], page)
    expect(request.get_by_role("button", name="Approve Erika Lee's annual leave")).to_be_visible()


def test_the_chief_registrar_decides_day_by_day(page: Page, live_server, real_bundles, requests):
    UserFactory(username="chief", is_staff=True, password="password")
    sign_in(page, live_server, "chief")

    page.goto(f"{live_server.url}/roster/leave/")
    request = request_for(page, "Erika Lee")
    request.get_by_role("button", name="Decline Tue 17 Dec as Chief registrar").click()

    wait_for(lambda: decisions(requests["days"], "reg") == [None, False], page)
    expect(request).to_contain_text("1 day declined, 1 waiting")
    # Only the day still waiting is left for the request's buttons
    expect(request.get_by_role("button", name="Approve the 1 waiting day of Erika Lee's annual leave")).to_be_visible()

    # Who else is away: Erika herself and Will on the Monday
    monday = "2 on leave of 2 on the roster, 1 still waiting on Mon 16 Dec. Show who."
    request.get_by_role("button", name=monday).click()
    expect(request).to_contain_text("Mon 16 Dec: Erika Lee (this request), Will Tane (Edu).")

    # j moves to the request, a approves what is waiting in it
    page.keyboard.press("Escape")
    page.locator("h1").click()
    page.keyboard.press("j")
    page.keyboard.press("a")
    wait_for(lambda: decisions(requests["days"], "reg") == [True, False], page)
    expect(request).to_contain_text("You approved 1 day and declined 1.")
