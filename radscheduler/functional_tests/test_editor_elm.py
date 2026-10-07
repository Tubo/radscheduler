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

from radscheduler.core.models import Leave, Registrar, Shift  # noqa: E402
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
    expect(page.get_by_role("heading", name="Roster Editor")).to_be_visible()
    return page


def cell(page: Page, day: str, registrar: Registrar):
    return page.locator(f"#cell-{day}-{registrar.pk}")


def test_grid_shows_shifts_and_leave(editor: Page, roster):
    expect(cell(editor, "2024-12-23", roster["erika"]).get_by_role("button", name="LONG")).to_be_visible()
    expect(cell(editor, "2024-12-24", roster["will"]).get_by_role("button", name=re.compile("ANNUAL"))).to_be_visible()
    expect(editor.locator("thead")).to_contain_text("2024-12-16")
    expect(editor.locator("thead")).to_contain_text("2025-01-05")


def test_add_change_and_delete_a_shift(editor: Page, roster):
    will = roster["will"]
    editor.get_by_role("button", name="Add a shift for will on 2024-12-27").click()
    editor.get_by_role("button", name="Night").click()
    night = cell(editor, "2024-12-27", will).get_by_role("button", name="NIGHT")
    expect(night).to_be_visible()
    added = Shift.objects.get(registrar=will, date=date(2024, 12, 27))
    assert added.type == ShiftType.NIGHT

    night.click()
    editor.get_by_role("button", name="Swing day").click()
    swing = cell(editor, "2024-12-27", will).get_by_role("button", name="SWING")
    expect(swing).to_be_visible()

    swing.click()
    editor.get_by_role("button", name="Extra").click()
    expect(cell(editor, "2024-12-27", will).get_by_text("Extra duty")).to_be_attached()
    added.refresh_from_db()
    assert (added.type, added.extra_duty) == (ShiftType.SWING, True)

    cell(editor, "2024-12-27", will).get_by_role("button", name=re.compile("SWING")).click()
    editor.get_by_role("button", name="Delete").click()
    editor.get_by_role("menu").get_by_role("button", name="Delete").click()
    expect(cell(editor, "2024-12-27", will).get_by_role("button", name=re.compile("SWING"))).to_have_count(0)
    assert not Shift.objects.filter(pk=added.pk).exists()


def test_approve_leave(editor: Page, roster):
    leave_button = cell(editor, "2024-12-24", roster["will"]).get_by_role("button", name=re.compile("ANNUAL"))
    leave_button.click()
    editor.get_by_role("menu").get_by_role("button", name="Approve").first.click()
    expect(editor.get_by_role("menu").get_by_role("button", name="Approve").first).to_have_attribute(
        "aria-pressed", "true"
    )
    roster["leave"].refresh_from_db()
    assert roster["leave"].reg_approved is True

    editor.keyboard.press("Escape")
    expect(editor.get_by_role("menu")).to_have_count(0)


def test_filters_hide_shift_types(editor: Page, roster):
    long_day = cell(editor, "2024-12-23", roster["erika"]).get_by_role("button", name="LONG")
    expect(long_day).to_be_visible()
    editor.get_by_label("Long day").uncheck()
    expect(long_day).to_have_count(0)
    editor.get_by_label("Long day").check()
    expect(long_day).to_be_visible()


def test_week_navigation_and_back_button(editor: Page, live_server):
    editor.get_by_role("button", name="Next week").click()
    expect(editor).to_have_url(re.compile(r"/roster/editor/next/2024-12-30/$"))
    expect(editor.locator("thead")).to_contain_text("2025-01-12")

    editor.go_back()
    expect(editor).to_have_url(re.compile(r"/roster/editor/next/2024-12-23/$"))
    expect(editor.locator("thead")).to_contain_text("2024-12-16")
