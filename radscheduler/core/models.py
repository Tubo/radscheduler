from datetime import date

from django.contrib.postgres.fields import ArrayField
from django.db import models

from radscheduler import roster
from radscheduler.users.models import User


class ShiftManager(models.Manager):
    def get_queryset(self):
        try:
            settings = Settings.objects.first()
            if settings:
                return (
                    super()
                    .get_queryset()
                    .filter(date__gte=settings.publish_start_date, date__lte=settings.publish_end_date)
                )
        except Settings.DoesNotExist:
            pass
        return super().get_queryset()


class Registrar(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    senior = models.BooleanField(default=False)
    start = models.DateField("start date", help_text="Date started training")
    finish = models.DateField("finish date", null=True, blank=True, help_text="Date finished training")
    created = models.DateTimeField(auto_now_add=True)
    last_edited = models.DateTimeField(auto_now=True)

    def __repr__(self) -> str:
        return f"<Registrar: {self.user.username}>"

    def __str__(self) -> str:
        return self.user.username

    @property
    def year(self):
        if self.start is None:
            return None

        return ((date.today() - self.start).days // 365) + 1


class Shift(models.Model):
    objects = ShiftManager()
    all_objects = models.Manager()  # Use this to get all shifts regardless of publication date

    date = models.DateField("shift date")
    type = models.CharField("shift type", max_length=10, choices=roster.ShiftType.choices)
    registrar = models.ForeignKey(Registrar, blank=True, null=True, on_delete=models.CASCADE)
    stat_day = models.BooleanField(default=False)
    extra_duty = models.BooleanField(default=False)
    fatigue_override = models.FloatField(default=0.0)
    series = models.IntegerField(default=1)

    created = models.DateTimeField(auto_now_add=True)
    last_edited = models.DateTimeField(auto_now=True)

    def __repr__(self) -> str:
        if self.registrar:
            registrar = self.registrar.user.username
        else:
            registrar = "N/A"
        return f"<{roster.ShiftType(self.type).name} Shift {self.date} ({roster.Weekday(self.date.weekday()).name}): {registrar}>"


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
    type = models.CharField(choices=roster.StatusType.choices, max_length=10)
    registrar = models.ForeignKey(Registrar, blank=False, null=False, on_delete=models.CASCADE)
    weekdays = ArrayField(
        models.IntegerField(choices=[(x.value, x.name) for x in roster.Weekday]),
        default=list,
        size=7,
        blank=True,
    )
    shift_types = ArrayField(
        models.CharField(max_length=10, choices=roster.ShiftType.choices),
        default=list,
        blank=True,
    )
    comment = models.TextField(blank=True)

    created = models.DateTimeField(auto_now_add=True)
    last_edited = models.DateTimeField(auto_now=True)

    def __repr__(self) -> str:
        return f"<Status: {self.registrar} {self.start}--{self.end} ({roster.StatusType(self.type).label})>"

    class Meta:
        verbose_name_plural = "statuses"


class Leave(models.Model):
    registrar = models.ForeignKey(Registrar, blank=False, null=False, on_delete=models.CASCADE)
    date = models.DateField("date of leave")
    type = models.CharField(choices=roster.LeaveType.choices, max_length=10)
    portion = models.CharField(
        "portion of day",
        choices=[("ALL", "All day"), ("AM", "AM"), ("PM", "PM")],
        default="ALL",
        max_length=5,
    )
    comment = models.TextField(blank=True)
    no_abutting_weekend = models.BooleanField(default=True)

    reg_approved = models.BooleanField(null=True, blank=True)
    dot_approved = models.BooleanField(null=True, blank=True)
    printed = models.BooleanField(default=False)
    microster = models.BooleanField(default=False)
    cancelled = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    last_edited = models.DateTimeField(auto_now=True)

    def __repr__(self) -> str:
        return f"<Leave: {self.registrar.user.username} {self.date} ({roster.LeaveType(self.type).name})>"

    def __str__(self):
        return f"{self.type} {self.portion}" if self.portion != "ALL" else self.type

    def is_past(self):
        return self.date < date.today()

    def is_approved(self):
        return True if self.reg_approved and self.dot_approved else False

    def is_declined(self):
        return self.reg_approved is False or self.dot_approved is False

    def is_pending(self):
        if self.cancelled:
            return False
        elif self.reg_approved and self.dot_approved:
            return False
        elif self.reg_approved is False or self.dot_approved is False:
            return False
        else:
            return True

    class Meta:
        unique_together = ["date", "registrar"]


class ShiftInterest(models.Model):
    """
    Expression of interst to a shift.

    This is used for tracking registrars who are interested in an Extra Duty shift.
    """

    shift = models.ForeignKey(Shift, blank=False, null=False, on_delete=models.CASCADE, related_name="interests")
    registrar = models.ForeignKey(Registrar, blank=False, null=False, on_delete=models.CASCADE)
    comment = models.TextField(blank=True)

    created = models.DateTimeField(auto_now_add=True)
    last_edited = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["shift", "registrar"]
        verbose_name_plural = "shift interests"


class Settings(models.Model):
    """
    Global settings for the application.
    """

    publish_start_date = models.DateField(
        "publish start date", help_text="Shifts and leaves before this date will not be displayed"
    )
    publish_end_date = models.DateField(
        "publish end date", help_text="Shifts and leaves after this date will not be displayed"
    )

    # Enforce a true singleton at the database level.
    # Any attempt to create a second Settings row will violate this unique constraint.
    singleton_id = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    last_edited = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Settings ({self.publish_start_date} - {self.publish_end_date})"

    class Meta:
        verbose_name_plural = "settings"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(publish_start_date__lte=models.F("publish_end_date")),
                name="valid_date_range",
            )
        ]
