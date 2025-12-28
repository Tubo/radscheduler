from datetime import date, timedelta

from django_ical.views import ICalFeed

from radscheduler.core.models import Leave, Shift
from radscheduler.roster.models import LeaveType, ShiftType


class ShiftFeed(ICalFeed):
    product_id = "-//radscheduler//radscheduler//EN"
    timezone = "Pacific/Auckland"

    def items(self):
        # Only fetch recent past (30 days) and future shifts to reduce query size
        return (
            Shift.objects.filter(
                date__gte=date.today() - timedelta(days=30), registrar__isnull=False
            )
            .select_related("registrar", "registrar__user")
            .only(
                "id",
                "date",
                "type",
                "extra_duty",
                "registrar__id",
                "registrar__user__username",
            )
        )

    def item_title(self, shift):
        result = f"{shift.type}: {shift.registrar.user.username}"
        if shift.extra_duty:
            result += " (extra)"
        return result

    def item_description(self, shift):
        shift_type = ShiftType(shift.type).label
        result = f"{shift_type}: {shift.registrar.user.username}"
        if shift.extra_duty:
            result += " (extra duty)"
        return result

    def item_start_datetime(self, shift):
        return shift.date

    def item_guid(self, shift):
        return f"shift_{shift.id}"

    def item_link(self, _):
        return "/"


class LeaveFeed(ICalFeed):
    product_id = "-//radscheduler//radscheduler//EN"
    timezone = "Pacific/Auckland"

    def items(self):
        # Only fetch recent past (30 days) and future leaves to reduce query size
        return (
            Leave.objects.filter(
                date__gte=date.today() - timedelta(days=30), cancelled=False
            )
            .select_related("registrar", "registrar__user")
            .only(
                "id",
                "date",
                "type",
                "portion",
                "registrar__id",
                "registrar__user__username",
            )
        )

    def item_title(self, leave):
        portion = f" ({leave.portion})" if leave.portion != "ALL" else ""
        leave_type = LeaveType(leave.type).label
        return f"{leave.registrar.user.username}: {leave_type}{portion}"

    def item_description(self, leave):
        return self.item_title(leave)

    def item_start_datetime(self, leave):
        return leave.date

    def item_guid(self, leave):
        return f"leave_{leave.id}"

    def item_link(self, _):
        return "/"
