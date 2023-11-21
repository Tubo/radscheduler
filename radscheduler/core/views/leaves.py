from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404, redirect, render

from radscheduler.core.forms import LeaveForm
from radscheduler.core.models import Leave
from radscheduler.roster import canterbury_holidays


@login_required
def leave_page(request):
    try:
        registrar = request.user.registrar
    except ObjectDoesNotExist:
        messages.error(request, "You are not a registrar.")
        return redirect("home")

    if request.method == "POST":
        form = LeaveForm(request.POST)
        if form.is_valid():
            leave = form.save()
            next_date = leave.date + timedelta(days=1) if leave.date.weekday() < 4 else leave.date + timedelta(days=3)
            form = LeaveForm(
                initial={
                    "date": next_date,
                    "type": leave.type,
                    "portion": leave.portion,
                    "registrar": registrar,
                }
            )
            msg = f"Leave added for {leave.date.strftime('%d/%m/%Y')}"
            if leave.date in canterbury_holidays:
                msg += f" ({canterbury_holidays[leave.date]})"
            messages.info(request, msg)
        else:
            for error in form.non_field_errors():
                messages.error(request, error)
            form.initial = request.POST
    else:
        form = LeaveForm(initial={"registrar": registrar})
    rows = Leave.objects.filter(registrar=registrar).order_by("-date")
    return render(request, "leaves/page.html", {"form": form, "rows": rows})


@login_required
def leave_form_inline(request, pk):
    leave = get_object_or_404(Leave, pk=pk)
    if request.method == "POST":
        form = LeaveForm(request.POST, instance=leave)
        if form.is_valid():
            form.save()
            return redirect("leave_row", pk=leave.pk)
    else:
        form = LeaveForm(instance=leave)
    return render(request, "leaves/form_inline.html", {"form": form})


@login_required
def leave_row(request, pk):
    leave = get_object_or_404(Leave, pk=pk)
    return render(request, "leaves/row.html", {"row": leave})


@login_required
def leave_delete(request, pk):
    if request.method == "POST":
        leave = get_object_or_404(Leave, pk=pk)
        leave.delete()
    return redirect("leave_list")


@login_required
def leave_list(request):
    rows = Leave.objects.filter(registrar__user=request.user).order_by("-date")
    return render(request, "leaves/list.html", {"rows": rows})
