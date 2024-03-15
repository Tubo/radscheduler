from collections import OrderedDict
from collections.abc import Sequence
from datetime import date, timedelta
from enum import IntEnum
from typing import Any

from django.contrib import admin
from django.db.models import Exists, OuterRef, Q
from django.db.models import Value as V
from django.db.models import functions as fn
from django.db.models.query import QuerySet
from django.http import FileResponse
from django.http.request import HttpRequest
from rangefilter.filters import DateRangeFilterBuilder

from radscheduler.core.models import Leave, Registrar, Shift, Status
from radscheduler.paper_forms.pdf import leaves_to_buffer
from radscheduler.roster.models import ShiftType, Weekday


class ISOWeekday(IntEnum):
    MON = 1
    TUE = 2
    WED = 3
    THUR = 4
    FRI = 5
    SAT = 6
    SUN = 7


# Register your models here.
def weekday(obj):
    return Weekday(obj.date.weekday()).name.capitalize()


class ShiftTypeListFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = "Shift categories"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "category"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return [
            ("weekdays", "Long days"),
            ("weekends", "Weekends"),
            ("weekends_and_rdos", "Weekends and RDOs"),
            ("nights", "Nights"),
            ("nights_and_sleeps", "Nights and sleep days"),
        ]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        queryset = queryset.select_related("registrar", "registrar__user")

        if self.value() == "weekdays":
            return queryset.filter(
                type=ShiftType.LONG,
                date__iso_week_day__in=[
                    ISOWeekday.MON,
                    ISOWeekday.TUE,
                    ISOWeekday.WED,
                    ISOWeekday.THUR,
                    ISOWeekday.FRI,
                ],
            )

        if self.value() == "weekends":
            return queryset.filter(
                Q(
                    type=ShiftType.LONG,
                    date__iso_week_day__in=[ISOWeekday.SAT, ISOWeekday.SUN],
                )
            )

        if self.value() == "weekends_and_rdos":
            return queryset.filter(
                Q(
                    type=ShiftType.LONG,
                    date__iso_week_day__in=[ISOWeekday.SAT, ISOWeekday.SUN],
                )
                | Q(type=ShiftType.RDO)
            )

        if self.value() == "nights":
            return queryset.filter(type=ShiftType.NIGHT)

        if self.value() == "nights_and_sleeps":
            return queryset.filter(
                type__in=[ShiftType.NIGHT, ShiftType.SLEEP],
            )


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    """
    Shift list view (admin):
    - Day of shift
    - Weekday of shift
    - Type of shift
    - Registrar covering
    - Default filter out shifts older than 2 weeks
    - Default show 50-100 entries
    - Default only show usual leave types
    - Filter by date range
    - Unfilled shifts

    Shift list view (user):
    - Extra duties
    """

    list_display = (
        "date",
        weekday,
        "type",
        "registrar",
    )

    ordering = ("-date", "registrar")

    list_select_related = ["registrar", "registrar__user"]

    list_filter = (
        (
            "date",
            DateRangeFilterBuilder(
                title="Shift date",
                default_start=date.today(),
                default_end=date.today() + timedelta(days=31),
            ),
        ),
        ShiftTypeListFilter,
    )


class OfficeLeaveFilter(admin.SimpleListFilter):
    title = "ready to print (for Chris)"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "for_office"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return [("2_weeks", "Next 2 weeks"), ("4_weeks", "Next 4 weeks"), ("6_weeks", "Next 6 weeks")]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        office = (
            queryset.filter(
                date__gte=date.today(),
                dot_approved=True,
                reg_approved=True,
                cancelled=False,
                printed=False,
            )
            .exclude(date__iso_week_day__in=[ISOWeekday.SAT, ISOWeekday.SUN])
            .select_related("registrar", "registrar__user")
        )

        if self.value() == "2_weeks":
            return office.filter(date__lte=date.today() + timedelta(days=14))

        elif self.value() == "4_weeks":
            return office.filter(date__lte=date.today() + timedelta(days=28))

        elif self.value() == "6_weeks":
            return office.filter(date__lte=date.today() + timedelta(days=42))

        else:
            return queryset


