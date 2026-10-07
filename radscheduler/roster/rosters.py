from .models import DetailedShiftType, Weekday


class SingleOnCallRoster:
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
