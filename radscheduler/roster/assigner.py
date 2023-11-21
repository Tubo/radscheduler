from datetime import date, timedelta
from random import choice, shuffle

from .models import (
    DetailedShiftType,
    Leave,
    LeaveType,
    NoOneAvailable,
    Registrar,
    Shift,
    ShiftType,
    Status,
    StatusType,
    Weekday,
)
from .rosters import SingleOnCallRoster
from .utils import filter_shifts, find_registrar_from_shifts, sort_shifts_by_date
from .validators import StonzMecaValidator


class AutoAssigner:
    WEEKLY_FATIGUE = 1.65  # Avg on 15 people roster

    def __init__(
        self,
        registrars: list[str],
        unfilled: list[Shift],
        filled: list[Shift] = [],
        leaves: list[Leave] = [],
        statuses: list[Status] = [],
    ):
        self.registrars = registrars
        self.leaves = leaves
        self.statuses = statuses

        self.baseline_fatigue = None
        self.filled = filled
        self.unfilled = unfilled

    def fill_roster(self) -> list[Shift]:
        results: list[Shift] = []
        shifts = self.sort_shifts(self.unfilled)

        for shift in shifts:
            results.append(self._fill_shift(shift, results))

        for idx, shift in enumerate(results):
            shift.input_id = idx

        results = sort_shifts_by_date(results + self.filled)
        return results

    def _fill_shift(self, shift: Shift, results: [Shift]) -> Shift:
        match DetailedShiftType.from_shift(shift):
            case DetailedShiftType.WEEKEND:
                if SingleOnCallRoster.is_start_of_set(shift):
                    # Find the registrar that had RDO 5 days ago
                    # Weekend shifts are special, they are deteremined by the RDO from previous Monday and Tuesday
                    # Find the registrar that had RDO from 5 days ago (Monday),
                    registrar = self.next_registrar(shift, results)
                else:
                    # On Sunday, find the weekend registrar from yesterday
                    registrar = self.same_registrar_yesterday(shift, results)

            case DetailedShiftType.RDO:
                if shift.date.weekday() in [Weekday.MON, Weekday.TUE]:
                    # If it is Monday or Tuesday, then the registrar is the same as last weekend
                    registrar = self.next_weekend_registrar(shift, results)
                elif shift.date.weekday() in [Weekday.THUR, Weekday.FRI]:
                    registrar = self.last_weekend_registrar(shift, results)

            case DetailedShiftType.NIGHT | DetailedShiftType.WEEKEND_NIGHT:
                if SingleOnCallRoster.is_start_of_set(shift):
                    # Start of week day and weekend nights
                    # Simply find next rested registrar
                    registrar = self.next_registrar(shift, results)
                else:  # keep the same registrar as yesterday
                    registrar = self.same_registrar_yesterday(shift, results)

            case DetailedShiftType.SLEEP:
                # Find the registrar that worked nights last weekend
                registrar = self.same_registrar_last_night(shift, results)

            case DetailedShiftType.LONG:
                registrar = self.next_registrar(shift, results)

        shift.registrar = registrar
        return shift

    @classmethod
    def sort_shifts(cls, shifts: [Shift]) -> [Shift]:
        # shifts = shifts[:]
        # shuffle(shifts)
        return sorted(shifts, key=lambda shift: (cls.shift_type_sort_key(shift), shift.date))

    @classmethod
    def shift_type_sort_key(cls, shift: Shift) -> int:
        match DetailedShiftType.from_shift(shift):
            case DetailedShiftType.WEEKEND:
                return 2
            case DetailedShiftType.RDO:
                return 10
            case DetailedShiftType.NIGHT:
                return 1
            case DetailedShiftType.WEEKEND_NIGHT:
                return 1
            case DetailedShiftType.SLEEP:
                return 10
            case DetailedShiftType.LONG:
                return 3

    def next_registrar(self, shift, proposal) -> Registrar:
        """
        Select the next registrar to be rostered on.
        """
        shifts = sort_shifts_by_date(proposal + self.filled)
        registrars = self.registrars_sorted_by_fatigue(shifts, shift)

        for registrar, fatigue in registrars:
            similarly_fatigued_registrars = [(r, f) for r, f in registrars if 0 <= f - fatigue < 2]
            shift_type_numbers = list(
                map(lambda x: self.shift_type_number(x[0], shift, proposal), similarly_fatigued_registrars)
            )
            ranked = sorted(zip(similarly_fatigued_registrars, shift_type_numbers), key=lambda x: x[1])

            for (registrar, _), _ in ranked:
                if self.validate_shift(shift, registrar, proposal):
                    return registrar
            continue

        return None

    def shift_type_number(self, registrar, shift, proposal) -> int:
        result = [
            s
            for s in proposal
            if (s.registrar == registrar) and (DetailedShiftType.from_shift(s) == DetailedShiftType.from_shift(shift))
        ]
        return len(result)

    def same_registrar_yesterday(self, shift, proposal) -> Registrar:
        yesterday = shift.date - timedelta(1)
        shifts = self.filled + proposal
        return find_registrar_from_shifts(shifts, yesterday, shift.type, series=shift.series)

    def same_registrar_last_night(self, shift, proposed_shifts) -> Registrar:
        last_rdo = shift.date - timedelta(3)  # look back 3 days
        shifts = self.filled + proposed_shifts
        registrar = find_registrar_from_shifts(shifts, last_rdo, ShiftType.NIGHT, shift.series)
        return registrar

    def next_weekend_registrar(self, shift, proposal) -> Registrar:
        saturday_delta = 5 - shift.date.weekday()
        next_saturday = shift.date + timedelta(saturday_delta)
        shifts = self.filled + proposal
        return find_registrar_from_shifts(shifts, next_saturday, ShiftType.LONG, series=shift.series)

    def last_weekend_registrar(self, shift, proposal) -> Registrar:
        saturday_delta = abs(5 - shift.date.weekday())  # weekday starts from 0
        saturday = shift.date - timedelta(days=7) + timedelta(saturday_delta)
        shifts = self.filled + proposal
        return find_registrar_from_shifts(shifts, saturday, ShiftType.LONG, series=shift.series)

    def validate_shift(self, shift, registrar, proposal) -> bool:
        shifts = proposal + self.filled
        validator = StonzMecaValidator(shift, registrar, shifts, leaves=self.leaves, statuses=self.statuses)
        return validator.is_valid()

    def registrars_baseline_fatigue(self):
        result = []
        shifts = self.filled
        for registrar in self.registrars:
            total: float = 0
            leave_fatigue = [
                SingleOnCallRoster.leave_fatigue(leave) for leave in self.leaves if leave.registrar == registrar
            ]
            status_fatigue = self.baseline_status_fatigue(
                [status for status in self.statuses if status.registrar == registrar]
            )
            total += sum(leave_fatigue) + sum(status_fatigue)

            shift_fatigue = [
                SingleOnCallRoster.shift_fatigue(shift)
                for shift in shifts
                if (shift.registrar == registrar) and (shift.extra_duty is False)
            ]
            total += sum(shift_fatigue)
            result.append((registrar, total))
        return result

    def baseline_status_fatigue(self, statuses: [Status]) -> [float]:
        if self.unfilled:
            first_shift = self.unfilled[0].date
            last_shift = self.unfilled[-1].date
            total_days = (last_shift - first_shift).days + 1
            result = [SingleOnCallRoster.status_fatigue(status, total_days) for status in statuses]
            return result
        return []

    def registrars_sorted_by_fatigue(self, proposal: [Shift], current: Shift = None) -> [(Registrar, int)]:
        """
        A key function that determines the next registrar to be rostered on.

        1. Calculate the fatigue weighting for each registrar.
        2. Stronger weighting on the last 7 days.
        3. Sort the list by fatigue weighting.
        """
        if not self.baseline_fatigue:
            self.baseline_fatigue = self.registrars_baseline_fatigue()

        result = []
        for registrar, baseline in self.baseline_fatigue:
            shift_fatigue = [
                self.shift_fatigue_with_recency_bias(shift, current)
                for shift in proposal
                if shift.registrar == registrar
            ]
            total = baseline + sum(shift_fatigue)
            result.append((registrar, total))
        result = sorted(result, key=lambda x: x[1])
        return result

    def shift_fatigue_with_recency_bias(self, shift, current_shift):
        fatigue = SingleOnCallRoster.shift_fatigue(shift)

        if current_shift:
            ref_date = current_shift.date
            if abs(shift.date - ref_date) <= timedelta(days=5):
                return fatigue * 35
            elif abs(shift.date - ref_date) <= timedelta(days=7):
                return fatigue * 14
            elif abs(shift.date - ref_date) <= timedelta(days=14):
                return fatigue * 7

        return fatigue
