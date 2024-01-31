import json
from datetime import date

import holidays
from django.http import JsonResponse
from django.shortcuts import HttpResponse, render

from radscheduler.core.forms import DateTimeRangeForm
from radscheduler.core.models import Leave, Shift
from radscheduler.roster import LeaveType, ShiftType


def get_calendar(request):
    """
    Display the roster in a calendar format.
    """
    if request.method == "GET":
        form = DateTimeRangeForm(request.GET)
        if form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
            shifts = Shift.objects.filter(date__gte=start, date__lte=end, registrar__isnull=False).select_related(
                "registrar", "registrar__user"
            )
            leaves = Leave.objects.filter(date__gte=start, date__lte=end, cancelled=False).select_related(
                "registrar", "registrar__user"
            )
            events = shifts_to_events(shifts) + leaves_to_events(leaves) + holidays_to_events(start.year)
            return JsonResponse(events, safe=False)


def holidays_to_events(year):
    cant_holidays = holidays.country_holidays("NZ", subdiv="CAN", years=year)
    result = []
    for date, name in cant_holidays.items():
        result.append(
            {
                "title": name,
                "start": format_date(date),
                "allDay": True,
                "order": 0,
                "display": "background",
            }
        )
    return result


def shifts_to_events(shifts):
    result = []

    for shift in shifts:
        shift_name = ShiftType(shift.type).name
        result.append(
            {
                "id": shift.id,
                "start": format_date(shift.date),
                "title": f"{shift_name}: {shift.registrar.user.username}" + (" (extra)" if shift.extra_duty else ""),
                "allDay": True,
                "order": 1,
                **map_shift_type_to_colour(shift.type),
            }
        )
    return result


def leaves_to_events(leaves):
    result = []
    for leave in leaves:
        leave_name = LeaveType(leave.type).name
        approved = leave.reg_approved and leave.dot_approved

        portion = f" ({leave.portion})" if leave.portion != "ALL" else ""
        tbc = " (TBC)" if not approved else ""
        result.append(
            {
                "id": leave.id,
                "start": format_date(leave.date),
                "title": f"{leave_name.capitalize()} {portion}: {leave.registrar.user.username}" + tbc,
                "allDay": True,
                "order": 2,
                "textColor": "black" if approved else "white",
                "backgroundColor": "DarkSeaGreen" if approved else "grey",
            }
        )
    return result


def format_date(date):
    return date.strftime("%Y-%m-%d")


def map_shift_type_to_colour(shift_type):
    if shift_type == "LONG":
        foreground = "black"
        background = "#FFB6C1"
    elif shift_type == "NIGHT":
        foreground = None
        background = "#000000"
    else:
        foreground = "black"
        background = "PaleTurquoise"
    return {"backgroundColor": background, "textColor": foreground}
