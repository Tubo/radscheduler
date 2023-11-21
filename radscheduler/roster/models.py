from dataclasses import dataclass
from datetime import date
from enum import Enum, IntEnum, auto

from django.db import models


class Weekday(IntEnum):
    MON = 0
    TUE = 1
    WED = 2
    THUR = 3
    FRI = 4
    SAT = 5
    SUN = 6


class LeaveType(models.TextChoices):
    ANNUAL = "ANNUAL", "Annual"
    BE = "BE", "Bereavement"
    LIEU = "LIEU", "Lieu day"
    SICK = "SICK", "Sick"
    PARENTAL = "PAR", "Parental"
    EDU = "EDU", "Education"
    CONF = "CONF", "Conference"


class ShiftType(models.TextChoices):
    LONG = "LONG", "Long day"  # from 8am to 10pm
    NIGHT = "NIGHT", "Night"  # from 10pm to 8am
    RDO = "RDO", "RDO"
    SLEEP = "SLEEP", "Sleep"


class DetailedShiftType(models.TextChoices):
    LONG = "LONG", "Long day"  # from 8am to 10pm
    WEEKEND = "WEEKEND", "Weekend long day"  # from 8am to 10pm
    NIGHT = "NIGHT", "Night"  # from 10pm to 8am
    WEEKEND_NIGHT = "WEEKEND_NIGHT", "Weekend night"  # from 10pm to 8am
    RDO = "RDO", "RDO"
    SLEEP = "SLEEP", "Sleep"

    @classmethod
    def from_shift(cls, shift: "Shift"):
        if shift.type == ShiftType.LONG:
            if shift.is_weekend:
                return cls.WEEKEND
            else:
                return cls.LONG
        elif shift.type == ShiftType.NIGHT:
            if shift.is_weekend:
                return cls.WEEKEND_NIGHT
            else:
                return cls.NIGHT
        elif shift.type == ShiftType.RDO:
            return cls.RDO
        elif shift.type == ShiftType.SLEEP:
            return cls.SLEEP


class StatusType(models.TextChoices):
    PRE_ONCALL = "PRECALL", "Pre-oncall"
    RELIEVER = "RELIEVER", "Reliever"
    PART_TIME = "PART", "Part time non-working day"
    PRE_EXAM = "PREEXAM", "Pre-exam"
    BUDDY = "BUDDY", "Buddy required"
    NA = "NA", "Not available"


@dataclass
class Registrar:
    username: str
    senior: bool
    start: date
    finish: date = None


@dataclass
class Shift:
    date: date
    type: ShiftType
    registrar: Registrar = None
    stat_day: bool = False
    extra_duty: bool = False
    fatigue_override: float = 0.0
    series: int = 1
    pk: int = None  # if shift is already in database

    @property
    def is_weekend(self) -> bool:
        """Determine if a LONG day shift is on a weekend"""
        if self.type == ShiftType.LONG:
            return self.date.weekday() in [Weekday.SAT, Weekday.SUN]
        elif self.type == ShiftType.NIGHT:
            return self.date.weekday() in [Weekday.FRI, Weekday.SAT, Weekday.SUN]
        return False

    def same_shift(self, shift):
        return self.date == shift.date and self.type == shift.type and self.series == shift.series


@dataclass
class Leave:
    date: date
    type: LeaveType
    registrar: Registrar


@dataclass
class Status:
    start: date
    end: date
    type: StatusType
    registrar: Registrar
    weekdays: list[Weekday] = tuple()
    shift_types: list[ShiftType] = tuple()

    def not_oncall(self, shift: Shift) -> bool:
        if self.type == StatusType.BUDDY:
            return False

        weekdays = self.weekdays if self.weekdays else [Weekday(x) for x in range(0, 7)]
        shift_types = self.shift_types if self.shift_types else [ShiftType(x) for x in ShiftType]

        if shift.date.weekday() in weekdays and shift.type in shift_types:
            return True
        return False


class NoOneAvailable(Exception):
    pass


class NonCompliantRoster(Exception):
    pass
