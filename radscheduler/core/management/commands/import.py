import argparse
from datetime import datetime

from django.core.management.base import BaseCommand

from radscheduler.core.models import Registrar, Shift, Leave, Status
from radscheduler.core.io import import_history, import_users, import_status


def valid_date(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):
    help = "Import previous roster from CSV file"

    def add_arguments(self, parser):
        parser.add_argument("fname", type=str, help="Path to csv file")
        parser.add_argument("user_profiles", type=str, help="Path to user profiles")
        parser.add_argument("status", type=str, help="Path to status file")
        parser.add_argument("--start", type=valid_date, help="Start date")
        parser.add_argument("--end", type=valid_date, help="End date")

    def handle(self, *args, **kwargs):
        fname = kwargs["fname"]
        start = kwargs.get("start", None)
        end = kwargs.get("end", None)

        users = import_users(kwargs["user_profiles"])
        Registrar.objects.bulk_create(users.values())
        shifts, leaves = import_history(fname, users, start, end)
        statuses = import_status(kwargs["status"])
        Shift.objects.bulk_create(shifts)
        Leave.objects.bulk_create(leaves)
        Status.objects.bulk_create(statuses)
        self.stdout.write(self.style.SUCCESS("Successfully imported roster"))
