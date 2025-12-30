import json
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
    shift = Shift.objects.create(
        date=date.today(), type=ShiftType.LONG, registrar=registrar
    )

    app.set_user(user)
    response = app.get(
        reverse("editor_by_date", args=[shift.date.strftime("%Y-%m-%d")])
    )

    # Every CSRF input should be populated (no empty string or NOTPROVIDED).
    csrf_inputs = response.html.find_all("input", attrs={"name": "csrfmiddlewaretoken"})
    assert csrf_inputs  # sanity: we actually found CSRF inputs
    for csrf_input in csrf_inputs:
        token = csrf_input.get("value", "")
        assert token and token != "NOTPROVIDED"

    # The delete button sends CSRF via Unpoly headers; ensure it is populated too.
    delete_button = response.html.find(
        "button",
        attrs={"up-href": reverse("delete_shift", args=[shift.id])},
    )
    assert delete_button is not None
    headers_raw = delete_button["up-headers"]
    csrf_header = json.loads(headers_raw).get("X-CSRFToken", "")
    assert csrf_header and csrf_header != "NOTPROVIDED", f"Got: {csrf_header}"
