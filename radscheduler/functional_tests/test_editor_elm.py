"""
The Elm roster editor, driven in a real browser. Needs the built bundles: run `pnpm build` first.
"""

import json
import os
import re
import socket
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
    elm = django_settings.BASE_DIR / "radscheduler/static/elm-build/editor.js"
    if not elm.exists() or not stats.exists() or "editor_elm" not in json.loads(stats.read_text()).get("chunks", {}):
        pytest.fail("The Elm editor isn't built; run `pnpm build` first.")
    # A build from `elm-watch hot` loads its code from elm-watch, so it only works while that runs.
    hot = re.search(r'webSocketPort":(\d+)', elm.read_text())
    if hot and socket.socket().connect_ex(("localhost", int(hot[1]))) != 0:
        pytest.fail("The Elm editor build is from `elm-watch hot`, which isn't running: run `pnpm build` first.")
    # django-webpack-loader reads its settings once, at import.
    real = {**webpack_config.user_config["DEFAULT"], "LOADER_CLASS": "webpack_loader.loaders.WebpackLoader"}
    monkeypatch.setitem(webpack_config.user_config, "DEFAULT", real)
    get_loader.cache_clear()
    yield
    get_loader.cache_clear()


@pytest.fixture
def roster(db):
    erika = Registrar.objects.create(user=UserFactory(username="erika", name="Erika Lee"), start=date(2022, 1, 1))
    will = Registrar.objects.create(user=UserFactory(username="will", name="Will Tane"), start=date(2022, 1, 1))
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

    # The editor keeps asking in the background (the rule checks after each change, a publish preview once
    # typing pauses). Let those answers arrive before the test's database is emptied, or the two deadlock.
    pending = set()
    page.on("request", lambda request: pending.add(request))
    page.on("requestfinished", lambda request: pending.discard(request))
    page.on("requestfailed", lambda request: pending.discard(request))

    page.goto(f"{live_server.url}/roster/editor/next/2024-12-23/")
    expect(page.get_by_role("grid")).to_be_visible()
    yield page

    page.wait_for_timeout(350)  # long enough for a debounced request to have started
    for _ in range(100):
        if not pending:
            break
        page.wait_for_timeout(50)


def cell(page: Page, day: str, registrar: Registrar):
    return page.locator(f"#cell-{day}-{registrar.pk}")


def menu(page: Page):
    return page.locator(".re-popover")


def test_grid_shows_shifts_leave_and_cover(editor: Page, roster):
    expect(cell(editor, "2024-12-23", roster["erika"])).to_contain_text("Long")
    expect(cell(editor, "2024-12-24", roster["will"])).to_contain_text("Annual")
    expect(cell(editor, "2024-12-24", roster["will"])).to_have_attribute(
        "aria-label", "Will Tane, Tue 24 Dec: Annual leave (all day), waiting for approval"
    )
    expect(editor.get_by_role("rowheader", name=re.compile("Erika Lee"))).to_be_visible()
    expect(editor.locator("thead")).to_contain_text("16 Dec")
    expect(editor.locator("thead")).to_contain_text("Christmas Day")


def test_cover_shows_only_what_is_missing(editor: Page, roster):
    Shift.objects.create(date=date(2024, 12, 24), type=ShiftType.SWING, registrar=roster["erika"])
    Shift.objects.create(date=date(2024, 12, 24), type=ShiftType.NIGHT, registrar=roster["will"])
    Shift.objects.create(date=date(2024, 12, 25), type=ShiftType.LONG, registrar=roster["will"])
    Shift.objects.create(date=date(2024, 12, 29), type=ShiftType.SWING)  # posted, not given to anyone
    editor.reload()

    def cover(day):
        return editor.locator(f".re-cover td:nth-child({(date(2024, 12, day) - date(2024, 12, 16)).days + 3})")

    # A weekday needs a swing day: Mon 23 Dec's long day doesn't count
    expect(cover(23).get_by_role("button", name="Mon 23 Dec needs a swing day: choose who")).to_be_visible()
    expect(cover(24)).to_contain_text("Covered: swing day, night")
    expect(cover(24).get_by_role("button")).to_have_count(0)
    # Christmas is a holiday, covered like a weekend: a long day will do, but it still needs a night
    expect(cover(25).get_by_role("button", name=re.compile("needs a swing day or long day"))).to_have_count(0)
    expect(cover(25).get_by_role("button", name="Wed 25 Dec needs a night: choose who")).to_be_visible()
    expect(cover(29)).to_contain_text("Swing day posted, not yet given to anyone")


