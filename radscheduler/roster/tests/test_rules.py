"""
Each test names the rule and clause it covers. Dates are January 2023:

    Mon  2   9  16  23
    Tue  3  10  17  24
    Wed  4  11  18  25
    Thu  5  12  19  26
    Fri  6  13  20  27
    Sat  7  14  21  28
    Sun  8  15  22  29
"""

from dataclasses import replace
from datetime import date, datetime
from functools import partial

from radscheduler.roster.models import (
    Contract,
    Leave,
    LeaveType,
    Registrar,
    Shift,
    ShiftType,
    Status,
    StatusType,
    Weekday,
)
from radscheduler.roster.rules import RDA, STONZ, Timeline, check_roster, infer_ordinary_days, max_hours, weekend_of

ALICE = Registrar("alice", senior=False, start=date(2022, 1, 1))
BOB = Registrar("bob", senior=False, start=date(2022, 1, 1))
RAY = Registrar("ray", senior=False, start=date(2022, 1, 1), contract=Contract.RDA)


def jan(day):
    return date(2023, 1, day)


def shifts(shift_type, *days, registrar=ALICE):
    return [Shift(date=jan(day), type=shift_type, registrar=registrar) for day in days]


def longs(*days, **kwargs):
    return shifts(ShiftType.LONG, *days, **kwargs)


def nights(*days, **kwargs):
    return shifts(ShiftType.NIGHT, *days, **kwargs)


def sleeps(*days, **kwargs):
    return shifts(ShiftType.SLEEP, *days, **kwargs)


def rdos(*days, **kwargs):
    return shifts(ShiftType.RDO, *days, **kwargs)


def retag(roster, registrar):
    return [replace(shift, registrar=registrar) for shift in roster]


def leave(day, leave_type=LeaveType.ANNUAL, **kwargs):
    return Leave(date=jan(day), type=leave_type, registrar=ALICE, **kwargs)


def found(rule, roster, leaves=(), statuses=(), period=None, clause=None):
    violations = check_roster(roster, leaves, statuses, period=period)
    return [v for v in violations if v.rule == rule and (clause is None or v.clause == clause)]


def dates(violations):
    return [[d.day for d in v.dates] for v in violations]


def test_shift_hours():
    night = Shift(date=jan(2), type=ShiftType.NIGHT)
    assert night.start == datetime(2023, 1, 2, 22)
    assert night.end == datetime(2023, 1, 3, 8)
    assert night.hours == 10
    assert Shift(date=jan(2), type=ShiftType.LONG).hours == 14
    assert not Shift(date=jan(2), type=ShiftType.RDO).is_duty


def test_weekend_starts_after_friday_day_duty():
    assert weekend_of(longs(6)[0]) is None
    assert weekend_of(nights(6)[0]) == jan(7)
    assert weekend_of(longs(7)[0]) == jan(7)
    assert weekend_of(nights(8)[0]) == jan(7)
    assert weekend_of(longs(9)[0]) is None


def test_ordinary_days_fill_weekdays_without_shifts_or_leave():
    part_time = Status(start=jan(1), end=jan(31), type=StatusType.PART_TIME, registrar=ALICE, weekdays=[Weekday.WED])
    leaver = Registrar("alice", senior=False, start=jan(1), finish=jan(9))
    timeline = Timeline(leaver, longs(5), leaves=[leave(6)], statuses=[part_time])
    # 2 and 3 Jan are public holidays, 4 Jan part-time, 5 Jan rostered, 6 Jan on leave, and she leaves after 9 Jan
    [monday] = infer_ordinary_days(timeline, jan(1), jan(15))
    assert monday.date == jan(9)
    assert monday.hours == 9


def test_help_desk_morning_continues_into_ordinary_work():
    [afternoon] = infer_ordinary_days(Timeline(ALICE, shifts(ShiftType.HELP, 11)), jan(11), jan(11))
    assert (afternoon.start, afternoon.end) == (datetime(2023, 1, 11, 12), datetime(2023, 1, 11, 17))

    # A help desk day is still one duty, and four ordinary days plus it is 45 hours
    roster = shifts(ShiftType.HELP, 11)
    period = (jan(9), jan(13))
    assert found("one_duty_per_day", roster, period=period) == []
    assert found("min_break_between_duties", roster, period=period) == []
    [violation] = check_roster(roster, period=period, rules=[partial(max_hours, limit=44, days=7, clause="test")])
    assert "Up to 45 hours" in violation.message