@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display = (
        "custom_date_format",
        "name",
        "type",
        "portion",
        "comment",
        "reg_approved",
        "dot_approved",
        "microster",
        "rostered",
        "printed",
        "no_abutting_weekend",
        "cancelled",
        "created",
        "last_edited",
    )
    list_editable = (
        "dot_approved",
        "reg_approved",
        "printed",
        "microster",
        "no_abutting_weekend",
        "cancelled",
    )
    list_filter = (
        (
            "date",
            DateRangeFilterBuilder(
                title="Leave date",
                default_start=date.today(),
                default_end=date.today() + timedelta(days=31 * 3),
            ),
        ),
        OfficeLeaveFilter,
        "reg_approved",
        "dot_approved",
        "type",
        "printed",
        "microster",
        "registrar__user",
    )
    list_select_related = ("registrar", "registrar__user")
    actions = ["mark_reg_approved", "mark_dot_approved", "mark_printed", "print_selected"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            # Check if a shift exists for the leave date
            rostered=Exists(Shift.objects.filter(registrar=OuterRef("registrar"), date=OuterRef("date"))),
            # Extract the last name from the user's name
            last_name=fn.Substr("registrar__user__name", fn.StrIndex("registrar__user__name", V(" ")) + 1),
        )
        queryset = queryset.order_by("-date", "last_name")
        queryset = queryset.select_related("registrar", "registrar__user")
        return queryset

    def get_list_display(self, request: HttpRequest) -> Sequence[str]:
        if request.user.username in ["dot", "office"]:
            return (
                "custom_date_format",
                "registrar",
                "type",
                "portion",
                "comment",
                "reg_approved",
                "dot_approved",
                "printed",
                "created",
                "last_edited",
            )
        return self.list_display

    def get_actions(self, request: HttpRequest) -> OrderedDict[Any, Any]:
        actions = super().get_actions(request)
        if request.user.username == "dot":
            if "mark_reg_approved" in actions:
                del actions["mark_reg_approved"]
            return actions
        elif request.user.username == "office":
            if "mark_dot_approved" in actions:
                del actions["mark_dot_approved"]
            if "mark_reg_approved" in actions:
                del actions["mark_reg_approved"]
            return actions
        else:
            return actions

    @admin.display(description="Date", ordering="date")
    def custom_date_format(self, obj):
        if obj.date:
            return obj.date.strftime("%d-%m-%Y, %a")
        return ""

    @admin.display(description="Rostered", boolean=True)
    def rostered(self, obj):
        # Returns True if a shift exists for the leave date
        return obj.rostered

    @admin.display(description="Name", ordering="last_name")
    def name(self, obj):
        full_name = obj.registrar.user.name
        return full_name if full_name else obj.registrar.user.username

    @admin.action(description="Print the selected leave forms")
    def print_selected(self, request, queryset):
        buffer = leaves_to_buffer(queryset)
        return FileResponse(buffer, as_attachment=False, filename="leaves.pdf")

    @admin.action(description="Mark selected leaves as registrar approved")
    def mark_reg_approved(self, request, queryset):
        queryset.update(reg_approved=True)

    @admin.action(description="Mark selected leaves as DOT approved")
    def mark_dot_approved(self, request, queryset):
        queryset.update(dot_approved=True)

    @admin.action(description="Mark selected leaves as printed")
    def mark_printed(self, request, queryset):
        queryset.update(printed=True)


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = (
        "registrar",
        "start",
        "end",
        "type",
        "weekdays",
        "shift_types",
        "comment",
    )
    list_filter = ("registrar__user", "type")
    list_select_related = ("registrar", "registrar__user")
