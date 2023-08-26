import json
from django.shortcuts import render

from radscheduler.core.service import retrieve_fullcalendar_events


# Create your views here.
def roster_view(request):
    """
    Display the roster in a calendar format.
    """
    events = retrieve_fullcalendar_events()
    e = json.dumps(events)
    return render(request, "roster.html", {"events": e})


def workload_view():
    """
    Various rankings of registrar workload
    - Heatmap of days of long days a registrar has done within a period
    """


def calendar_feed():
    """
    Three calendars
    - Oncall shifts
    - Leaves and RDOs
    - Leave requests (admin only)
    """
