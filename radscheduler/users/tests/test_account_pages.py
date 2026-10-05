import pytest
from django.core import mail
from django.urls import reverse

from radscheduler.users.models import User

pytestmark = pytest.mark.django_db


class TestSignOut:
    def test_confirm_page_signs_out(self, app, user: User):
        page = app.get(reverse("account_logout"), user=user)

        assert page.html.select_one(f'a[href="{reverse("home")}"]')  # cancel

        page.forms["logout-form"].submit().follow()

        assert "_auth_user_id" not in app.session


class TestPasswordChange:
    def test_change_password(self, app, user: User):
        user.set_password("old-password-123")
        user.save()
        page = app.get(reverse("account_change_password"), user=user)

        assert page.html.select_one(f'a[href="{user.get_absolute_url()}"]')  # back to profile

        form = page.forms["password-change-form"]
        form["oldpassword"] = "old-password-123"
        form["password1"] = "a-much-better-password-456"
        form["password2"] = "a-much-better-password-456"
        form.submit().follow()

        user.refresh_from_db()
        assert user.check_password("a-much-better-password-456")


class TestPasswordReset:
    def test_request_sends_email(self, app, user: User):
        page = app.get(reverse("account_reset_password"))

        assert page.html.select_one(f'a[href="{reverse("account_login")}"]')  # back to sign in

        form = page.forms["password-reset-form"]
        form["email"] = user.email
        response = form.submit().follow()

        assert len(mail.outbox) == 1
        assert response.html.select_one(f'a[href="{reverse("account_login")}"]')

    def test_bad_key_offers_new_link(self, app):
        response = app.get(reverse("account_reset_password_from_key", kwargs={"uidb36": "x", "key": "bad"}))

        assert response.html.select_one(f'a[href="{reverse("account_reset_password")}"]')


class TestErrorPages:
    def test_404_links_home(self, app, user: User):
        response = app.get("/this-page-does-not-exist/", user=user, status=404)

        assert response.html.select_one("main h1")
        assert response.html.select_one(f'main a[href="{reverse("home")}"]')
