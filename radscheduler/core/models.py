from enum import Enum, IntEnum, auto

from django.db import models
from django.contrib.auth.models import AbstractUser


class Weekday(IntEnum):
    MON = 0
    TUE = 1
    WED = 2
    THUR = 3
    FRI = 4
    SAT = 5
    SUN = 6


class Registrar(AbstractUser):
    senior = models.BooleanField(default=False)
    start = models.DateField("start date")
    finish = models.DateField("finish date")
    year = models.IntegerField(default=1)

    def __repr__(self) -> str:
        return f"<Profile: {self.username}>"


class ShiftType(models.TextChoices):
    LONG = "L", "Long day"  # from 5pm to 10m
    NIGHT = "N", "Night"  # from 10pm to 8am
    WEEKEND = "W", "Weekend"  # from 8am to 10pm
    WRDO = "WRDO", "Post weekend RDO"
    NRDO = "NRDO", "Sleep day"


class Shift(models.Model):
    date = models.DateField("shift date")
    type = models.CharField("shift type", max_length=10, choices=ShiftType)
    registrar = models.ForeignKey(
        Registrar,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    stat_day = models.BooleanField(default=False)
    extra_duty = models.BooleanField(default=False)
    fatigue_override = models.FloatField(default=0.0)

    def __repr__(self) -> str:
        if self.registrar:
            registrar = self.registrar.username
        else:
            registrar = "N/A"
        return f"<{self.type} Shift {self.date} ({Weekday(self.date.weekday()).name}): {registrar}>"


class StatusType(models.IntegerChoices):
    PRE_ONCALL = auto(), "Pre-oncall"
    RELIEVER = auto(), "Reliever"
    PART_TIME = auto(), "Part time non-working day"
    PRE_EXAM = auto(), "Pre-exam"
    BUDDY = auto(), "Buddy required"


class Status(models.Model):
    """
    Given a date range, a registrar can be assigned a status.

    - Pre-oncall: 1st years
    - Reliever: no auto assignment, only manual rostering
    - Part time: do not work on some days
    - Pre-exam: 2 weeks before pathology, 6 months before viva
    - Buddy: 2nd years requiring a buddy when oncall
    """

    start = models.DateField("start date")
    end = models.DateField("end date")
    type = models.IntegerField(choices=StatusType)
    registrar = models.ForeignKey(
        Registrar, blank=False, null=False, on_delete=models.CASCADE
    )

    @property
    def not_oncall(self):
        return self.type != StatusType.BUDDY

    def __repr__(self) -> str:
        return f"<Status: {self.registrar.username} {self.start}--{self.end} ({StatusType(self.type).name})>"


class LeaveType(models.IntegerChoices):
    ANNUAL = auto(), "Annual"
    EDU = auto(), "Medical education"
    CONF = auto(), "Conference"
    BE = auto(), "Bereavement"
    LIEU = auto(), "Lieu day"
    PARENT = auto(), "Parental"
    SICK = auto(), "Sick"


class Leave(models.Model):
    type = models.IntegerField(choices=LeaveType)
    date = models.DateField("date of leave")
    portion = models.CharField(
        "portion of day",
        max_length=5,
        choices=[("ALL", "All day"), ("AM", "AM"), ("PM", "PM")],
    )
    approved = models.BooleanField(default=False)
    cancelled = models.BooleanField(default=False)
    comment = models.TextField()

    registrar = models.ForeignKey(
        Registrar, blank=False, null=False, on_delete=models.CASCADE
    )
    created = models.DateTimeField(auto_now_add=True)
    last_edited = models.DateTimeField(auto_now=True)

    def __repr__(self) -> str:
        return f"<Leave: {self.registrar.username} {self.date} ({LeaveType(self.type).name})>"


class LeaveApplication(models.Model):
    """
    - Generate printable PDF
    - Triggers an email after creation
    """


class SwapApplication(models.Model):
    pass