def test_fill_a_cover_gap_from_the_least_loaded(editor: Page, roster):
    erika, will = roster["erika"], roster["will"]
    Shift.objects.create(date=date(2024, 11, 5), type=ShiftType.NIGHT, registrar=erika)
    editor.reload()

    editor.get_by_role("button", name="Thu 19 Dec needs a night: choose who").click()
    candidates = menu(editor).locator(".re-candidates li")
    expect(candidates.first).to_contain_text("Will Tane")  # no load yet; Erika has a night
    menu(editor).get_by_role("button", name="Give Will Tane the night").first.click()

    expect(cell(editor, "2024-12-19", will)).to_contain_text("Night")
    expect(cell(editor, "2024-12-19", will)).to_be_focused()
    assert Shift.objects.get(registrar=will, date=date(2024, 12, 19)).type == ShiftType.NIGHT


def test_rule_breaks_show_with_their_clause(editor: Page, roster):
    erika = roster["erika"]
    day = cell(editor, "2024-12-23", erika)  # already a long day
    cell(editor, "2024-12-24", erika).focus()
    editor.keyboard.press("l")

    nextday = cell(editor, "2024-12-24", erika)
    expect(nextday).to_have_class(re.compile("has-problem"))
    expect(day).to_have_class(re.compile("has-problem"))
    expect(nextday).to_have_attribute("aria-label", re.compile("Breaks 1 rule"))

    nextday.click()
    expect(menu(editor)).to_contain_text("Department rule")
    expect(menu(editor)).to_contain_text("Long days on Mon 23 Dec and Tue 24 Dec back to back.")
    editor.keyboard.press("Escape")

    editor.locator("#problems-button").click()
    expect(menu(editor).get_by_role("button", name=re.compile("Long days on Mon 23 Dec"))).to_be_visible()


def test_undo_an_add_and_a_delete(editor: Page, roster):
    erika = roster["erika"]
    day = cell(editor, "2024-12-27", erika)
    day.focus()
    editor.keyboard.press("n")
    expect(editor.locator(".re-toast")).to_contain_text("Added a night for Erika Lee on Fri 27 Dec")
    editor.keyboard.press("Control+z")
    expect(day).not_to_contain_text("Night")
    assert not Shift.objects.filter(registrar=erika, date=date(2024, 12, 27)).exists()

    long_day = cell(editor, "2024-12-23", erika)
    long_day.focus()
    editor.keyboard.press("Delete")
    editor.get_by_role("button", name="Delete shift").click()
    expect(long_day).not_to_contain_text("Long")
    editor.locator(".re-toast").get_by_role("button", name="Undo").click()
    expect(long_day).to_contain_text("Long")
    assert Shift.objects.get(registrar=erika, date=date(2024, 12, 23)).type == ShiftType.LONG


def test_a_shift_on_leave_asks_first(editor: Page, roster):
    will = roster["will"]
    day = cell(editor, "2024-12-24", will)
    day.focus()
    editor.keyboard.press("n")
    expect(menu(editor)).to_contain_text(
        "Will Tane is on annual leave (all day), waiting for approval. Add a night anyway?"
    )
    assert not Shift.objects.filter(registrar=will, date=date(2024, 12, 24)).exists()

    menu(editor).get_by_role("button", name="Add night anyway").click()
    expect(day).to_contain_text("N")
    assert Shift.objects.get(registrar=will, date=date(2024, 12, 24)).type == ShiftType.NIGHT


