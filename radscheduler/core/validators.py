from datetime import timedelta, date

from radscheduler.core.models import Weekday, ShiftType, StatusType, Shift


def group_shifts_by_date(shifts: list[Shift]) -> dict[date, list[Shift]]:
    """
    Group shifts by date
    """
    results = {}
    for shift in shifts:
        if shift.date not in results:
            results[shift.date] = []
        results[shift.date].append(shift)
    return results


class Validator:
    def __init__(self, shift, registrar, assignments, **kwargs) -> None:
        self.registrar = registrar
        self.shift = shift
        self.assignments = assignments
        self.leaves = kwargs.get("leaves", [])
        self.statuses = kwargs.get("statuses", [])

    @property
    def my_assignments(self):
        return [a for a in self.assignments if a.registrar == self.registrar]

    @property
    def my_leaves(self):
        return [l for l in self.leaves if l.registrar == self.registrar]

    @property
    def my_statuses(self):
        return [s for s in self.statuses if s.registrar == self.registrar]

    def validate(self):
        return False


def validate_roster(assignments, leaves, statuses):
    registrars = set(a.registrar.username for a in assignments)

    for registrar in registrars:
        shifts = [
            assignment.shift
            for assignment in filter(lambda a: a.registrar == registrar, assignments)
        ]
        leaves = list(filter(lambda l: l.registrar == registrar, leaves))
        statuses = list(filter(lambda s: s.registrar == registrar, statuses))

        groupby_date = group_shifts_by_date(shifts)
        for date, shifts in groupby_date.items():
            if len(shifts) > 1:
                assert (
                    False
                ), f"{registrar} cannot work more than 1 shift per day: {shifts}"

        working_days = [
            shift.date
            for shift in shifts
            if shift.type in [ShiftType.LONG, ShiftType.NIGHT, ShiftType.WEEKEND]
        ]
        for i in range(len(working_days) - 7):
            if len(working_days[i : i + 7]) >= 2:
                assert False, f"{registrar} cannot work more than 2 shifts in 7 days"

        for leave in leaves:
            shifts = list(filter(lambda s: (s.date == leave.date), shifts))
            assert (
                shifts == []
            ), f"{registrar} cannot work {shifts} while on leave {leave}"

        for leave in leaves:
            if leave.date.weekday() == Weekday.MON:
                shifts = list(
                    filter(
                        lambda a: (
                            date - timedelta(2) <= a.shift.date <= date - timedelta(1)
                        ),
                        shifts,
                    )
                )
                assert (
                    shifts == []
                ), f"{registrar} cannot work on weekends abutting leave"

        for status in statuses:
            if status.type == StatusType.BUDDY:
                continue
            shifts = filter(
                lambda shift: (status.start <= shift.date <= status.end), shifts
            )
            assert list(shifts) == [], f"{registrar} cannot work while on {status}"

    return True


class OneShiftPerDayValidator(Validator):
    def validate(self):
        """
        Return False if a registrar was placed on two shifts on a same day.
        """
        same_date = [a for a in self.my_assignments if a.shift.date == self.shift.date]
        return len(same_date) == 0


class NotOnLeaveValidator(Validator):
    def validate(self):
        """
        Return False if a registrar was placed on a shift while on leave.
        """
        leaves_on_this_day = [l for l in self.my_leaves if l.date == self.shift.date]
        return len(leaves_on_this_day) == 0


class NotRosteredStatusValidator(Validator):
    def validate(self):
        """
        Return False if a registrar has a no_roster status.
        """
        no_roster = [
            s
            for s in self.my_statuses
            if s.not_oncall and (s.start <= self.shift.date <= s.end)
        ]
        return len(no_roster) == 0


class NoMoreThan2LongDaysIn7Validator(Validator):
    def validate(self):
        """
        17.2.2 RMOs shall not be rostered on duty for more than 2 long days in 7.
        For the purposes of this clause, a “long day” shall be a duty where in excess of 10 hours are worked.
        """
        last_7_days = [
            a
            for a in self.my_assignments
            if (self.shift.date - timedelta(7) <= a.shift.date)
        ]
        return len(last_7_days) < 2


class NoBackToBackLongDaysValidator(Validator):
    def validate(self):
        """
        A registrar should not be placed on a long day if they worked a long day the day before.

        Nights and weekends are special cases that will be handled separately.
        """
        prev_day = [
            a
            for a in self.my_assignments
            if (a.shift.date == self.shift.date - timedelta(1))
        ]
        return len(prev_day) == 0


class NoWeekendAbuttingLeaveValidator(Validator):
    def validate(self):
        """
        21.4.1 When an RMO is on annual leave on the days immediately before or after a weekend,
        she/he cannot be required to work the weekend(s).

        - Friday long is not considered a weekend shift, but a Friday night shift is part of a weekend.
        - Lieu days are not considered in this clause
        """
        if self.shift.type == ShiftType.WRDO:
            # This is a Monday WRDO
            assert self.shift.date.weekday() == Weekday.MON, "Must be a Monday WRDO"
            # Other shifts are deteremined by the shift generation algorithm
            leaves_next_fri_or_mon = [
                l
                for l in self.my_leaves
                if (l.date == self.shift.date + timedelta(4))
                or (l.date == self.shift.date + timedelta(7))
            ]
            return leaves_next_fri_or_mon == []

        elif self.shift.type == ShiftType.NIGHT:
            if self.shift.date.weekday() == Weekday.MON:
                # Monday night is handled by validate_not_on_leave
                pass
            elif self.shift.date.weekday() == Weekday.FRI:
                # Cannot work this weekend night if on leave on Monday
                leaves_next_mon = [
                    l
                    for l in self.my_leaves
                    if (l.date == self.shift.date + timedelta(3))
                ]
                return leaves_next_mon == []
        return True


class EverySecondWeekendFreeValidator(Validator):
    def validate(self):
        """
        17.3.5 Employees shall have, as a minimum, every second weekend completely free from duty.
        """
        if self.shift.date.weekday() in [Weekday.SAT, Weekday.SUN]:
            last_weekend = [
                a
                for a in self.my_assignments
                if a.shift.date == self.shift.date - timedelta(7)
            ]
            return len(last_weekend) == 0
        return True


def shift_validate_post_night_RDOs(shift, registrar, assignments, *args, **kwargs):
    """
    17.4.6 Employees working three-night duties or less shall be given a minimum break of the
    calendar day upon which the employee ceased the last night duty plus a further one
    calendar day free from rostered duty.

    In other words:
    - Weekend nights = Fri, Sat, Sun RDOs
    - Weekdays nights = Mon, Tues RDOs

    This has been built into the shift generation algorithm already.
    """


def leave_validate_lieu_day_notice():
    """
    24.1 Lieu days must be applied
    - 14 days before regular day
    - 28 days before long day, weekends or nights
    - within 12 months
    """