def test_half_day_leave_shortens_the_ordinary_day():
    def ordinary(portion):
        timeline = Timeline(ALICE, [], leaves=[leave(11, portion=portion)])
        return [(d.from_time.hour, d.to_time.hour) for d in infer_ordinary_days(timeline, jan(11), jan(11))]

    assert ordinary("AM") == [(12, 17)]
    assert ordinary("PM") == [(8, 12)]
    assert ordinary("ALL") == []


def test_weekday_long_day_includes_the_ordinary_day():
    # Ordinary 8-5 then on until 10pm is one 14-hour duty, not an ordinary day plus a long day
    roster = longs(11)
    period = (jan(9), jan(13))
    assert found("one_duty_per_day", roster, period=period) == []
    assert found("min_break_between_duties", roster, period=period) == []
    assert roster[0].hours == 14

    # Four ordinary days and the long day: 4 x 9 + 14 = 50 hours
    [violation] = check_roster(roster, period=period, rules=[partial(max_hours, limit=49, days=7, clause="test")])
    assert "Up to 50 hours" in violation.message


def test_max_hours_stonz_17_1_2():
    period = (jan(2), jan(22))
    # A week of ordinary days and a weekend of long days is 73 hours
    [violation] = found("max_hours", longs(14, 15), period=period, clause="STONZ 17.1.2")
    assert "Up to 73 hours" in violation.message

    # An RDO on the Friday before and the Monday after brings every 7 days to 64 hours or less
    assert found("max_hours", longs(14, 15) + rdos(13, 16), period=period, clause="STONZ 17.1.2") == []


def test_max_hours_stonz_17_1_4():
    # Ten ordinary days and four weekend long days are 146 hours in 14 days
    [violation] = found("max_hours", longs(14, 15, 21, 22), period=(jan(9), jan(22)), clause="STONZ 17.1.4")
    assert "the limit is 140" in violation.message


def test_max_consecutive_days_stonz_17_3_1():
    # Weekdays from 9 Jan with the weekend between are 12 days in a row
    period = (jan(9), jan(22))
    assert found("max_consecutive_days", longs(14, 15), period=period) == []

    [violation] = found("max_consecutive_days", longs(14, 15, 21), period=period)
    assert violation.clause == "STONZ 17.3.1"
    assert "13 days in a row" in violation.message


def test_one_duty_per_day_stonz_17_2_5():
    roster = longs(4) + shifts(ShiftType.SWING, 4)
    [violation] = found("one_duty_per_day", roster)
    assert violation.clause == "STONZ 17.2.5"
    assert dates([violation]) == [[4]]

    # A night ending on the morning the next night starts is allowed
    assert found("one_duty_per_day", nights(2, 3, 4, 5)) == []


def test_max_long_days_stonz_17_2_2():
    [violation] = found("max_long_days", longs(12, 14, 15))
    assert violation.clause == "STONZ 17.2.2"
    assert dates([violation]) == [[12, 14, 15]]

    # 7 Jan and 14 Jan are 7 days apart, so never in the same 7-day window
    assert found("max_long_days", longs(7, 8, 14)) == []

    # Nights are exactly 10 hours, so they are not long days
    assert found("max_long_days", nights(2, 3, 4, 5)) == []

    # Four long days in one window are reported once
    assert dates(found("max_long_days", longs(2, 4, 6, 8))) == [[2, 4, 6, 8]]


def test_every_second_weekend_free_stonz_17_3_5():
    [violation] = found("every_second_weekend_free", longs(7, 8, 14, 15))
    assert violation.clause == "STONZ 17.3.5"
    assert dates([violation]) == [[7, 14]]

    assert found("every_second_weekend_free", longs(7, 8, 21, 22)) == []

    # A Friday night belongs to the weekend; a Friday long day does not
    assert len(found("every_second_weekend_free", longs(7) + nights(13))) == 1
    assert found("every_second_weekend_free", longs(7) + longs(13)) == []


def test_min_break_between_duties_stonz_17_4_2():
    [violation] = found("min_break_between_duties", nights(2) + shifts(ShiftType.SWING, 3))
    assert violation.clause == "STONZ 17.4.2"
    assert "Only 4 hours off" in violation.message

    assert len(found("min_break_between_duties", nights(2) + longs(3))) == 1

    # Two duties on one day are reported by one_duty_per_day only
    assert found("min_break_between_duties", longs(4) + shifts(ShiftType.SWING, 4)) == []

    # A long day ends at 10pm, so 10 hours off before the next one
    assert found("min_break_between_duties", longs(2) + shifts(ShiftType.LONG, 3)) == []


