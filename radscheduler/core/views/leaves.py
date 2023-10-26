from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django_htmx.http import HttpResponseClientRefresh

from radscheduler.core.forms import LeaveForm
from radscheduler.core.models import Leave


@login_required
def leave_page(request):
    form = LeaveForm()
    rows = Leave.objects.filter(registrar__user=request.user).order_by("-date")
    return render(request, "leaves/page.html", {"form": form, "rows": rows})


@login_required
def leave_form(request):
    if request.method == "POST":
        form = LeaveForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.registrar = request.user.registrar
            try:
                leave.save()
                form = LeaveForm(initial={"date": leave.date + timedelta(days=1), "type": leave.type})
            except IntegrityError as e:
                messages.error(request, "Leave already exists for this date")
                return HttpResponseClientRefresh()
    else:
        form = LeaveForm()
    return render(request, "leaves/form.html", {"form": form})


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