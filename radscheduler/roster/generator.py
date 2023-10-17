from datetime import date, timedelta

import holidays

from .models import Shift, ShiftType, Weekday
from .utils import daterange

canterbury_holidays = holidays.country_holidays("NZ", subdiv="CAN")


class SingleOnCallRoster:
    STAT_DAY_SHIFTS = [
        ShiftType.LONG,
        ShiftType.NIGHT,
        ShiftType.RDO,
    ]
    STAT_NIGHT_SHIFTS = [
        ShiftType.NIGHT,
    ]

    def generate_shifts(self, start: date, end: date) -> list[Shift]:
        """
        Generate a list of shifts from Start to End date.
        Public holidys should be stat days.

        This is the roster requirement as of 2023:

        Monday and Tuesday:
        - Long day and night
        - RDO (Pre-weekend)
        - Sleep (Post-weekend)

        Wednesday:
        - Long day and night

        Thursday:
        - Long day and night
        - RDO (Post-weekend)

        Friday:
        - Long day and night
        - Sleep (Post weekday night)
        - RDO (Post-weekend)

        Saturday and Sunday:
        - Long day and night
        - Sleep (Post weekday night)
        """
        self.start, self.end = start, end
        results = []

        for day in daterange(self.start, self.end):
            match day.weekday():
                case Weekday.MON:
                    results.extend(self._gen_monday(day))
                case Weekday.TUE:
                    results.extend(self._gen_tuesday(day))
                case Weekday.WED:
                    results.extend(self._gen_wednesday(day))
                case Weekday.THUR:
                    results.extend(self._gen_thursday(day))
                case Weekday.FRI:
                    results.extend(self._gen_friday(day))
                case Weekday.SAT:
                    results.extend(self._gen_saturday(day))
                case Weekday.SUN:
                    results.extend(self._gen_sunday(day))

        results = [mark_stat_day(shift, self.STAT_DAY_SHIFTS, self.STAT_NIGHT_SHIFTS) for shift in results]
        self.shifts = results
        return results

    def _gen_common_shifts(self, day) -> [Shift]:
        return [
            Shift(date=day, type=ShiftType.LONG),
            Shift(date=day, type=ShiftType.NIGHT),
        ]

    def _gen_monday(self, day) -> [Shift]:
        shifts = self._gen_common_shifts(day)
        shifts.append(Shift(date=day, type=ShiftType.RDO))
        if self.start <= day - timedelta(2):
            shifts.append(Shift(date=day, type=ShiftType.SLEEP))
        return shifts

    def _gen_tuesday(self, day) -> [Shift]:
        return self._gen_monday(day)

    def _gen_wednesday(self, day) -> [Shift]:
        return self._gen_common_shifts(day)

    def _gen_thursday(self, day) -> [Shift]:
        shifts = self._gen_common_shifts(day)
        if self.start <= day - timedelta(5):
            shifts.append(Shift(date=day, type=ShiftType.RDO))
        return shifts

    def _gen_friday(self, day) -> [Shift]:
        shifts = self._gen_common_shifts(day)
        if self.start <= day - timedelta(5):
            shifts.append(Shift(date=day, type=ShiftType.RDO))
        if self.start <= day - timedelta(2):
            shifts.append(Shift(date=day, type=ShiftType.SLEEP))
        return shifts

    def _gen_saturday(self, day) -> [Shift]:
        shifts = self._gen_common_shifts(day)
        if self.start <= day - timedelta(2):
            shifts.append(Shift(date=day, type=ShiftType.SLEEP))
        return shifts

    def _gen_sunday(self, day) -> [Shift]:
        return self._gen_saturday(day)


def mark_stat_day(shift: Shift, day_shifts: [ShiftType], night_shifts: [ShiftType]) -> Shift:
    """
    Change a shift to a stat day if it falls on a public holiday.
    Public holidays are never on weekends per NZ law.

    If a LONG, WEEKEND, RDO falls on a stat day, it should be a stat day.
    If a NIGHT shift falls starts on or finishes on a stat day, it should be counted.
    Post night sleep day should not be a stat day according to clause 17.4.6
    """
    if (shift.date in canterbury_holidays) and (shift.type in day_shifts + night_shifts):
        shift.stat_day = True

    elif shift.type in night_shifts:
        tomorrow = shift.date + timedelta(1)
        if tomorrow in canterbury_holidays:
            shift.stat_day = True

    return shift
