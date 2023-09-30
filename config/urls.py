"""
URL configuration for radscheduler project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from radscheduler.core.views import (
    calendar_view,
    table_view,
    get_roster_events,
    get_workload,
    get_date_annotations,
)

urlpatterns = [
    path("calendar/", calendar_view, name="calendar"),
    path("roster/", table_view, name="roster"),
    path("roster/events/", get_roster_events, name="roster_events"),
    path("roster/workload/", get_workload, name="roster_workload"),
    path("roster/dates/", get_date_annotations, name="roster_dates"),
    path("admin/", admin.site.urls),
]
