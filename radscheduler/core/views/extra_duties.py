from datetime import date, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import redirect, render

from radscheduler.core.forms import ShiftInterestForm
from radscheduler.core.models import Shift, ShiftInterest, Status
from radscheduler.roster import ShiftType, StatusType, canterbury_holidays


@login_required
def page(request):
    if hasattr(request.user, "registrar"):
        subquery = ShiftInterest.objects.filter(registrar=request.user.registrar, shift=OuterRef("pk"))
        extra_shifts = (
            Shift.objects.filter(extra_duty=True, date__gte=date.today() - timedelta(days=30))
            .annotate(
                interest_id=Subquery(subquery.values("pk")),
                comment=Subquery(subquery.values("comment")),
            )
            .order_by("-date")
            .select_related("registrar__user")
            .prefetch_related("interests")
        )

        return render(
            request,
            "extra_duties/page.html",
            {"extra_shifts": extra_shifts, "holidays": canterbury_holidays},
        )
    else:
        messages.error(request, "You are not a registrar.")
        return redirect("home")


@login_required
def interests(request):
    if request.method == "POST":
        shift_id = request.POST.get("shift_id")
        shift = Shift.objects.get(pk=shift_id)
        interest = ShiftInterest.objects.create(registrar=request.user.registrar, shift=shift)
        shift.interest_id = interest.pk
        shift.comment = interest.comment
        return render(
            request, "extra_duties/row.html", {"shift": shift, "interest": interest, "holidays": canterbury_holidays}
        )


@login_required
def interest(request, interest_id):
    interest = ShiftInterest.objects.get(id=interest_id)
    shift = interest.shift

    if request.method == "POST":
        form = ShiftInterestForm(request.POST, instance=interest)
        if form.is_valid():
            form.save()
            shift.interest_id = interest.pk
            shift.comment = interest.comment
            return render(
                request,
                "extra_duties/row.html",
                {"shift": shift, "interest": interest, "holidays": canterbury_holidays},
            )
    elif request.method == "DELETE":
        interest.delete()
        shift.interest = None
        return render(request, "extra_duties/row.html", {"shift": shift, "holidays": canterbury_holidays})


@staff_member_required
def edit_page(request):
    extra_shifts = (
        Shift.objects.filter(extra_duty=True, registrar=None).order_by("date").select_related("registrar__user")
    )

    return render(
        request, "extra_duties/edit_page.html", {"extra_shifts": extra_shifts, "holidays": canterbury_holidays}
    )