def test_post_night_recovery_stonz_17_4_6():
    # Four nights end Fri 6: Friday, Saturday and Sunday must be free
    weekday_nights = nights(2, 3, 4, 5) + sleeps(6)
    [violation] = found("post_night_recovery", weekday_nights + longs(7))
    assert violation.clause == "STONZ 17.4.6"
    assert dates([violation]) == [[7]]
    assert len(found("post_night_recovery", weekday_nights + longs(8))) == 1
    assert found("post_night_recovery", weekday_nights + longs(9)) == []

    # Without a sleep day, Friday is an ordinary working day
    assert dates(found("post_night_recovery", nights(2, 3, 4, 5), period=(jan(2), jan(8)))) == [[6]]

    # Three nights end Mon 9: Monday and Tuesday must be free
    weekend_nights = nights(6, 7, 8) + sleeps(9)
    assert dates(found("post_night_recovery", weekend_nights + longs(10))) == [[10]]
    assert found("post_night_recovery", weekend_nights + rdos(10) + longs(11)) == []


def test_no_weekend_next_to_leave_stonz_21_4():
    # Leave on Monday 9 rules out the weekend before it, including Friday night
    [violation] = found("no_weekend_next_to_leave", nights(6) + longs(7, 8), [leave(9)])
    assert violation.clause == "STONZ 21.4"
    assert dates([violation]) == [[6, 7, 8]]
    assert found("no_weekend_next_to_leave", longs(6), [leave(9)]) == []

    # Leave on Friday 13 rules out the weekend after it
    assert len(found("no_weekend_next_to_leave", longs(14), [leave(13)])) == 1

    # 21.4.3: after leave ending on the Friday, the Sunday night is allowed; not before Monday leave
    assert found("no_weekend_next_to_leave", nights(15), [leave(13)]) == []
    assert len(found("no_weekend_next_to_leave", nights(15), [leave(16)])) == 1

    # A half day counts only when it touches the weekend: Friday afternoon or Monday morning
    assert len(found("no_weekend_next_to_leave", longs(14), [leave(13, portion="PM")])) == 1
    assert found("no_weekend_next_to_leave", longs(14), [leave(13, portion="AM")]) == []
    assert len(found("no_weekend_next_to_leave", longs(14), [leave(16, portion="AM")])) == 1
    assert found("no_weekend_next_to_leave", longs(14), [leave(16, portion="PM")]) == []

    # 21.4.5: lieu days don't count, and leave can be marked as allowing an abutting weekend
    assert found("no_weekend_next_to_leave", longs(7), [leave(9, LeaveType.LIEU)]) == []
    assert found("no_weekend_next_to_leave", longs(7), [leave(9, no_abutting_weekend=False)]) == []


def test_lieu_day_notice_stonz_24_1():
    requested = datetime(2023, 1, 1, 9)

    [violation] = found("lieu_day_notice", longs(2), [leave(10, LeaveType.LIEU, created=requested)])
    assert violation.clause == "STONZ 24.1"
    assert "needs 14 days' notice" in violation.message

    assert found("lieu_day_notice", longs(2), [leave(25, LeaveType.LIEU, created=requested)]) == []

    # 28 days if rostered on a long day, night or weekend duty that day
    [violation] = found("lieu_day_notice", longs(25), [leave(25, LeaveType.LIEU, created=requested)])
    assert "needs 28 days' notice" in violation.message

    # Annual leave and leave without a request date are not checked
    assert found("lieu_day_notice", longs(2), [leave(10, created=requested)]) == []
    assert found("lieu_day_notice", longs(2), [leave(10, LeaveType.LIEU)]) == []


def test_employed():
    starter = Registrar("carol", senior=False, start=jan(10), finish=jan(20))
    roster = longs(9, 12, 23, registrar=starter)
    assert dates(found("employed", roster)) == [[9, 23]]


