import argparse
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError

from radscheduler.core.io import import_history, import_status, import_users
from radscheduler.core.models import Leave, Registrar, Shift, Status
from radscheduler.users.models import User


def valid_date(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):
    help = "Import previous roster from CSV file"

    def add_arguments(self, parser):
        parser.add_argument("history", type=str, help="Path to csv file")
        parser.add_argument("--users", type=str, help="Path to user profiles")
        parser.add_argument("--statuses", type=str, help="Path to status file")
        parser.add_argument("--start", type=valid_date, help="Start date")
        parser.add_argument("--end", type=valid_date, help="End date")

    def handle(self, *args, **options):
        fname = options["history"]
        start = options["start"]
        end = options["end"]
        profile_path = options["users"]
        statuses = options["statuses"]

        if not profile_path:
            profile_path = "resources/users.yaml"
        if not statuses:
            statuses = "resources/statuses.yaml"
        profiles = import_users(profile_path)
        users = profiles["users"]
        registrars = profiles["registrars"]
        Registrar.objects.bulk_create(registrars, ignore_conflicts=True)

        shifts, leaves = import_history(fname, users, start, end)
        statuses = import_status(statuses)
        Shift.objects.bulk_create(shifts)
        Leave.objects.bulk_create(leaves)
        Status.objects.bulk_create(statuses)
        self.stdout.write(self.style.SUCCESS("Successfully imported roster"))
