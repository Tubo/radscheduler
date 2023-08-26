from datetime import date, timedelta
from dataclasses import dataclass

import holidays

from radscheduler.core.models import (
    Shift,
    ShiftType,
    LeaveType,
    Weekday,
    Registrar,
    Leave,
    Status,
)
from radscheduler.core.validators import (
    OneShiftPerDayValidator,
    NotOnLeaveValidator,
    NotRosteredStatusValidator,
    NoMoreThan2LongDaysIn7Validator,
    NoBackToBackLongDaysValidator,
    NoWeekendAbuttingLeaveValidator,
    EverySecondWeekendFreeValidator,
    validate_roster,
)


canterbury_holidays = holidays.country_holidays("NZ", subdiv="CAN")


@dataclass
class Assignment:
    shift: Shift
    registrar: Registrar


class NoOneAvailable(Exception):
    pass


class NonCompliantRoster(Exception):
    pass


class DefaultRoster:
    """
    This defines the interface for the legacy roster used in 2023.
    """

    WEEKLY_FATIGUE = 1.65  # 15 people roster
    RECENCY_WGT = 1.5

    SHIFT_TYPES = [
        ShiftType.LONG,
        ShiftType.NIGHT,
        ShiftType.RDO,
        ShiftType.SLEEP,
    ]
    STAT_DAY_SHIFTS = [
        ShiftType.LONG,
        ShiftType.NIGHT,
        ShiftType.RDO,
    ]
    STAT_NIGHT_SHIFTS = [
        ShiftType.NIGHT,
    ]
    VALIDATORS = [
        OneShiftPerDayValidator,
        NotOnLeaveValidator,
        NotRosteredStatusValidator,
        NoMoreThan2LongDaysIn7Validator,
        NoBackToBackLongDaysValidator,
        NoWeekendAbuttingLeaveValidator,
        EverySecondWeekendFreeValidator,
    ]

    def __init__(
        self,
        registrars: list[Registrar] = [],
        prev_assignments: list[Assignment] = [],
        leaves: list[Leave] = [],
        statuses: list[Status] = [],
    ):
        self.registrars = registrars
        self.prev_assignments = prev_assignments
        self.leaves = leaves
        self.statuses = statuses

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

        results = [
            mark_stat_day(shift, self.STAT_DAY_SHIFTS, self.STAT_NIGHT_SHIFTS)
            for shift in results
        ]
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

    def fill_roster(self) -> list[Assignment]:
        shifts = self.shifts
        results: list[Assignment] = []

        for shift in shifts:
            if shift.type == ShiftType.LONG:
                registrar = self.fill_LONG_shift(shift, results)

            elif shift.type == ShiftType.NIGHT:
                registrar = self.fill_NIGHT_shift(shift, results)

            elif shift.type == ShiftType.RDO:
                registrar = self.fill_RDO_shift(shift, results)

            elif shift.type == ShiftType.SLEEP:
                registrar = self.fill_SLEEP_day(shift, results)

            else:
                raise ValueError("Unknown shift type")

            results.append(Assignment(shift, registrar))

        if self.validate_proposed_assignment(results):
            return results
        else:
            raise NonCompliantRoster("Non-compliant roster")

    def fill_LONG_shift(self, shift, results) -> Registrar:
        if shift.is_weekend:
            if self.is_start_of_set(shift):
                # Find the registrar that had RDO 5 days ago
                # Weekend shifts are special, they are deteremined by the RDO from previous Monday and Tuesday
                # Find the registrar that had RDO from 5 days ago (Monday),
                registrar = self.same_registrar_last_RDO(shift, results)
            else:
                # On Sunday, find the weekend registrar from yesterday
                registrar = self.same_registrar_yesterday(shift, results)
            return registrar
        else:
            return self.select_next_registrar(shift, results)

    def fill_NIGHT_shift(self, shift, results) -> Registrar:
        if self.is_start_of_set(shift):
            # Start of week day and weekend nights
            # Simply find next rested registrar
            registrar = self.select_next_registrar(shift, results)
        else:  # keep the same registrar as yesterday
            registrar = self.same_registrar_yesterday(shift, results)
        return registrar

    def fill_RDO_shift(self, shift, results) -> Registrar:
        if self.is_start_of_set(shift):
            # Find next rested registrar
            registrar = self.select_next_registrar(shift, results)

        elif shift.date.weekday() == Weekday.THUR:
            # Find the registrar from last weekend
            registrar = self.last_weekend_registrar(shift, results)

        else:
            registrar = self.same_registrar_yesterday(shift, results)
        return registrar

    def fill_SLEEP_day(self, shift, results) -> Registrar:
        # Find the registrar that worked nights last weekend
        registrar = self.same_registrar_last_night_shift(shift, results)
        return registrar

    def select_next_registrar(self, shift, proposed_assignments) -> Registrar:
        """
        Select the next registrar to be rostered on.
        """
        assignments = sort_assignments_by_date(
            proposed_assignments + self.prev_assignments
        )
        registrars = self.registrar_sorted_by_fatigue(assignments, shift.date)

        for idx, (registrar, _) in enumerate(registrars):
            if not self.validate_registrar(shift, registrar, assignments):
                # Go to next registrar if this one is not valid for this shift
                continue

            # Look at the next registrar, just in case they worked less of this shift type
            next_reg = registrars[(idx + 1) % len(registrars)][0]
            if not self.validate_registrar(shift, next_reg, assignments):
                # If the next registrar is not valid, then this registrar is the best choice
                return registrar
            elif compare_shift_counts(registrar, next_reg, shift.type, assignments):
                # If next registrar worked less of this shift type, then this registrar is the best choice
                return next_reg
            else:
                return registrar

        raise NoOneAvailable("No one available")

    def is_start_of_set(self, shift: Shift) -> bool:
        """
        Determines if the shift is the first day of a shift block.

        If NIGHT shift, then Monday and Friday are first days.
        If WEEKEND shift, then Saturday is the first day.
        If RDO shift, then Monday is the first day.
        """
        if shift.type == ShiftType.NIGHT:
            return shift.date.weekday() in [Weekday.MON, Weekday.FRI]
        elif (shift.type == ShiftType.LONG) and shift.is_weekend:
            return shift.date.weekday() == Weekday.SAT
        elif shift.type == ShiftType.RDO:
            return shift.date.weekday() == Weekday.MON
        return False

    def same_registrar_yesterday(self, shift, proposed_assignments) -> Registrar:
        yesterday = shift.date - timedelta(1)

        return find_registrar_from_assignments(
            yesterday,
            shift.type,
            self.prev_assignments + proposed_assignments,
            "No one worked this shift yesterday",
        )

    def same_registrar_last_night_shift(self, shift, proposed_assignments) -> Registrar:
        last_rdo = shift.date - timedelta(3)  # look back 3 days
        registrar = find_registrar_from_assignments(
            last_rdo,
            ShiftType.NIGHT,
            self.prev_assignments + proposed_assignments,
            "No RDO post weekends nights",
        )
        return registrar

    def same_registrar_last_RDO(self, shift, proposed_assignment) -> Registrar:
        last_rdo = shift.date - timedelta(5)
        registrar = find_registrar_from_assignments(
            last_rdo,
            ShiftType.RDO,
            self.prev_assignments + proposed_assignment,
            "No RDO before weekends",
        )
        return registrar

    def last_weekend_registrar(self, shift, proposed_assignments) -> Registrar:
        delta = abs(shift.date.weekday() + 2)  # weekday starts from 0
        saturday = shift.date - timedelta(delta)

        return find_registrar_from_assignments(
            saturday,
            ShiftType.LONG,
            self.prev_assignments + proposed_assignments,
            "No one worked last weekend",
        )

    def validate_registrar(self, shift, registrar, assignments) -> bool:
        return all(
            validator(
                shift,
                registrar,
                assignments,
                leaves=self.leaves,
                statuses=self.statuses,
            ).validate()
            for validator in self.VALIDATORS
        )

    def validate_proposed_assignment(
        self, proposed_assignments: list[Assignment]
    ) -> bool:
        return validate_roster(proposed_assignments, self.leaves, self.statuses)

    def shift_fatigue_wgt(self, assignment: Assignment) -> float:
        """
        Calculates the fatigue weighting for a shift.

        If the shift has a fatigue override, then use that value.

        Otherwise if the shift is a LONG shift, then it is more tiring on Friday.
        If the registrar is not senior, then Wednesday is also more tiring.

        Note: WEEKEND and NIGHT has no fatigue weighting, because their RDOs are counted as shifts.
        """
        shift = assignment.shift
        registrar = assignment.registrar

        if shift.fatigue_override:
            return shift.fatigue_override

        elif shift.stat_day:
            return 2.0

        elif shift.type == ShiftType.LONG:
            if shift.date.weekday() == Weekday.FRI:
                return 1.5
            elif shift.date.weekday() == Weekday.WED and not registrar.senior:
                return 1.5

        return 1.0

    def registrar_sorted_by_fatigue(
        self,
        assignments: list[Assignment],
        until: date,
        recency_length: int = 7,
    ) -> [(Registrar, int)]:
        """
        A key function that determines the next registrar to be rostered on.

        1. Calculate the fatigue weighting for each registrar.
        2. Stronger weighting on the last 7 days.
        3. Sort the list by fatigue weighting.
        """
        result = []
        for registrar in self.registrars:
            total: float = 0

            my_leaves = list(filter(lambda l: l.registrar == registrar, self.leaves))
            total += leave_fatigue_wgt(my_leaves, until, self.WEEKLY_FATIGUE)

            my_statuses = list(
                filter(lambda s: s.registrar == registrar, self.statuses)
            )
            total += status_fatigue_wgt(my_statuses, until, self.WEEKLY_FATIGUE)

            for assignment in assignments:
                if assignment.registrar == registrar:
                    if recency_length and (
                        assignment.shift.date >= until - timedelta(recency_length)
                    ):
                        recency_wgt = self.RECENCY_WGT
                    else:
                        recency_wgt = 1.0
                    total += self.shift_fatigue_wgt(assignment) * recency_wgt

            result.append((registrar, total))

        return sorted(result, key=lambda x: x[1])


