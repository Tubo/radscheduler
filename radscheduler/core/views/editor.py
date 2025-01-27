import json
from datetime import date, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from radscheduler import roster
from radscheduler.core import domain_mapper
from radscheduler.core.forms import DateForm, DateRangeForm, EventsFilterForm, ShiftAddForm, ShiftChangeForm
from radscheduler.core.models import Registrar, Shift, Status
from radscheduler.core.service import *


@staff_member_required
@require_GET
def page(request):
    """
    Display the roster generation form.
    """
    date_form = DateForm(request.GET)
    week_in_focus = date_form.cleaned_data["date"] if date_form.is_valid() else date.today()

    events_filter_form = EventsFilterForm(request.GET)
    if request.up and events_filter_form.is_valid():
        shift_types = events_filter_form.cleaned_data["shift_types"]
        leave_types = events_filter_form.cleaned_data["leave_types"]
    else:
        events_filter_form = EventsFilterForm(
            initial={"shift_types": roster.ShiftType.values, "leave_types": roster.LeaveType.values}
        )
        shift_types, leave_types = roster.ShiftType.values, roster.LeaveType.values

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
            "prev": week_in_focus - timedelta(weeks=1),
            "next": week_in_focus + timedelta(weeks=1),
        },
    )


def save_roster(request):
    if request.method == "POST":
        form = DateRangeForm(request.POST)
        if form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
            shifts = fill_shifts(start, end)
            to_save = []
            for shift in shifts:
                if not shift.pk and shift.registrar:
                    to_save.append(domain_mapper.shift_to_db(shift))
            try:
                Shift.objects.bulk_create(to_save)
                return HttpResponse("<span>Success</span>")
            except:
                return HttpResponse("<span>Failed</span>")


def change_shift_registrar(request, pk):
    if request.method == "GET":
        shift = Shift.objects.get(pk=pk)
        registrars = active_and_available_registrars(shift.date)
        return render(
            request,
            "editor/shift_cell_change_form.html",
            {
                "shift": shift,
                "registrars": registrars,
                "current_registrar": shift.registrar,
            },
        )

    elif request.method == "POST":
        form = ShiftChangeForm(request.POST)
        if form.is_valid():
            registrar = form.cleaned_data["registrar"]
            shift = Shift.objects.get(pk=pk)
            shift.registrar = registrar
            shift.save()
            return render(request, "editor/shift_cell_button.html", {"shift": domain_mapper.shift_from_db(shift)})

    elif request.method == "DELETE":
        form = ShiftChangeForm(request.POST)
        if form.is_valid():
            shift = Shift.objects.get(pk=pk)
            shift.delete()
            return HttpResponse()


def cancel_shift_change(request, pk):
    "Cancel button for change registrar form"
    shift = Shift.objects.get(pk=pk)
    return render(request, "editor/shift_cell_button.html", {"shift": domain_mapper.shift_from_db(shift)})


def add_shift(request):
    "Add shift button"
    if request.method == "GET":
        date = request.GET.get("date")
        type_ = request.GET.get("type")
        registrars = active_and_available_registrars(date)
        return render(
            request, "editor/shift_cell_new_form.html", {"registrars": registrars, "date": date, "type": type_}
        )

    elif request.method == "POST":
        form = ShiftAddForm(request.POST)
        if form.is_valid():
            registrar = form.cleaned_data["registrar"]
            date = form.cleaned_data["date"]
            type_ = form.cleaned_data["type"]
            stat_day = form.cleaned_data["stat_day"]
            extra_duty = form.cleaned_data["extra_duty"]
            shift = Shift(date=date, type=type_, registrar=registrar, stat_day=stat_day, extra_duty=extra_duty)
            shift.save()
            return render(request, "editor/shift_cell_button.html", {"shift": domain_mapper.shift_from_db(shift)})
