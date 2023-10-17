from datetime import date, timedelta

from .models import Leave, LeaveType, NoOneAvailable, Registrar, Shift, ShiftType, Status, StatusType, Weekday
from .utils import find_registrar_from_shifts, sort_shifts_by_date
from .validators import StonzMecaValidator


class AutoAssigner:
    WEEKLY_FATIGUE = 1.65  # Avg on 15 people roster

    def __init__(
        self,
        registrars: list[str],
        future_shifts: [Shift],
        prev_shifts: list[Shift] = [],
        leaves: list[Leave] = [],
        statuses: list[Status] = [],
    ):
        self.registrars = registrars
        self.future_shifts = future_shifts
        self.prev_shifts = prev_shifts
        self.leaves = leaves
        self.statuses = statuses

    def fill_roster(self) -> list[Shift]:
        results: list[Shift] = []

        shifts = sorted(self.future_shifts, key=lambda shift: (self.shift_type_sort_key(shift), shift.date))

        for shift in shifts:
            if shift.registrar is not None:
                continue
            results.append(self._fill_shift(shift, results))

        return results

    def _fill_shift(self, shift: Shift, results: [Shift]) -> Shift:
        if shift.type == ShiftType.LONG:
            registrar = self._fill_LONG_shift(shift, results)

        elif shift.type == ShiftType.NIGHT:
            registrar = self._fill_NIGHT_shift(shift, results)

        elif shift.type == ShiftType.RDO:
            registrar = self._fill_RDO_shift(shift, results)

        elif shift.type == ShiftType.SLEEP:
            registrar = self._fill_SLEEP_day(shift, results)

        else:
            raise ValueError("Unknown shift type: " + shift.type)

        shift.registrar = registrar
        return shift

    def _fill_LONG_shift(self, shift, results) -> Registrar:
        if shift.is_weekend:
            if shift.is_start_of_set():
                # Find the registrar that had RDO 5 days ago
                # Weekend shifts are special, they are deteremined by the RDO from previous Monday and Tuesday
                # Find the registrar that had RDO from 5 days ago (Monday),
                registrar = self.same_registrar_last_RDO(shift, results)
            else:
                # On Sunday, find the weekend registrar from yesterday
                registrar = self.same_registrar_yesterday(shift, results)
            return registrar
        else:
            return self.next_registrar(shift, results)

    def _fill_NIGHT_shift(self, shift, results) -> Registrar:
        if shift.is_start_of_set():
            # Start of week day and weekend nights
            # Simply find next rested registrar
            registrar = self.next_registrar(shift, results)
        else:  # keep the same registrar as yesterday
            registrar = self.same_registrar_yesterday(shift, results)
        return registrar

    def _fill_RDO_shift(self, shift, results) -> Registrar:
        if shift.is_start_of_set():
            # Find next rested registrar
            registrar = self.next_registrar(shift, results)

        elif shift.date.weekday() == Weekday.THUR:
            # Find the registrar from last weekend
            registrar = self.last_weekend_registrar(shift, results)

        else:
            registrar = self.same_registrar_yesterday(shift, results)
        return registrar

    def _fill_SLEEP_day(self, shift, results) -> Registrar:
        # Find the registrar that worked nights last weekend
        registrar = self.same_registrar_last_night_shift(shift, results)
        return registrar

    def shift_type_sort_key(self, shift: Shift) -> int:
        """
        Sorts the shifts by type, so that:
        1. Weekend long days and RDOs are rostered first
        2. Weekday nights are rostered second
        3. Weekend nights are rostered third
        4. Sleep days are rostered last
        """
        if shift.type == ShiftType.LONG:
            if shift.is_weekend:
                return 0
            else:
                return 3
        elif shift.type == ShiftType.NIGHT:
            if shift.is_weekend:
                return 2
            else:
                return 1
        elif shift.type == ShiftType.RDO:
            return 0
        else:
            return 10

    def next_registrar(self, shift, proposed_shifts) -> Registrar:
        """
        Select the next registrar to be rostered on.
        """
        shifts = sort_shifts_by_date(proposed_shifts + self.prev_shifts)
        registrars = self.registrars_sorted_by_fatigue(shifts)

        for registrar, _ in registrars:
            if not self.validate_shift(shift, registrar, shifts):
                # Go to next registrar if this one is not valid for this shift
                continue
            return registrar

        raise NoOneAvailable(f"No one available for {shift.type} on {shift.date}")

    def same_registrar_yesterday(self, shift, proposed_shifts) -> Registrar:
        yesterday = shift.date - timedelta(1)
        shifts = self.prev_shifts + proposed_shifts
        return find_registrar_from_shifts(shifts, yesterday, shift.type)

    def same_registrar_last_night_shift(self, shift, proposed_shifts) -> Registrar:
        last_rdo = shift.date - timedelta(3)  # look back 3 days
        shifts = self.prev_shifts + proposed_shifts
        registrar = find_registrar_from_shifts(shifts, last_rdo, ShiftType.NIGHT)
        return registrar

    def same_registrar_last_RDO(self, shift, proposed_shifts) -> Registrar:
        last_rdo = shift.date - timedelta(5)
        shifts = self.prev_shifts + proposed_shifts
        registrar = find_registrar_from_shifts(shifts, last_rdo, ShiftType.RDO)
        return registrar

    def last_weekend_registrar(self, shift, proposed_shifts) -> Registrar:
        delta = abs(shift.date.weekday() + 2)  # weekday starts from 0
        saturday = shift.date - timedelta(delta)
        shifts = self.prev_shifts + proposed_shifts
        return find_registrar_from_shifts(shifts, saturday, ShiftType.LONG)

    def validate_shift(self, shift, registrar, proposed_shifts) -> bool:
        shifts = proposed_shifts + self.prev_shifts
        validator = StonzMecaValidator(shift, registrar, shifts, leaves=self.leaves, statuses=self.statuses)
        return validator.is_valid()

    def registrars_sorted_by_fatigue(self, proposed_shifts: [Shift]) -> [(Registrar, int)]:
        """
        A key function that determines the next registrar to be rostered on.

        1. Calculate the fatigue weighting for each registrar.
        2. Stronger weighting on the last 7 days.
        3. Sort the list by fatigue weighting.
        """
        result = []
        shifts = proposed_shifts + self.prev_shifts
        for registrar in self.registrars:
            total: float = 0
            leave_fatigue = [leave.fatigue_wgt() for leave in self.leaves if leave.registrar == registrar]
            total += sum(leave_fatigue)
            shift_fatigue = [shift.fatigue_wgt() for shift in shifts if shift.registrar == registrar]
            total += sum(shift_fatigue)
            result.append((registrar, total))
        return sorted(result, key=lambda x: x[1])