def mark_stat_day(
    shift: Shift, day_shifts: [ShiftType], night_shifts: [ShiftType]
) -> Shift:
    """
    Change a shift to a stat day if it falls on a public holiday.
    Public holidays are never on weekends per NZ law.

    If a LONG, WEEKEND, RDO falls on a stat day, it should be a stat day.
    If a NIGHT shift falls starts on or finishes on a stat day, it should be counted.
    Post night sleep day should not be a stat day according to clause 17.4.6
    """
    if (shift.date in canterbury_holidays) and (
        shift.type in day_shifts + night_shifts
    ):
        shift.stat_day = True

    elif shift.type in night_shifts:
        tomorrow = shift.date + timedelta(1)
        if tomorrow in canterbury_holidays:
            shift.stat_day = True

    return shift


def compare_shift_counts(
    current_registrar, next_registrar, shift_type, assignments
) -> bool:
    """
    If the current registrar has more shiftType than the next registrar, then return True.
    """
    current_reg_count = [
        assignment
        for assignment in assignments
        if (assignment.registrar == current_registrar)
        and (assignment.shift.type == shift_type)
    ]
    next_reg_count = [
        assignment
        for assignment in assignments
        if (assignment.registrar == next_registrar)
        and (assignment.shift.type == shift_type)
    ]

    return len(current_reg_count) > len(next_reg_count)


