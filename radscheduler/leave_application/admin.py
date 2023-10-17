from typing import Any

from django import forms
from django.contrib import admin
from django.db import models
from django.http.request import HttpRequest

from radscheduler.leave_application.models import LeaveForm, LeaveRow


class LeaveRowInline(admin.TabularInline):
    model = LeaveRow
    extra = 6


@admin.register(LeaveForm)
class LeaveFormAdmin(admin.ModelAdmin):
    inlines = [LeaveRowInline]
    list_display = ["registrar", "created", "approved"]
    readonly_fields = ["created", "last_edited"]
