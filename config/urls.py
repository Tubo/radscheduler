from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views import defaults as default_views
from django.views.generic import TemplateView

import radscheduler.core.views as views
import radscheduler.core.views.leaves as leaves_views

leave_view_urls = [
    path("", leaves_views.leave_page, name="leave_page"),
    path("list/", leaves_views.leave_list, name="leave_list"),
    path("form/", leaves_views.leave_form, name="leave_form"),
    path("inline/<int:pk>/", leaves_views.leave_row, name="leave_row"),
    path("inline/<int:pk>/form/", leaves_views.leave_form_inline, name="leave_form_inline"),
    path("inline/<int:pk>/delete/", leaves_views.leave_delete, name="leave_delete"),
]

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path("about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("radscheduler.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
    # Your stuff: custom urls includes go here
    path("calendar/", TemplateView.as_view(template_name="roster/calendar.html"), name="calendar"),
    path("calendar/events/", views.get_calendar, name="calendar_events"),
    path("roster/", TemplateView.as_view(template_name="roster/roster_table.html"), name="roster"),
    path("roster/events/", views.get_roster, name="roster_events"),
    path("roster/workload/", views.get_workload, name="roster_workload"),
    path("leaves/", include(leave_view_urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
