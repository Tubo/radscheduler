import json
from datetime import date

from django.shortcuts import HttpResponse, render

from radscheduler.core.forms import DateRangeForm
from radscheduler.core.service import (
    generate_roster,
    retrieve_fullcalendar_events,
    retrieve_roster,
    retrieve_workload_breakdown,
)


def get_calendar(request):
    """
    Display the roster in a calendar format.
    """
    if request.method == "GET":
        events = retrieve_fullcalendar_events()
        events_json = json.dumps(events)
        return HttpResponse(events_json, content_type="application/json")


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


def get_roster(request):
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
