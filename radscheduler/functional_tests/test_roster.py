"""
The roster that opens the app, in a real browser: following a registrar across a month on a wide screen, and
on a phone the list running on month to month. Needs the built bundles: run `pnpm build` first.
"""

import re
from datetime import date, timedelta
from urllib.parse import parse_qsl, urlsplit

import pytest
from django.utils import timezone
from playwright.sync_api import Page, expect

from radscheduler.core.models import Leave, Registrar, Settings, Shift
from radscheduler.functional_tests.conftest import sign_in
from radscheduler.roster.models import LeaveType, ShiftType
from radscheduler.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def add_months(month: date, n: int) -> date:
    index = month.year * 12 + month.month - 1 + n
    return date(index // 12, index % 12 + 1, 1)


@pytest.fixture
def roster(db):
    today = timezone.localdate()
    month = today.replace(day=1)
    people = {
        name: Registrar.objects.create(
            user=UserFactory(username=name.lower(), name=f"{name} Hart", password="password"), start=date(2024, 2, 5)
        )
        for name in ("Rachel", "Ed", "Mo", "Kate", "Sam")
    }
    # Every day of this month and the next: Rachel on a swing, Ed on nights; on the 10th three more away.
    day = month
    while day < add_months(month, 2):
        Shift.objects.create(date=day, type=ShiftType.SWING, registrar=people["Rachel"])
        Shift.objects.create(date=day, type=ShiftType.NIGHT, registrar=people["Ed"])
        day += timedelta(days=1)
    busy = month.replace(day=10)
    Shift.objects.create(date=busy, type=ShiftType.SLEEP, registrar=people["Mo"])
    Leave.objects.create(date=busy, type=LeaveType.ANNUAL, registrar=people["Kate"])
    Leave.objects.create(date=busy, type=LeaveType.EDU, registrar=people["Sam"])
    Settings.objects.create(publish_start_date=month, publish_end_date=add_months(month, 2) - timedelta(days=1))
    return {**people, "month": month, "busy": busy}


def follow_style(page: Page) -> str:
    return page.locator("#rb-follow-css").evaluate("style => style.textContent")


def test_office_staff_follow_one_registrar_across_the_month(page: Page, live_server, real_bundles, roster):
    # A short window: the month can't stretch, so busy days stay folded.
    page.set_viewport_size({"width": 1440, "height": 500})
    page.goto(f"{live_server.url}/?view=dept")
    swings = page.locator(".rb-chips .rb-chip", has_text="Rachel H.")
    busy = page.locator(".rb-day:not(.is-outside)").nth(9)

    # A busy day folds its days off and leave into a line that opens their names.
    fold = busy.locator(".rb-fold-summary")
    expect(fold).to_contain_text("1 off · 2 on leave")
    fold.click()
    expect(busy.locator(".rb-fold-list .rb-chip")).to_have_count(3)
    page.keyboard.press("Escape")
    expect(busy.locator(".rb-fold")).not_to_have_attribute("open", "")

    # Pointing at a chip rings that registrar's chips and dims nothing.
    swings.first.hover()
    page.wait_for_function(
        "r => document.getElementById('rb-follow-css').textContent.includes(r)", arg=f'data-r="{roster["Rachel"].pk}"'
    )
    assert ":not(" not in follow_style(page)
    page.mouse.move(0, 0)
    page.wait_for_function("() => document.getElementById('rb-follow-css').textContent === ''")

    # Clicking follows them, in the address too; their folded leave comes out of its line.
    busy.locator(".rb-fold-list .rb-chip", has_text="Kate H.").evaluate("chip => chip.click()")
    expect(page).to_have_url(f"{live_server.url}/?view=dept&follow={roster['Kate'].pk}")
    expect(busy.locator(".rb-chips .rb-chip", has_text="Kate H.")).to_be_visible()
    expect(page.locator(".rb-following")).to_contain_text("Following Kate Hart:")
    expect(page.locator(".rb-following-count")).to_have_text(f"1 day of leave in {roster['month']:%B}")

    # In a tall window the month fills it, and a day with room draws its days off and leave in full.
    page.get_by_role("link", name="Stop following").click()
    page.set_viewport_size({"width": 1440, "height": 1400})
    expect(busy).to_have_class(re.compile(r"\bis-unfolded\b"))
    expect(busy.locator(".rb-chips .rb-chip", has_text="Kate H.")).to_be_visible()
    expect(busy.locator(".rb-fold-summary")).to_be_hidden()
    busy.locator(".rb-chips .rb-chip", has_text="Kate H.").click()

    # ] steps a month, still following them.
    page.keyboard.press("]")
    next_month = add_months(roster["month"], 1)
    expect(page.locator(".rb-monthtitle")).to_have_text(f"{next_month:%B %Y}")
    query = dict(parse_qsl(urlsplit(page.url).query))
    assert query == {"view": "dept", "follow": str(roster["Kate"].pk), "month": f"{next_month:%Y-%m}"}


def test_a_registrar_on_a_phone_opens_at_today_and_scrolls_on_to_next_month(
    page: Page, live_server, real_bundles, roster
):
    page.set_viewport_size({"width": 390, "height": 844})
    sign_in(page, live_server, "rachel")
    page.goto(f"{live_server.url}/")

    expect(page.get_by_role("heading", level=1)).to_have_text("My roster")
    today = page.locator("#rb-today")
    expect(today.locator(".rb-chip")).to_have_text("Swing day")
    expect(today.locator(".rb-mates")).to_contain_text("Night Ed H.")
    expect(today).to_be_in_viewport()

    # The next month loads under this one, then the published roster ends.
    for _ in range(6):
        page.mouse.wheel(0, 20000)
        page.wait_for_timeout(300)
    expect(page.locator(".rb-monthblock")).to_have_count(2)
    expect(page.locator("#rb-end")).to_contain_text("That's the published roster")


def test_a_registrar_follows_themselves_and_switches_views_with_m(page: Page, live_server, real_bundles, roster):
    page.set_viewport_size({"width": 1440, "height": 900})
    sign_in(page, live_server, "rachel")
    page.goto(f"{live_server.url}/?view=dept")

    page.get_by_role("button", name="Me").click()
    expect(page.get_by_role("button", name="Me")).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".rb-following")).to_contain_text("Following you:")

    page.keyboard.press("m")
    expect(page.get_by_role("heading", level=1)).to_have_text("My roster")
    page.keyboard.press("m")
    expect(page.get_by_role("heading", level=1)).to_have_text("Roster")
