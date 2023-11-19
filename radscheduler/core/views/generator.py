import json
from datetime import date, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from radscheduler.core import mapper
from radscheduler.core.forms import DateRangeForm
from radscheduler.core.models import Shift
from radscheduler.core.service import breakdown_before_and_after, fill_shifts, group_shifts_by_date_and_type


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
            breakdown = breakdown_before_and_after(shifts)
            form = DateRangeForm(initial={"start": start, "end": end})
            return render(request, "generator/page.html", {"days": days, "breakdown": breakdown, "form": form})
        else:
            start = date.today()
            shifts = (
                Shift.objects.filter(date__gte=start).order_by("-date").select_related("registrar", "registrar__user")
            )
            end = shifts.first().date if shifts else start + timedelta(days=90)
            form = DateRangeForm(initial={"start": start, "end": end})
            shifts = list(map(mapper.shift_from_db, shifts))
            days = group_shifts_by_date_and_type(start, end, shifts)
            breakdown = breakdown_before_and_after(shifts)
    return render(request, "generator/page.html", {"days": days, "breakdown": breakdown, "form": form})


def save_roster(request):
    pass
