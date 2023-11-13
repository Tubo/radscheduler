import json
from datetime import date, timedelta

from django.shortcuts import HttpResponse, render

from radscheduler.core.forms import DateRangeForm
from radscheduler.core.models import Shift
from radscheduler.core.service import breakdown_before_and_after, fill_shifts, group_shifts_by_date_and_type


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
            breakdown = breakdown_before_and_after(shifts, start, end)
            form = DateRangeForm(initial={"start": start, "end": end})
            return render(request, "generator/page.html", {"days": days, "breakdown": breakdown, "form": form})
        else:
            start = date.today()
            shifts = (
                Shift.objects.filter(date__gte=start).order_by("-date").select_related("registrar", "registrar__user")
            )
            end = shifts.first().date
            form = DateRangeForm(initial={"start": start, "end": end})
            days = group_shifts_by_date_and_type(start, end, shifts)
            breakdown = breakdown_before_and_after(shifts, start, end)
    return render(request, "generator/page.html", {"days": days, "breakdown": breakdown, "form": form})


def save_roster(request):
    pass