def test_add_change_and_delete_a_shift_from_the_cell_menu(editor: Page, roster):
    will = roster["will"]
    day = cell(editor, "2024-12-27", will)
    day.click()
    expect(menu(editor).get_by_role("heading", level=2)).to_have_text("Will Tane · Fri 27 Dec")
    menu(editor).get_by_role("button", name="Add Night").click()
    expect(day).to_contain_text("Night")
    added = Shift.objects.get(registrar=will, date=date(2024, 12, 27))
    assert added.type == ShiftType.NIGHT
    expect(day).to_be_focused()

    day.click()
    menu(editor).get_by_role("button", name="Change to Swing day").click()
    expect(day).to_contain_text("Swing")

    day.click()
    menu(editor).get_by_role("switch", name="Extra duty").click()
    expect(day).to_have_attribute("aria-label", re.compile(r"Swing day \(extra duty\)"))
    added.refresh_from_db()
    assert (added.type, added.extra_duty) == (ShiftType.SWING, True)

    day.click()
    menu(editor).get_by_role("button", name="Delete…").click()
    expect(menu(editor)).to_contain_text("Delete Will Tane's swing day on Fri 27 Dec?")
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
    approvals = menu(editor).get_by_role("group", name="Chief registrar")
    approvals.get_by_text("Approve").click()
    expect(approvals.get_by_role("radio", name="Approve")).to_be_checked()
    expect(approvals).to_contain_text("by ")
    expect(menu(editor)).to_contain_text("Chief registrar approved · waiting on the Director of Training.")
    roster["leave"].refresh_from_db()
    assert roster["leave"].reg_approved is True
    assert roster["leave"].reg_decided_by.username == "chief"

    editor.keyboard.press("Escape")
    expect(menu(editor)).to_have_count(0)
    expect(day).to_be_focused()


def test_approve_a_whole_leave_request(editor: Page, roster):
    will = roster["will"]
    roster["leave"].delete()
    days = [Leave.objects.create(date=date(2024, 12, d), type=LeaveType.ANNUAL, registrar=will) for d in (19, 20, 23)]
    editor.reload()

    cell(editor, "2024-12-20", will).click()
    expect(menu(editor)).to_contain_text("Apply to the whole request: 3 days, Thu 19 – Mon 23 Dec")
    menu(editor).get_by_role("group", name="Director of Training").get_by_text("Approve").click()
    expect(cell(editor, "2024-12-23", will)).to_have_attribute("aria-label", re.compile("approved by one"))
    assert all(Leave.objects.get(pk=leave.pk).dot_approved for leave in days)


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
    expect(dialog.get_by_role("heading", name="Publish the roster")).to_be_focused()

    dialog.get_by_label("From").fill("2024-12-31")
    dialog.get_by_label("To").fill("2024-12-01")
    expect(dialog.get_by_text("The start must be on or before the end.")).to_be_visible()
    expect(dialog.get_by_role("button", name="Publish")).to_be_disabled()

    # A year still being typed asks nothing of the server.
    dialog.get_by_label("From").fill("0002-12-01")
    expect(dialog.get_by_text("Check the years: the dates need to be from 2000 on.")).to_be_visible()
    expect(dialog.get_by_role("button", name="Publish")).to_be_disabled()

    dialog.get_by_label("From").fill("2024-12-01")
    dialog.get_by_label("To").fill("2024-12-31")
    expect(dialog.get_by_text("Registrars will start seeing 1 shift and 1 leave.")).to_be_visible()
    dialog.get_by_role("button", name="Publish").click()

    expect(dialog).to_have_count(0)
    expect(editor.get_by_text("Published to Tue 31 Dec")).to_be_visible()
    settings = Settings.objects.get()
    assert (settings.publish_start_date, settings.publish_end_date) == (date(2024, 12, 1), date(2024, 12, 31))


