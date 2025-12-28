import json
from datetime import date, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from radscheduler import roster
from radscheduler.core import domain_mapper
from radscheduler.core.forms import (
    DateForm,
    DateRangeForm,
    EventsFilterForm,
    LeaveChangeEditorForm,
    SettingsForm,
    ShiftAddForm,
    ShiftChangeForm,
)
from radscheduler.core.models import Registrar, Settings, Shift, Status
from radscheduler.core.service import *


@staff_member_required
@require_GET
def page(request, date_=None):
    """
    Display the roster generation form.
    """
    date_form = DateForm({"date": date_})
    week_in_focus = (
        date_form.cleaned_data["date"] if date_form.is_valid() else date.today()
    )

    # By default, show all shift types and leave types
    shift_types, leave_types = roster.ShiftType.values, roster.LeaveType.values

    if "shift_types" in request.GET or "leave_types" in request.GET:
        events_filter_form = EventsFilterForm(request.GET)
    elif request.up:
        # Else if the request is an Unpoly request, use the context data from unpoly
        data = {
            "shift_types": request.up.context.get("shift_types", []),
            "leave_types": request.up.context.get("leave_types", []),
        }
        events_filter_form = EventsFilterForm(data)
    else:
        # If the request is an normal browser request, create a new form with the default values
        events_filter_form = EventsFilterForm(
            initial={
                "shift_types": shift_types,
                "leave_types": leave_types,
            }
        )

    if events_filter_form.is_bound:
        if events_filter_form.is_valid():
            shift_types = events_filter_form.cleaned_data["shift_types"]
            leave_types = events_filter_form.cleaned_data["leave_types"]

    registrars, dates, events = get_events(week_in_focus, shift_types, leave_types)

    return render(
        request,
        "editor/page.html",
        {
            "events_filter_form": events_filter_form,
            "registrars": registrars,
            "dates": dates,
            "events": events,
            "holidays": canterbury_holidays,
            "week_in_focus": week_in_focus,
            "prev": week_in_focus - timedelta(weeks=1),
            "next": week_in_focus + timedelta(weeks=1),
            "shift_types": roster.ShiftType.choices,
            "leave_types": roster.LeaveType.choices,
        },
    )


@staff_member_required
@require_GET
def update_cell(request):
    pass


@staff_member_required
@require_POST
def add_shift(request):
    "Add shift button"
    shift_types = roster.ShiftType.choices
    form = ShiftAddForm(request.POST)
    if form.is_valid():
        shift = form.save(commit=False)
        stat_day = shift.date in canterbury_holidays
        shift.stat_day = stat_day
        shift.save()
        return render(
            request,
            "editor/wrapper_cell.html",
            {
                "template_name": "editor/event_shift_button.html",
                "shift": shift,
                "shift_types": shift_types,
            },
        )
    return HttpResponse(status=304)


@staff_member_required
@require_POST
def change_shift(request, pk):
    shift_types = roster.ShiftType.choices
    shift = Shift.objects.get(pk=pk)
    form = ShiftChangeForm(request.POST, instance=shift)
    if form.is_valid():
        shift = form.save()
        return render(
            request,
            "editor/event_shift_button.html",
            {"shift": shift, "shift_types": shift_types},
        )
    return HttpResponse(status=304)


@staff_member_required
@require_POST
def delete_shift(request, pk):
    try:
        shift = Shift.objects.get(pk=pk)
        shift.delete()
        if request.up:
            request.up.emit("shift:deleted", {"shift_id": pk})
        return HttpResponse(status=204)
    except Shift.DoesNotExist:
        return HttpResponse(status=404)
    except Exception:
        return HttpResponse(status=500)


@staff_member_required
@require_POST
def change_leave(request, pk):
    leave = Leave.objects.get(pk=pk)
    form = LeaveChangeEditorForm(request.POST, instance=leave)
    if form.is_valid():
        leave = form.save()
        return render(request, "editor/event_leave_button.html", {"leave": leave})
    return HttpResponse(status=304)


@staff_member_required
@require_GET
def settings(request):
    """
    Display the settings form.
    """
    settings_obj = Settings.objects.first()
    if not settings_obj:
        settings_obj = Settings.objects.create(
            publish_start_date=date.today(),
            publish_end_date=date.today() + timedelta(days=365),
        )
    form = SettingsForm(instance=settings_obj)
    return render(request, "editor/settings.html", {"form": form})


@staff_member_required
@require_POST
def update_settings(request):
    """
    Update the settings.
    """
    settings_obj = Settings.objects.first()
    if not settings_obj:
        settings_obj = Settings.objects.create(
            publish_start_date=date.today(),
            publish_end_date=date.today() + timedelta(days=365),
        )
    form = SettingsForm(request.POST, instance=settings_obj)
    if form.is_valid():
        form.save()
        response = HttpResponse(status=204)
        response["X-Up-Accept-Layer"] = json.dumps(None)
        return response
    return render(request, "editor/settings.html", {"form": form}, status=400)
