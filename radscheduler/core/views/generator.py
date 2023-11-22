import json
from datetime import date, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render

from radscheduler.core import mapper
from radscheduler.core.forms import DateRangeForm, ShiftFormSet
from radscheduler.core.models import Shift
from radscheduler.core.service import canterbury_holidays, fill_shifts, group_shifts_by_date_and_type, shifts_breakdown


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
                "generator/page.html",
                {"days": days, "workload": workload, "form": form, "holidays": canterbury_holidays},
            )
        else:
            start = date.today()
            shifts = (
                Shift.objects.filter(date__gte=start).order_by("-date").select_related("registrar", "registrar__user")
            )
            end = shifts.first().date if shifts else start + timedelta(days=90)
            form = DateRangeForm(initial={"start": start, "end": end})
            shifts = list(map(mapper.shift_from_db, shifts))
            days = group_shifts_by_date_and_type(start, end, shifts)
            workload = shifts_breakdown(shifts)
    return render(
        request,
        "generator/page.html",
        {"days": days, "breakdown": workload, "form": form, "holidays": canterbury_holidays},
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
                    to_save.append(mapper.shift_to_db(shift))
            try:
                Shift.objects.bulk_create(to_save)
                return HttpResponse("<span>Success</span>")
            except:
                return HttpResponse("<span>Failed</span>")
