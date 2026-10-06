from datetime import date

import pytest
from django.urls import reverse

from radscheduler.core.models import Registrar, Shift
from radscheduler.roster.models import ShiftType
from radscheduler.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_editor_shift_buttons_render_csrf_tokens(app):
    """
    Regression test: ensure CSRF tokens make it through the editor templates.
    The bug was that `{% include ... only %}` stripped the csrf context, leaving
    empty tokens in both forms and Unpoly headers.
    """

    user = UserFactory(is_staff=True, is_superuser=True, password="password")
    registrar = Registrar.objects.create(user=user, start=date(2022, 1, 1))
    shift = Shift.objects.create(date=date.today(), type=ShiftType.LONG, registrar=registrar)

    app.set_user(user)
    response = app.get(reverse("editor_by_date", args=[shift.date.strftime("%Y-%m-%d")]))

    # Every CSRF input should be populated (no empty string or NOTPROVIDED).
    csrf_inputs = response.html.find_all("input", attrs={"name": "csrfmiddlewaretoken"})
    assert csrf_inputs  # sanity: we actually found CSRF inputs
    for csrf_input in csrf_inputs:
        token = csrf_input.get("value", "")
        assert token and token != "NOTPROVIDED"

    # The delete button posts through Unpoly, which sends the token from the csrf-token meta tag.
    delete_button = response.html.find(
        "button",
        attrs={"up-href": reverse("delete_shift", args=[shift.id])},
    )
    assert delete_button is not None
    csrf_meta = response.html.find("meta", attrs={"name": "csrf-token"})["content"]
    assert csrf_meta and csrf_meta != "NOTPROVIDED", f"Got: {csrf_meta}"