def test_select_a_block_and_set_it_in_one_go(editor: Page, roster):
    erika = roster["erika"]
    cell(editor, "2024-12-16", erika).focus()
    editor.keyboard.press("Shift+ArrowRight")
    editor.keyboard.press("Shift+ArrowRight")
    editor.keyboard.press("Shift+ArrowRight")
    expect(editor.locator(".re-selection")).to_contain_text("4 cells selected")
    expect(cell(editor, "2024-12-18", erika)).to_have_attribute("aria-selected", "true")

    editor.keyboard.press("n")
    expect(editor.locator(".re-toast")).to_contain_text("Set 4 cells to night")
    for day in ("16", "17", "18", "19"):
        expect(cell(editor, f"2024-12-{day}", erika)).to_contain_text("Night")

    editor.keyboard.press("Control+z")
    for day in ("16", "17", "18", "19"):
        expect(cell(editor, f"2024-12-{day}", erika)).not_to_contain_text("Night")
    assert not Shift.objects.filter(registrar=erika, date__range=[date(2024, 12, 16), date(2024, 12, 19)]).exists()


def test_copy_a_pattern_to_another_registrar(editor: Page, roster):
    erika, will = roster["erika"], roster["will"]
    Shift.objects.create(date=date(2024, 12, 16), type=ShiftType.NIGHT, registrar=erika)
    Shift.objects.create(date=date(2024, 12, 17), type=ShiftType.NIGHT, registrar=erika)
    Shift.objects.create(date=date(2024, 12, 18), type=ShiftType.RDO, registrar=erika)
    editor.reload()

    cell(editor, "2024-12-16", erika).focus()
    editor.keyboard.press("Shift+End")
    editor.keyboard.press("Control+c")
    expect(editor.locator(".re-toast")).to_contain_text("Copied 21 days")

    cell(editor, "2024-12-30", will).click(modifiers=["Shift"])  # moves the cursor without opening the menu
    editor.keyboard.press("Escape")
    cell(editor, "2024-12-30", will).focus()
    editor.keyboard.press("Control+v")
    expect(editor.locator(".re-toast")).to_contain_text("Pasted 3 shifts")
    expect(cell(editor, "2024-12-31", will)).to_contain_text("Night")
    expect(cell(editor, "2025-01-01", will)).to_contain_text("RDO")


def test_delete_a_selected_block(editor: Page, roster):
    erika = roster["erika"]
    for day in (16, 17):
        Shift.objects.create(date=date(2024, 12, day), type=ShiftType.NIGHT, registrar=erika)
    editor.reload()

    cell(editor, "2024-12-16", erika).focus()
    editor.keyboard.press("Shift+ArrowRight")
    editor.keyboard.press("Delete")
    expect(menu(editor)).to_contain_text("Delete 2 shifts in the selected cells?")
    menu(editor).get_by_role("button", name="Delete 2 shifts").click()
    expect(cell(editor, "2024-12-17", erika)).not_to_contain_text("Night")
    assert not Shift.objects.filter(registrar=erika).exclude(date=date(2024, 12, 23)).exists()


def test_step_through_problems(editor: Page, roster):
    erika = roster["erika"]
    Shift.objects.create(date=date(2024, 12, 24), type=ShiftType.LONG, registrar=erika)
    editor.reload()

    # Problems go day by day, each day's cover gaps before the rows.
    cell(editor, "2024-12-22", erika).focus()
    editor.keyboard.press("]")
    expect(editor.locator("#cover-2024-12-23")).to_be_focused()
    editor.keyboard.press("]")
    expect(cell(editor, "2024-12-23", erika)).to_be_focused()  # back-to-back long days, marked from the first
    editor.keyboard.press("[")
    expect(editor.locator("#cover-2024-12-23")).to_be_focused()


def test_drag_to_scroll(editor: Page, roster):
    scroller = editor.locator(".re-scroll")
    start = cell(editor, "2024-12-20", roster["erika"]).bounding_box()
    x, y = start["x"] + start["width"] / 2, start["y"] + start["height"] / 2

    editor.mouse.move(x, y)
    editor.mouse.down()
    editor.mouse.move(x - 150, y, steps=5)
    editor.mouse.move(x - 300, y, steps=5)
    editor.mouse.up()

    assert scroller.evaluate("el => el.scrollLeft") == pytest.approx(300, abs=2)
    expect(menu(editor)).to_have_count(0)  # the drag's click doesn't open the day

    cell(editor, "2024-12-23", roster["erika"]).click()  # a plain click still does
    expect(menu(editor)).to_be_visible()
