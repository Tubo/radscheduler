import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_index(django_app):
    resp = django_app.get("/")
    assert resp.status_code == 200, "Should return a 200 status code"


class TestLeaves:
    def test_page(self):
        # Go to leave page
        # Sees a form and a list of leaves
        # fills the form
        # submits the form
        # sees the form and the new leave in the list
        pass

    def test_form(self, app, juniors_db):
        app.set_user(juniors_db[0].user)
        form = app.get(reverse("leave_page")).form
        r = form.submit()
        assert "required" in r


class TestAccess:
    def ordinary_user_cannot_access_roster_generation(self):
        # Cannot see the button on the menu
        # Cannot access the page
        pass


class TestRosterGeneration:
    def test_generate_empty_schedule(self, app, juniors_db):
        pass
