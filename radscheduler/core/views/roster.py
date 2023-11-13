import json
from datetime import date

from django.shortcuts import HttpResponse, render

from radscheduler.core.forms import DateRangeForm
from radscheduler.core.service import group_shifts_by_date_and_type, retrieve_roster, retrieve_workload_breakdown


def get_generated_roster(request):
    if request.method == "GET":
        form = DateRangeForm(request.GET)
        if form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
            events = group_shifts_by_date_and_type(start, end)
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
