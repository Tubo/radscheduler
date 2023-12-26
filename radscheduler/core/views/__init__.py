import json
from datetime import date

from django.shortcuts import HttpResponse, render

from radscheduler.core.service import (
    group_shifts_by_date_and_type,
    retrieve_fullcalendar_events,
    retrieve_roster,
    retrieve_workload_breakdown,
)


def get_calendar(request):
    """
    Display the roster in a calendar format.
    """
    if request.method == "GET":
        events = retrieve_fullcalendar_events(request.user.registrar)
        events_json = json.dumps(events)
        return HttpResponse(events_json, content_type="application/json")