def test_not_on_leave():
    assert len(found("not_on_leave", longs(4), [leave(4)])) == 1
    # A night ending on the morning of the leave overlaps it
    assert len(found("not_on_leave", nights(3), [leave(4)])) == 1
    assert found("not_on_leave", longs(3, 5), [leave(4)]) == []
    # Days off aren't duties
    assert found("not_on_leave", shifts(ShiftType.RDO, 4), [leave(4)]) == []

    # Half-day leave only clashes with duties in its half
    assert found("not_on_leave", shifts(ShiftType.SWING, 11), [leave(11, portion="AM")]) == []
    assert found("not_on_leave", nights(10), [leave(11, portion="AM")]) == []
    assert found("not_on_leave", nights(11), [leave(11, portion="PM")]) == []
    assert len(found("not_on_leave", longs(11), [leave(11, portion="PM")])) == 1
    assert len(found("not_on_leave", shifts(ShiftType.HELP, 11), [leave(11, portion="AM")])) == 1


def test_status_allows_duty():
    reliever = Status(start=jan(1), end=jan(31), type=StatusType.RELIEVER, registrar=ALICE)
    [violation] = found("status_allows_duty", longs(4), statuses=[reliever])
    assert violation.message == "Rostered while reliever."

    part_time = Status(
        start=jan(1),
        end=jan(31),
        type=StatusType.PART_TIME,
        registrar=ALICE,
        weekdays=[Weekday.FRI],
        shift_types=[ShiftType.LONG],
    )
    assert dates(found("status_allows_duty", longs(6) + nights(13), statuses=[part_time])) == [[6]]


def test_no_back_to_back_long_days():
    assert dates(found("no_back_to_back_long_days", longs(5, 6))) == [[5, 6]]
    assert found("no_back_to_back_long_days", longs(7, 8)) == []
    assert dates(found("no_back_to_back_long_days", longs(8, 9))) == [[8, 9]]


def test_no_long_day_before_weekend_nights():
    assert dates(found("no_long_day_before_weekend_nights", longs(9) + nights(13, 14, 15))) == [[9]]
    assert found("no_long_day_before_weekend_nights", longs(2) + nights(13, 14, 15)) == []
    assert found("no_long_day_before_weekend_nights", longs(9) + nights(16, 17, 18, 19)) == []


def test_compliant_roster_has_no_violations():
    roster = nights(2, 3, 4, 5) + sleeps(6) + rdos(13) + longs(14, 15) + rdos(16) + longs(23)
    roster += longs(2, 4, registrar=BOB) + nights(13, 14, 15, registrar=BOB) + sleeps(16, registrar=BOB)
    roster += rdos(17, registrar=BOB)
    assert check_roster(roster, [leave(18)]) == []


def test_check_roster_ignores_unassigned_shifts_and_separates_registrars():
    roster = longs(4) + longs(4, registrar=BOB) + [Shift(date=jan(4), type=ShiftType.NIGHT)]
    assert check_roster(roster) == []

    violation = check_roster(longs(4, 5, registrar=BOB))[0]
    assert violation.registrar == BOB
    assert violation.dates == (jan(4), jan(5))


def test_rda_covers_the_same_rules_as_stonz():
    assert [rule.func for rule in RDA] == [rule.func for rule in STONZ]
    assert all(rule.keywords["clause"].startswith("RDA ") for rule in RDA)


def test_each_registrar_is_checked_against_their_contract():
    roster = longs(12, 14, 15) + longs(12, 14, 15, registrar=RAY)
    clauses = {(v.registrar.username, v.clause) for v in check_roster(roster) if v.rule == "max_long_days"}
    assert clauses == {("alice", "STONZ 17.2.2"), ("ray", "RDA 13.4.8")}


def test_post_night_recovery_rda_13_4_7():
    # RDA sets no extra rest after fewer than 5 nights, where STONZ needs two days after four
    four_nights = nights(2, 3, 4, 5) + sleeps(6) + longs(7)
    assert found("post_night_recovery", four_nights) != []
    assert [v for v in check_roster(retag(four_nights, RAY)) if v.rule == "post_night_recovery"] == []

    # Five nights end Sat 7: Saturday, Sunday and Monday must be free
    five_nights = nights(2, 3, 4, 5, 6, registrar=RAY)
    [violation] = [v for v in check_roster(five_nights + longs(9, registrar=RAY)) if v.rule == "post_night_recovery"]
    assert violation.clause == "RDA 13.4.7"
    assert dates([violation]) == [[9]]
    roster = five_nights + sleeps(9, registrar=RAY) + longs(10, registrar=RAY)
    assert [v for v in check_roster(roster) if v.rule == "post_night_recovery"] == []
