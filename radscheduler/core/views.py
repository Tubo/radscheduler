import json
from datetime import date
from django.shortcuts import render, HttpResponse

from radscheduler.core.service import (
    retrieve_fullcalendar_events,
    retrieve_roster_events,
    retrieve_workload_breakdown,
)
from radscheduler.core.forms import DateRangeForm


def calendar_view(request):
    """
    Display the roster in a calendar format.
    """
    events = retrieve_fullcalendar_events()
    events_json = json.dumps(events)
    return render(request, "calendar.html", {"events": events_json})


def table_view(request):
    """
    Display the roster in a table format.

    Todo: This should be eventually changed into an Unicorn view.
    """
    return render(request, "table.html")


def get_roster_events(request):
    if request.method == "GET":
        form = DateRangeForm(request.GET)
        if form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
            events = retrieve_roster_events(start, end)
            events_json = events.to_json(orient="table", index=False)
            return HttpResponse(events_json, content_type="application/json")


def get_workload(request):
    """
    Various rankings of registrar workload
    - Heatmap of days of long days a registrar has done within a period
    """
    if request.method == "GET":
        form = DateRangeForm(request.GET)
        if form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
            workload = retrieve_workload_breakdown(start, end)
            events_json = workload.to_json(orient="table", index=False)
            return HttpResponse(events_json, content_type="application/json")


def feed_view():
    """
    iCal feed of all events groupbed by:
    - Oncall shifts
    - Leaves: RDO, SLEEP, AL, MEL, LIEU etc
    - Leave requests (admin only)
    """
