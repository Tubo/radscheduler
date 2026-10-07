from datetime import date

import pytest
from django.urls import reverse

from radscheduler.core.models import Registrar
from radscheduler.roster.models import Contract
from radscheduler.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def registrar(user: User) -> Registrar:
    return Registrar.objects.create(user=user, start=date(2022, 1, 1))


class TestContract:
    def test_registrar_sees_their_contract(self, app, user: User, registrar):
        page = app.get(user.get_absolute_url(), user=user)

        form = page.forms["contract-form"]
        assert form["contract"].value == Contract.STONZ
        assert [value for value, *_ in form["contract"].options] == [Contract.STONZ, Contract.RDA]

    def test_change_contract(self, app, user: User, registrar):
        page = app.get(user.get_absolute_url(), user=user)
        form = page.forms["contract-form"]
        form["contract"] = Contract.RDA

        page = form.submit().follow()

        registrar.refresh_from_db()
        assert registrar.contract == Contract.RDA
        assert "Contract updated" in page.text
        assert page.forms["contract-form"]["contract"].value == Contract.RDA

    def test_invalid_contract_shows_error(self, app, user: User, registrar):
        page = app.post(reverse("users:contract"), {"contract": "ASMS"}, user=user)

        assert page.status_code == 200
        assert "Select a valid choice" in page.text
        registrar.refresh_from_db()
        assert registrar.contract == Contract.STONZ

    def test_user_without_registrar_has_no_contract(self, app, user: User):
        page = app.get(user.get_absolute_url(), user=user)

        assert "contract-form" not in page.forms
        app.post(reverse("users:contract"), {"contract": Contract.RDA}, user=user, status=404)

    def test_contract_is_not_shown_on_someone_elses_profile(self, app, user: User, registrar, django_user_model):
        other = django_user_model.objects.create_user(username="other", password="password")

        page = app.get(user.get_absolute_url(), user=other)

        assert "contract-form" not in page.forms

    def test_get_redirects_to_profile(self, app, user: User, registrar):
        page = app.get(reverse("users:contract"), user=user)

        assert page.status_code == 302
        assert page.location == user.get_absolute_url()
