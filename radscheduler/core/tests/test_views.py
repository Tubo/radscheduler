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

    def test_inline_form(self, app, juniors_db):
        pass


class TestAccess:
    def ordinary_user_cannot_access_roster_generation(self):
        # Cannot see the button on the menu
        # Cannot access the page
        pass


class TestRosterGeneration:
    def test_generate_empty_schedule(self, app, juniors_db):
        pass


class TestSettingsView:
    """Tests for the settings view Unpoly layer behavior."""

    def test_settings_redirects_to_editor_on_direct_access(self, app, admin_user):
        """When accessing settings URL directly (browser refresh), redirect to editor."""
        app.set_user(admin_user)
        resp = app.get(reverse("settings"))
        assert resp.status_code == 302
        assert resp.location == reverse("editor")

    def test_settings_renders_form_when_accessed_via_unpoly_layer(
        self, app, admin_user
    ):
        """When accessing settings via Unpoly layer, render the settings form."""
        app.set_user(admin_user)
        resp = app.get(reverse("settings"), headers={"X-Up-Mode": "modal"})
        assert resp.status_code == 200
        assert "Publication Settings" in resp.text

    def test_settings_redirects_when_unpoly_mode_is_root(self, app, admin_user):
        """When X-Up-Mode is 'root', treat as direct access and redirect."""
        app.set_user(admin_user)
        resp = app.get(reverse("settings"), headers={"X-Up-Mode": "root"})
        assert resp.status_code == 302
        assert resp.location == reverse("editor")
