from .models import DetailedShiftType, LeaveType, Shift, ShiftType, Weekday


class SingleOnCallRoster:
    COMMON = ((ShiftType.LONG, 1), (ShiftType.NIGHT, 1))

    MON = (*COMMON, (ShiftType.SLEEP, 1), (ShiftType.RDO, 1))
    TUE = (*COMMON, (ShiftType.SLEEP, 1), (ShiftType.RDO, 1))
    WED = COMMON
    THUR = (*COMMON, (ShiftType.RDO, 1))
    FRI = (*COMMON, (ShiftType.SLEEP, 1), (ShiftType.RDO, 1))
    SAT = (*COMMON, (ShiftType.SLEEP, 1))
    SUN = (*COMMON, (ShiftType.SLEEP, 1))

    STAT_DAY_SHIFTS = [
        ShiftType.LONG,
        ShiftType.NIGHT,
        ShiftType.RDO,
    ]
    STAT_NIGHT_SHIFTS = [
        ShiftType.NIGHT,
    ]

    @staticmethod
    def is_start_of_set(shift) -> bool:
        """
        Determines if the shift is the first day of a shift block.

        If NIGHT shift, then Monday and Friday are first days.
        If WEEKEND shift, then Saturday is the first day.
        If RDO shift, then Monday is the first day.
        """
        match DetailedShiftType.from_shift(shift):
            case DetailedShiftType.WEEKEND:
                return shift.date.weekday() == Weekday.SAT
            case DetailedShiftType.RDO:
                return shift.date.weekday() == Weekday.MON
            case DetailedShiftType.NIGHT:
                return shift.date.weekday() == Weekday.MON
            case DetailedShiftType.WEEKEND_NIGHT:
                return shift.date.weekday() == Weekday.FRI
            case DetailedShiftType.LONG:
                return False

    @staticmethod
    def shift_fatigue(shift) -> float:
        """
        Calculates the fatigue weighting for a shift.

        If the shift has a fatigue override, then use that value.

        If the shift lands on a stat day, then it has higher fatigue weighting.
        Even if it is a rest day, it would have otherwise been an holiday.

        Otherwise if the shift is a LONG shift, then it is more tiring on Friday.
        If the registrar is not senior, then Wednesday is also more tiring.
        """

        if shift.fatigue_override:
            return shift.fatigue_override
        elif shift.stat_day:
            return 2.0

        match DetailedShiftType.from_shift(shift):
            case DetailedShiftType.WEEKEND:
                return 2.0
            case DetailedShiftType.RDO:
                return 0
            case DetailedShiftType.NIGHT:
                return 7 / 4  # 4 shifts + 3 sleeps
            case DetailedShiftType.WEEKEND_NIGHT:
                return 5 / 3  # 3 shifts + 2 sleeps
            case DetailedShiftType.SLEEP:
                return 0
            case DetailedShiftType.LONG:
                if shift.date.weekday() in [Weekday.WED, Weekday.FRI]:
                    return 1.5
                return 1.25

    def leave_fatigue(leave, base_wgt=1.0) -> float:
        """
        Only parental leave is given fatigue weighting.

        Every 5 day of parental leave is counted as 1 shift.
        """
        if leave.type == LeaveType.PARENTAL:
            return 0.2 * base_wgt
        return 0.0

    def status_fatigue(status, roster_span, base_wgt=1.0) -> float:
        status_span = (status.end - status.start).days
        if status_span < roster_span:
            return 0.2 * status_span * base_wgt
        else:
            return 0.2 * roster_span * base_wgt
