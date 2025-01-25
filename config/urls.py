from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views import defaults as default_views
from django.views.generic import TemplateView

import radscheduler.core.ical as ical
import radscheduler.core.views.editor as editor_views
import radscheduler.core.views.extra_duties as extra_duties_views
import radscheduler.core.views.leaves as leaves_views
import radscheduler.core.views.roster as roster_views
from radscheduler.core.api import api

admin.site.site_header = "Radscheduler"

leave_view_urls = [
    path("", leaves_views.leave_page, name="leave_page"),
    path("list/", leaves_views.leave_list, name="leave_list"),
    path("inline/<int:pk>/", leaves_views.leave_row, name="leave_row"),
    path("inline/<int:pk>/form/", leaves_views.leave_form_inline, name="leave_form_inline"),
    path("inline/<int:pk>/delete/", leaves_views.leave_delete, name="leave_delete"),
]

editor_view_urls = [
    path("", editor_views.page, name="editor"),
    path("save/", editor_views.save_roster, name="save_shifts"),
    path("change_shift/<int:pk>/", editor_views.change_shift_registrar, name="change_shift"),
    path("change_shift/<int:pk>/cancel/", editor_views.cancel_shift_change, name="cancel_shift_change"),
    path("add_shift/", editor_views.add_shift, name="add_shift"),
]

roster_view_urls = [
    path("", TemplateView.as_view(template_name="roster/calendar.html"), name="calendar"),
    path("editor/", include(editor_view_urls)),
    # path("editor/", TemplateView.as_view(template_name="roster/editor.html"), name="editor"),
    path("table/", TemplateView.as_view(template_name="roster/roster_table.html"), name="roster"),
    path("workload/", roster_views.get_workload, name="workload"),
]

api_view_urls = [
    path("", api.urls, name="api"),
    path("table/events/", roster_views.get_roster, name="table_events"),
]


extra_duties_urls = [
    path("", extra_duties_views.page, name="extra_page"),
    path("interests/", extra_duties_views.interests, name="extra_interests"),
    path("interest/<int:interest_id>/", extra_duties_views.interest, name="extra_interest"),
    path("editor/", extra_duties_views.edit_page, name="extra_edit_page"),
    path("editor/random/", extra_duties_views.interested_random_registrar, name="extra_random_registrar"),
    path("editor/save/<int:shift_id>/", extra_duties_views.save_registrar, name="extra_save_registrar"),
]

ical_urls = [
    path("shifts/", ical.ShiftFeed(), name="ical_shifts"),
    path("leaves/", ical.LeaveFeed(), name="ical_leaves"),
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
    path("leaves/", include(leave_view_urls)),
    path("roster/", include(roster_view_urls)),
    path("extra_duties/", include(extra_duties_urls)),
    path("ical/", include(ical_urls)),
    path("api/", include(api_view_urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [path("django_functest/", include("django_functest.urls"))]
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
