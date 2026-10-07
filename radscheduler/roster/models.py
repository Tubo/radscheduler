from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import IntEnum

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
    EDU = "EDU", "Education"
    CONF = "CONF", "Conference"
    LIEU = "LIEU", "Lieu day"
    SICK = "SICK", "Sick"
    PARENTAL = "PAR", "Parental"
    BE = "BE", "Bereavement"


class ShiftType(models.TextChoices):
    SWING = "SWING", "Swing day"
    HELP = "HELP", "Help desk"
    LONG = "LONG", "Long day"
    RDO = "RDO", "RDO"
    NIGHT = "NIGHT", "Night"
    SLEEP = "SLEEP", "Sleep"


# Start time and length of each shift type that is a period of duty.
# RDO and SLEEP are days off, so they have no hours.
SHIFT_HOURS = {
    ShiftType.SWING: (time(12), timedelta(hours=10)),
    ShiftType.HELP: (time(8), timedelta(hours=4)),
    ShiftType.LONG: (time(8), timedelta(hours=14)),
    ShiftType.NIGHT: (time(22), timedelta(hours=10)),
}


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
    finish: date | None = None
    id: int = None  # if registrar is already in database


@dataclass
class Shift:
    date: date
    type: ShiftType
    registrar: Registrar = None
    stat_day: bool = False
    extra_duty: bool = False
    fatigue_override: float = 0.0
    series: int = 1
    id: int = None  # if shift is already in database

    @property
    def is_weekend(self) -> bool:
        """Determine if a LONG day shift is on a weekend"""
        if self.type == ShiftType.LONG:
            return self.date.weekday() in [Weekday.SAT, Weekday.SUN]
        elif self.type == ShiftType.NIGHT:
            return self.date.weekday() in [Weekday.FRI, Weekday.SAT, Weekday.SUN]
        return False

    @property
    def is_duty(self) -> bool:
        return self.type in SHIFT_HOURS

    @property
    def start(self) -> datetime:
        start_time, _ = SHIFT_HOURS[self.type]
        return datetime.combine(self.date, start_time)

    @property
    def end(self) -> datetime:
        _, length = SHIFT_HOURS[self.type]
        return self.start + length

    @property
    def hours(self) -> float:
        return (self.end - self.start) / timedelta(hours=1)

    def same_shift(self, shift):
        return self.date == shift.date and self.type == shift.type and self.series == shift.series


@dataclass
class Leave:
    date: date
    type: LeaveType
    registrar: Registrar
    no_abutting_weekend: bool = True
    created: datetime | None = None  # when the leave was requested


@dataclass
class Status:
    start: date
    end: date
    type: StatusType
    registrar: Registrar
    weekdays: list[Weekday] = ()
    shift_types: list[ShiftType] = ()

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
