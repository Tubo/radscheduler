"""
The Elm roster editor, driven in a real browser. Needs the built bundles: run `pnpm build` first.
"""

import json
import os
import re
from datetime import date

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import pytest  # noqa: E402
from django.conf import settings as django_settings  # noqa: E402
from playwright.sync_api import Page, expect  # noqa: E402
from webpack_loader import config as webpack_config  # noqa: E402
from webpack_loader.utils import get_loader  # noqa: E402

from radscheduler.core.models import Leave, Registrar, Settings, Shift  # noqa: E402
from radscheduler.roster.models import LeaveType, ShiftType  # noqa: E402
from radscheduler.users.tests.factories import UserFactory  # noqa: E402

pytestmark = pytest.mark.django_db


@pytest.fixture
def real_bundles(monkeypatch):
    """Serve the built bundles instead of the test settings' fake ones."""
    stats = django_settings.BASE_DIR / "webpack-stats.json"
    if not stats.exists() or "editor_elm" not in json.loads(stats.read_text()).get("chunks", {}):
        pytest.fail("The Elm editor bundle is missing; run `pnpm build` first.")
    # django-webpack-loader reads its settings once, at import.
    real = {**webpack_config.user_config["DEFAULT"], "LOADER_CLASS": "webpack_loader.loaders.WebpackLoader"}
    monkeypatch.setitem(webpack_config.user_config, "DEFAULT", real)
    get_loader.cache_clear()
    yield
    get_loader.cache_clear()


@pytest.fixture
def roster(db):
    erika = Registrar.objects.create(user=UserFactory(username="erika"), start=date(2022, 1, 1))
    will = Registrar.objects.create(user=UserFactory(username="will"), start=date(2022, 1, 1))
    shift = Shift.objects.create(date=date(2024, 12, 23), type=ShiftType.LONG, registrar=erika)
    leave = Leave.objects.create(date=date(2024, 12, 24), type=LeaveType.ANNUAL, registrar=will)
    return {"erika": erika, "will": will, "shift": shift, "leave": leave}


@pytest.fixture
def editor(page: Page, live_server, real_bundles, roster):
    UserFactory(username="chief", is_staff=True, password="password")
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill("input[name='login']", "chief")
    page.fill("input[name='password']", "password")
    page.click("button[type='submit']")
    page.goto(f"{live_server.url}/roster/editor/next/2024-12-23/")
    expect(page.get_by_role("grid")).to_be_visible()
    return page


def cell(page: Page, day: str, registrar: Registrar):
    return page.locator(f"#cell-{day}-{registrar.pk}")


def menu(page: Page):
    return page.locator(".re-popover")


def test_grid_shows_shifts_leave_and_cover(editor: Page, roster):
    expect(cell(editor, "2024-12-23", roster["erika"])).to_contain_text("Long")
    expect(cell(editor, "2024-12-24", roster["will"])).to_contain_text("Annual")
    expect(cell(editor, "2024-12-24", roster["will"])).to_contain_text("waiting for approval")
    expect(editor.locator("thead")).to_contain_text("16 Dec")
    expect(editor.locator("thead")).to_contain_text("Christmas Day")
    # Only Mon 23 Dec has its long day; nobody is on nights
    expect(editor.locator(".re-coverchip.is-ok")).to_have_count(1)


def test_add_change_and_delete_a_shift_from_the_cell_menu(editor: Page, roster):
    will = roster["will"]
    day = cell(editor, "2024-12-27", will)
    day.click()
    expect(menu(editor).get_by_role("heading", level=2)).to_have_text("will · Fri 27 Dec")
    menu(editor).get_by_role("button", name="Add Night").click()
    expect(day).to_contain_text("Night")
    added = Shift.objects.get(registrar=will, date=date(2024, 12, 27))
    assert added.type == ShiftType.NIGHT
    expect(day).to_be_focused()

    day.click()
    menu(editor).get_by_role("button", name="Change to Swing day").click()
    expect(day).to_contain_text("Swing")

    day.click()
    menu(editor).get_by_role("button", name="Mark as extra duty").click()
    expect(day).to_contain_text("extra duty")
    added.refresh_from_db()
    assert (added.type, added.extra_duty) == (ShiftType.SWING, True)

    day.click()
    menu(editor).get_by_role("button", name="Delete…").click()
    expect(menu(editor)).to_contain_text("Delete will's swing day on Fri 27 Dec?")
    menu(editor).get_by_role("button", name="Delete shift").click()
    expect(day).not_to_contain_text("Swing")
    assert not Shift.objects.filter(pk=added.pk).exists()


