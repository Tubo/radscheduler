from typing import Any

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth import decorators, get_user_model
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from django.utils.translation import gettext_lazy as _

from radscheduler.core.models import Registrar
from radscheduler.users.forms import UserAdminChangeForm, UserAdminCreationForm

User = get_user_model()

if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    # Force the `admin` sign in process to go through the `django-allauth` workflow:
    # https://django-allauth.readthedocs.io/en/stable/advanced.html#admin
    admin.site.login = decorators.login_required(admin.site.login)  # type: ignore[method-assign]


class RegistrarInline(admin.StackedInline):
    model = Registrar


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("name", "email")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = [
        "username",
        "name",
        "registrar_year",
        "registrar_start",
        "registrar_finish",
        "employee_number",
        "phone",
    ]
    list_editable = ["name"]
    search_fields = ["name", "username"]
    inlines = [RegistrarInline]
    ordering = ["-registrar__start"]
    list_select_related = ["registrar"]

    def registrar_year(self, obj: User) -> Any:
        return obj.registrar.year

    def registrar_start(self, obj: User) -> Any:
        return obj.registrar.start

    def registrar_finish(self, obj: User) -> Any:
        return obj.registrar.finish

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request)
