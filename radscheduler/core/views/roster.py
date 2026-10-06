import json

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import HttpResponse

from radscheduler.core.forms import DateRangeForm
from radscheduler.core.service import group_shifts_by_date_and_type, retrieve_roster


@staff_member_required
def get_generated_roster(request):
    if request.method == "GET":
        form = DateRangeForm(request.GET)
        if form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
            events = group_shifts_by_date_and_type(start, end)
            events_json = json.dumps(events)
            return HttpResponse(events_json, content_type="application/json")


@staff_member_required
def get_roster(request):
    if request.method == "GET":
        form = DateRangeForm(request.GET)
        if form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
            events = retrieve_roster(start, end)
            events_json = json.dumps(events)
            return HttpResponse(events_json, content_type="application/json")
