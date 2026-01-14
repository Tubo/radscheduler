from django.contrib import admin
from django.urls import reverse

from radscheduler.users.models import User


class TestUserAdmin:
    def test_changelist(self, admin_client):
        url = reverse("admin:users_user_changelist")
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_search(self, admin_client):
        url = reverse("admin:users_user_changelist")
        response = admin_client.get(url, data={"q": "test"})
        assert response.status_code == 200

    def test_add(self, admin_client):
        url = reverse("admin:users_user_add")
        response = admin_client.get(url)
        assert response.status_code == 200

        response = admin_client.post(
            url,
            data={
                "username": "test",
                "password1": "My_R@ndom-P@ssw0rd",
                "password2": "My_R@ndom-P@ssw0rd",
            },
        )
        assert response.status_code == 302
        assert User.objects.filter(username="test").exists()

    def test_view_user(self, admin_client):
        user = User.objects.get(username="admin")
        url = reverse("admin:users_user_change", kwargs={"object_id": user.pk})
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_changelist_without_registrar(self, admin_client, db):
        user = User.objects.create_user(username="no-registrar", password="pass")
        url = reverse("admin:users_user_changelist")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert user.username in response.content.decode()

    def test_registrar_year_missing_registrar(self, db):
        user = User.objects.create_user(username="no-registrar", password="pass")
        user_admin = admin.site._registry[User]
        assert user_admin.registrar_year(user) is None
