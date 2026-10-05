import pytest
from allauth.account.models import EmailAddress
from django.urls import reverse

from radscheduler.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def second_email(user: User) -> EmailAddress:
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
    return EmailAddress.objects.create(user=user, email="second@example.com", primary=False, verified=False)


class TestEmailPage:
    def test_each_address_has_its_own_actions(self, app, user: User, second_email):
        page = app.get(reverse("account_email"), user=user)

        assert user.email in page.text
        assert f"email-actions-{second_email.email}" in page.forms
        # Only a non-primary address can be made primary.
        assert "action_primary" in page.forms[f"email-actions-{second_email.email}"].fields
        assert "action_primary" not in page.forms[f"email-actions-{user.email}"].fields

    def test_single_address_offers_no_make_primary(self, app, user: User):
        # allauth syncs User.email into a non-primary address; with nothing to
        # choose between, "Make primary" would only be noise.
        page = app.get(reverse("account_email"), user=user)

        assert "action_primary" not in page.forms[f"email-actions-{user.email}"].fields

    def test_make_primary(self, app, user: User, second_email):
        second_email.verified = True
        second_email.save()
        page = app.get(reverse("account_email"), user=user)

        page.forms[f"email-actions-{second_email.email}"].submit("action_primary").follow()

        second_email.refresh_from_db()
        assert second_email.primary

    def test_remove(self, app, user: User, second_email):
        page = app.get(reverse("account_email"), user=user)

        page.forms[f"email-actions-{second_email.email}"].submit("action_remove").follow()

        assert not EmailAddress.objects.filter(pk=second_email.pk).exists()

    def test_add(self, app, user: User):
        page = app.get(reverse("account_email"), user=user)
        form = page.forms["add-email-form"]
        form["email"] = "new@example.com"

        form.submit("action_add").follow()

        assert EmailAddress.objects.filter(user=user, email="new@example.com").exists()

    def test_add_invalid_shows_error(self, app, user: User):
        page = app.get(reverse("account_email"), user=user)
        form = page.forms["add-email-form"]
        form["email"] = user.email  # already on the account

        response = form.submit("action_add")

        assert response.status_code == 200
        assert response.html.select(".invalid-feedback")

    def test_unverified_address_offers_verification(self, app, user: User, second_email):
        # allauth only lets a verified address become primary, so the way to verify must stay visible.
        page = app.get(reverse("account_email"), user=user)

        assert "Unverified" in page.text
        assert "action_send" in page.forms[f"email-actions-{second_email.email}"].fields
        assert "action_send" not in page.forms[f"email-actions-{user.email}"].fields

    def test_links_back_to_profile(self, app, user: User):
        page = app.get(reverse("account_email"), user=user)

        assert page.html.select_one(f'a[href="{user.get_absolute_url()}"]')
