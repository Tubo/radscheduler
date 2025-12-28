import os
import re
from datetime import date

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import pytest
from playwright.sync_api import Page, expect

from radscheduler.core.models import Registrar, Shift
from radscheduler.roster.models import ShiftType
from radscheduler.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user(db):
    return UserFactory(
        username="admin", is_staff=True, is_superuser=True, password="password"
    )


@pytest.fixture
def registrar(admin_user):
    return Registrar.objects.create(user=admin_user, start=date(2020, 1, 1))


def test_editor_menu_bar(page: Page, live_server, admin_user, registrar):
    # Create a shift for today
    today = date.today()
    Shift.objects.create(date=today, type=ShiftType.LONG, registrar=registrar)

    # Login
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill("input[name='login']", "admin")
    page.fill("input[name='password']", "password")
    page.click("button[type='submit']")

    # Navigate to editor for today
    page.goto(f"{live_server.url}/roster/editor/{today.strftime('%Y-%m-%d')}/")

    # 1. Check tooltips direction
    prev_btn = page.locator("a[title='Previous week']")
    expect(prev_btn).to_have_attribute("data-bs-placement", "top")

    next_btn = page.locator("a[title='Next week']")
    expect(next_btn).to_have_attribute("data-bs-placement", "top")

    # 2. Check button group width
    # The filter container should have flex-grow-1 to take up available space
    # It is the second child of #menu-bar
    filter_container = page.locator("#menu-bar > div").nth(1)
    expect(filter_container).to_have_class(re.compile(r"flex-grow-1"))

    # 3. Check filtering persistence and functionality
    # Find the "Long day" checkbox (value="LONG")
    long_day_input = page.locator("input[name='shift_types'][value='LONG']")
    long_day_label = page.locator("label", has_text="Long day").first

    # Ensure it is checked initially
    expect(long_day_input).to_be_checked()

    # Verify the shift is visible in the table
    # The shift cell should contain the text "LONG" (the value)
    # Let's look for the button with the shift type
    cell_id = f"cell-{today.strftime('%Y-%m-%d')}-{registrar.id}"
    shift_button = page.locator(f"#{cell_id} button.dropdown-toggle:has-text('LONG')")
    expect(shift_button).to_be_visible()

    # Click to uncheck "Long day" filter
    long_day_label.click()

    # Wait for the form submission and response (Unpoly)
    page.wait_for_load_state("networkidle")

    # Verify input is unchecked
    expect(long_day_input).not_to_be_checked()

    # Verify the shift is NO LONGER visible
    expect(shift_button).not_to_be_visible()
