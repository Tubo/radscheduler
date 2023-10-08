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
    roster_table_view,
    roster_generation_view,
    get_roster_table,
    get_workload,
    get_generated_roster,
)

urlpatterns = [
    path("calendar/", calendar_view, name="calendar"),
    path("roster/", roster_table_view, name="roster_table_view"),
    path("roster/events/", get_roster_table, name="roster_events"),
    path("roster/workload/", get_workload, name="roster_workload"),
    path("generate/", roster_generation_view, name="roster_generate_view"),
    path("generate/results/", get_generated_roster, name="roster_generate_results"),
    path("admin/", admin.site.urls),
]
