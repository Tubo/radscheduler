import json
from datetime import date
from django.shortcuts import render, HttpResponse

from radscheduler.core.service import (
    retrieve_fullcalendar_events,
    retrieve_roster,
    retrieve_workload_breakdown,
    generate_roster,
)
from radscheduler.core.forms import DateRangeForm


def calendar_view(request):
    """
    Display the roster in a calendar format.
    """
    events = retrieve_fullcalendar_events()
    events_json = json.dumps(events)
    return render(request, "calendar.html", {"events": events_json})


def roster_table_view(request):
    """
    Display the roster in a table format.
    """
    return render(request, "roster_table.html")


def roster_generation_view(request):
    """
    Display the roster generation form.
    """
    return render(request, "roster_generation.html")


def get_generated_roster(request):
    if request.method == "GET":
        form = DateRangeForm(request.GET)
        if form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
            events = generate_roster(start, end)
            events_json = json.dumps(events)
            return HttpResponse(events_json, content_type="application/json")


def get_roster_table(request):
    if request.method == "GET":
        form = DateRangeForm(request.GET)
        if form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
            events = retrieve_roster(start, end)
            events_json = json.dumps(events)
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
