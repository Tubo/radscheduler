import random
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import F, OuterRef, Q, Subquery
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from radscheduler.core.forms import ShiftChangeForm, ShiftInterestForm
from radscheduler.core.models import Shift, ShiftInterest, Status
from radscheduler.core.service import active_registrars
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
    subquery = ShiftInterest.objects.filter(registrar=request.user.registrar, shift=OuterRef("pk"))
    buddy_shifts = Shift.objects.filter(date=OuterRef("date"), type=OuterRef("type"), extra_duty=False).values(
        "registrar__user__username"
    )
    extra_shifts = (
        Shift.objects.filter(extra_duty=True, date__gte=date.today() - timedelta(days=30))
        .annotate(
            interest_id=Subquery(subquery.values("pk")),
            comment=Subquery(subquery.values("comment")),
            buddy=Subquery(buddy_shifts[:1]),
        )
        .order_by("-date")
        .select_related("registrar__user")
        .prefetch_related("interests", "interests__registrar__user")
    )
    end = extra_shifts.first().date if extra_shifts else date.today()
    start = extra_shifts.last().date if extra_shifts else date.today()
    registrars = active_registrars(start, end)

    return render(
        request,
        "extra_duties/edit_page.html",
        {"extra_shifts": extra_shifts, "registrars": registrars, "holidays": canterbury_holidays},
    )


@staff_member_required
def interested_random_registrar(request):
    shift_id = request.GET.get("id")
    interests = Shift.objects.get(pk=shift_id).interests.values("registrar").all()
    if len(interests) == 0:
        return JsonResponse({}, safe=True)
    else:
        return JsonResponse(random.choice(list(interests)), safe=True)


@staff_member_required
def save_registrar(request, shift_id):
    if request.method == "POST":
        form = ShiftChangeForm(request.POST)
        if form.is_valid():
            registrar = form.cleaned_data["registrar"]
            shift = Shift.objects.get(pk=shift_id)
            shift.registrar = registrar
            shift.save()
            return HttpResponse("Saved", status=200)