def test_keyboard_moves_and_assigns(editor: Page, roster):
    erika = roster["erika"]
    start = cell(editor, "2024-12-23", erika)
    start.focus()
    editor.keyboard.press("ArrowRight")
    expect(cell(editor, "2024-12-24", erika)).to_be_focused()

    editor.keyboard.press("n")
    expect(cell(editor, "2024-12-24", erika)).to_contain_text("Night")
    assert Shift.objects.get(registrar=erika, date=date(2024, 12, 24)).type == ShiftType.NIGHT

    editor.keyboard.press("h")
    expect(cell(editor, "2024-12-24", erika)).to_contain_text("Help")

    editor.keyboard.press("Delete")
    editor.get_by_role("button", name="Delete shift").click()
    expect(cell(editor, "2024-12-24", erika)).not_to_contain_text("Help")
    expect(cell(editor, "2024-12-24", erika)).to_be_focused()


def test_approve_leave_and_escape_back_to_the_day(editor: Page, roster):
    day = cell(editor, "2024-12-24", roster["will"])
    day.click()
    approvals = menu(editor).get_by_role("group", name="Chief registrar approval")
    approvals.get_by_role("button", name="Approve").click()
    expect(approvals.get_by_role("button", name="Approve")).to_have_attribute("aria-pressed", "true")
    roster["leave"].refresh_from_db()
    assert roster["leave"].reg_approved is True

    editor.keyboard.press("Escape")
    expect(menu(editor)).to_have_count(0)
    expect(day).to_be_focused()


def test_filters_hide_shift_types(editor: Page, roster):
    day = cell(editor, "2024-12-23", roster["erika"])
    expect(day).to_contain_text("Long")
    editor.get_by_role("button", name="Filter").click()
    menu(editor).get_by_label("Long day").uncheck()
    expect(day).not_to_contain_text("Long")
    expect(editor.get_by_text("Hiding 1 shift")).to_be_visible()
    editor.keyboard.press("Escape")
    editor.get_by_role("button", name="Show all").click()
    expect(day).to_contain_text("Long")


def test_week_navigation_and_back_button(editor: Page):
    editor.get_by_role("button", name="Next week").click()
    expect(editor).to_have_url(re.compile(r"/roster/editor/next/2024-12-30/$"))
    expect(editor.locator("thead")).to_contain_text("12 Jan")

    editor.go_back()
    expect(editor).to_have_url(re.compile(r"/roster/editor/next/2024-12-23/$"))
    expect(editor.locator("thead")).to_contain_text("16 Dec")


def test_publish_with_a_preview(editor: Page, roster):
    editor.get_by_role("button", name="Publish…").click()
    dialog = editor.get_by_role("dialog", name="Publish the roster")
    expect(dialog.get_by_label("From")).to_be_focused()

    dialog.get_by_label("From").fill("2024-12-31")
    dialog.get_by_label("To").fill("2024-12-01")
    expect(dialog.get_by_text("The start must be on or before the end.")).to_be_visible()
    expect(dialog.get_by_role("button", name="Publish")).to_be_disabled()

    dialog.get_by_label("From").fill("2024-12-01")
    dialog.get_by_label("To").fill("2024-12-31")
    expect(dialog.get_by_text("Registrars will start seeing 1 shift and 1 leave.")).to_be_visible()
    dialog.get_by_role("button", name="Publish").click()

    expect(dialog).to_have_count(0)
    expect(editor.get_by_text("Published to Tue 31 Dec")).to_be_visible()
    settings = Settings.objects.get()
    assert (settings.publish_start_date, settings.publish_end_date) == (date(2024, 12, 1), date(2024, 12, 31))
