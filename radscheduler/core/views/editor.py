import json
from datetime import date, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render

from radscheduler import roster
from radscheduler.core import domain_mapper
from radscheduler.core.forms import DateRangeForm, ShiftAddForm, ShiftChangeForm
from radscheduler.core.models import Registrar, Shift, Status
from radscheduler.core.service import (
    active_and_available_registrars,
    canterbury_holidays,
    fill_shifts,
    group_shifts_by_date_and_type,
    shifts_breakdown,
)


@staff_member_required
def page(request):
    """
    Display the roster generation form.
    """

    if request.method == "GET":
        form = DateRangeForm(request.GET)
        if form.is_valid():
            start = form.cleaned_data["start"]
            end = form.cleaned_data["end"]
            shifts = fill_shifts(start, end)
            days = group_shifts_by_date_and_type(start, end, shifts)
            workload = shifts_breakdown(shifts)
            form = DateRangeForm(initial={"start": start, "end": end})
            return render(
                request,
                "editor/page.html",
                {
                    "days": days,
                    "workload": workload,
                    "form": form,
                    "holidays": canterbury_holidays,
                },
            )
        else:
            start = date.today()
            shifts = (
                Shift.objects.filter(date__gte=start)
                .order_by("-date", "extra_duty", "registrar")
                .select_related("registrar", "registrar__user")
            )
            end = shifts.first().date if shifts else start + timedelta(days=90)
            form = DateRangeForm(initial={"start": start, "end": end})
            shifts = list(map(domain_mapper.shift_from_db, shifts))
            buddy_required = list(
                Status.objects.filter(type=roster.StatusType.BUDDY, start__lte=end, end__gte=start).values_list(
                    "registrar", flat=True
                )
            )
            days = group_shifts_by_date_and_type(start, end, shifts)
            workload = shifts_breakdown(shifts)
    return render(
        request,
        "editor/page.html",
        {
            "days": days,
            "workload": workload,
            "buddy_required": buddy_required,
            "form": form,
            "holidays": canterbury_holidays,
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
