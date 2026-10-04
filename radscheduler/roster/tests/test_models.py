from datetime import date

from radscheduler.roster.models import Registrar, Shift, ShiftType, Status, StatusType, Weekday


def test_status_not_oncall():
    registrar = Registrar(username="Waleed", senior=True, start=date(2020, 1, 1))
    mon_long = Shift(date=date(2021, 3, 15), type=ShiftType.LONG, registrar=registrar)
    fri_long = Shift(date=date(2021, 3, 19), type=ShiftType.LONG, registrar=registrar)
    mon_night = Shift(date=date(2021, 3, 15), type=ShiftType.NIGHT, registrar=registrar)
    fri_night = Shift(date=date(2021, 3, 19), type=ShiftType.NIGHT, registrar=registrar)

    # Relievers are not oncall
    status = Status(
        type=StatusType.RELIEVER,
        start=date(2020, 1, 1),
        end=date(2022, 1, 1),
        registrar=registrar,
    )
    assert status.not_oncall(mon_long) is True
    assert status.not_oncall(fri_long) is True
    assert status.not_oncall(mon_night) is True
    assert status.not_oncall(fri_night) is True

    # No long days if part-time on Fridays
    status = Status(
        type=StatusType.PART_TIME,
        start=date(2021, 3, 1),
        end=date(2021, 5, 15),
        registrar=registrar,
        weekdays=[Weekday.FRI],
        shift_types=[ShiftType.LONG],
    )
    assert status.not_oncall(mon_long) is False
    assert status.not_oncall(mon_night) is False
    assert status.not_oncall(fri_night) is False
    assert status.not_oncall(fri_long) is True

    # No night shifts if not allowed
    status = Status(
        type=StatusType.NA,
        start=date(2021, 3, 1),
        end=date(2021, 5, 15),
        registrar=registrar,
        shift_types=[ShiftType.NIGHT],
    )
    assert status.not_oncall(mon_long) is False
    assert status.not_oncall(fri_long) is False
    assert status.not_oncall(mon_night) is True
    assert status.not_oncall(fri_night) is True

    status = Status(
        type=StatusType.PRE_ONCALL,
        start=date(2021, 3, 1),
        end=date(2021, 5, 15),
        registrar=registrar,
    )
    assert status.not_oncall(mon_long) is True
    assert status.not_oncall(fri_long) is True
    assert status.not_oncall(mon_night) is True
    assert status.not_oncall(fri_night) is True
