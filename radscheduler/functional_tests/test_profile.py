import os
from datetime import date

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import pytest  # noqa: E402
from playwright.sync_api import Page, expect  # noqa: E402

from radscheduler.core.models import Registrar  # noqa: E402
from radscheduler.roster.models import Contract  # noqa: E402
from radscheduler.users.tests.factories import UserFactory  # noqa: E402

pytestmark = pytest.mark.django_db


def test_registrar_changes_their_contract(page: Page, live_server):
    user = UserFactory(username="erika", password="password")
    registrar = Registrar.objects.create(user=user, start=date(2022, 1, 1))

    page.goto(f"{live_server.url}/accounts/login/")
    page.fill("input[name='login']", "erika")
    page.fill("input[name='password']", "password")
    page.click("button[type='submit']")
    page.goto(f"{live_server.url}{user.get_absolute_url()}")

    contract = page.locator("#contract")
    expect(contract.get_by_label("STONZ")).to_be_checked()
    contract.get_by_label("RDA").check()
    contract.get_by_role("button", name="Save contract").click()

    expect(page.get_by_text("Contract updated")).to_be_visible()
    expect(page.locator("#contract").get_by_label("RDA")).to_be_checked()
    registrar.refresh_from_db()
    assert registrar.contract == Contract.RDA
