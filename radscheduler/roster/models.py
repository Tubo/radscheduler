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


class LeaveType(models.IntegerChoices):
    ANNUAL = auto(), "Annual"
    EDU = auto(), "Education"
    CONF = auto(), "Conference"
    BE = auto(), "Bereavement"
    LIEU = auto(), "Lieu day"
    PARENTAL = auto(), "Parental"
    SICK = auto(), "Sick"


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


class StatusType(models.IntegerChoices):
    PRE_ONCALL = auto(), "Pre-oncall"
    RELIEVER = auto(), "Reliever"
    PART_TIME = auto(), "Part time non-working day"
    PRE_EXAM = auto(), "Pre-exam"
    BUDDY = auto(), "Buddy required"
    NA = auto(), "Not available"


@dataclass
class Registrar:
    username: str
    senior: bool


@dataclass
class Shift:
    date: date
    type: ShiftType
    registrar: Registrar = None
    stat_day: bool = False
    fatigue_override: float = 0.0

    @property
    def is_weekend(self) -> bool:
        """Determine if a LONG day shift is on a weekend"""
        if self.type == ShiftType.LONG:
            return self.date.weekday() in [Weekday.SAT, Weekday.SUN]
        elif self.type == ShiftType.NIGHT:
            return self.date.weekday() in [Weekday.FRI, Weekday.SAT, Weekday.SUN]
        return False

    def is_start_of_set(self) -> bool:
        """
        Determines if the shift is the first day of a shift block.

        If NIGHT shift, then Monday and Friday are first days.
        If WEEKEND shift, then Saturday is the first day.
        If RDO shift, then Monday is the first day.
        """
        if self.type == ShiftType.NIGHT:
            return self.date.weekday() in [Weekday.MON, Weekday.FRI]
        elif (self.type == ShiftType.LONG) and self.is_weekend:
            return self.date.weekday() == Weekday.SAT
        elif self.type == ShiftType.RDO:
            return self.date.weekday() == Weekday.MON
        return False

    def fatigue_wgt(self) -> float:
        """
        Calculates the fatigue weighting for a shift.

        If the shift has a fatigue override, then use that value.

        If the shift lands on a stat day, then it has higher fatigue weighting.
        Even if it is a rest day, it would have otherwise been an holiday.

        Otherwise if the shift is a LONG shift, then it is more tiring on Friday.
        If the registrar is not senior, then Wednesday is also more tiring.

        Note: WEEKEND and NIGHT has no fatigue weighting, because their RDOs are counted as shifts.
        """

        if self.fatigue_override:
            return self.fatigue_override
        elif self.stat_day:
            return 2.0
        elif self.type == ShiftType.LONG:
            if self.date.weekday() in [Weekday.FRI, Weekday.WED, Weekday.MON]:
                return 1.5
        return 1.0


@dataclass
class Leave:
    date: date
    type: LeaveType
    registrar: Registrar

    def fatigue_wgt(self, base_wgt=1.0) -> float:
        """
        Only parental leave is given fatigue weighting.

        Every 5 day of parental leave is counted as 1 shift.
        """
        if self.type == LeaveType.PARENTAL:
            return 0.2 * base_wgt
        return 0.0


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
