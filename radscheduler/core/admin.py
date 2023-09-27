from datetime import date, timedelta

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q

from rangefilter.filters import (
    DateRangeFilterBuilder,
    DateTimeRangeFilterBuilder,
    NumericRangeFilterBuilder,
    DateRangeQuickSelectListFilterBuilder,
)

from radscheduler.core.models import Registrar, Shift, ISOWeekday, Weekday, ShiftType


@admin.register(Registrar)
class RegistrarAdmin(UserAdmin):
    list_display = (
        "username",
        "year",
        "senior",
        "start",
        "finish",
    )
    ordering = ("-start", "username")


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

    ordering = ("date", "registrar")

    list_editable = ("registrar",)

    list_filter = (
        (
            "date",
            DateRangeFilterBuilder(
                title="Shift date",
                default_start=date.today(),
                default_end=date.today() + timedelta(days=31 * 2),
            ),
        ),
        ShiftTypeListFilter,
        "registrar",
    )


"""


Leave list view:
- Day start, finish, return
- Type of leave
- Approval status (me, Chris, DOT)
- Active or not (calculated by finish date)

Leave form details view:
- Generate PDF
- Hide special types

Custom actions
- Swap shifts
"""
