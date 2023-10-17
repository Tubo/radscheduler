from django.db import models

from radscheduler.core.models import Registrar
from radscheduler.roster import LeaveType


class LeaveRow(models.Model):
    start_date = models.DateField()
    end_date = models.DateField()
    return_date = models.DateField()
    total_hours = models.IntegerField()
    type = models.CharField(max_length=10, choices=LeaveType.choices)
    form = models.ForeignKey("LeaveForm", related_name="rows", on_delete=models.CASCADE)
    comment = models.CharField(max_length=100, blank=True, null=True)


class LeaveForm(models.Model):
    """
    - Generate printable PDF
    - Triggers an email after creation
    """

    registrar = models.ForeignKey(Registrar, on_delete=models.CASCADE)
    employee_number = models.CharField(max_length=20, blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    last_edited = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(default=False)