def leave_fatigue_wgt(leaves: list[Leave], until: date, weighting: float) -> float:
    """
    Only parental leave is given fatigue weighting.

    Every 5 day of parental leave is counted as 1 shift.
    """
    parental = list(
        filter(lambda l: (l.type == LeaveType.PARENTAL) and (l.date <= until), leaves)
    )
    return len(parental) / 5 * weighting


def status_fatigue_wgt(statuses: list[Status], until: date, weighting: float) -> float:
    """
    Only non-oncall status is given fatigue weighting.

    Every 7 day of non-oncall status is counted as 1 shift.
    """
    days = 0
    for status in filter(lambda s: s.not_oncall and s.end <= until, statuses):
        days += (status.end - status.start).days + 1
    return days / 7 * weighting


def filter_assignments_by_date_and_shift_type(
    assignments,
    date,
    shift_type,
) -> list[Assignment]:
    return [
        assignment
        for assignment in assignments
        if (assignment.shift.date == date) and (assignment.shift.type == shift_type)
    ]


def find_registrar_from_assignments(date, shift_type, assignments, msg) -> Registrar:
    assignments = filter_assignments_by_date_and_shift_type(
        assignments,
        date,
        shift_type,
    )
    if assignments:
        return assignments[0].registrar
    return None


def sort_assignments_by_date(assignments: list[Assignment]) -> list[Assignment]:
    """
    Sort assignments by date from earliest to latest.
    """
    return sorted(assignments, key=lambda a: a.shift.date)


def shift_to_assignment(shift: Shift, registrar: Registrar) -> Assignment:
    return Assignment(shift, registrar)


def shifts_to_assignments(shifts: list[Shift]) -> list[Assignment]:
    return [
        shift_to_assignment(shift, shift.registrar)
        for shift in shifts
        if shift.registrar
    ]


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)
