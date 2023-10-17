from datetime import date

from freezegun import freeze_time

from radscheduler.core.models import Leave, Registrar, Shift, Status
from radscheduler.roster.models import ShiftType, StatusType, Weekday


@freeze_time("2023-8-01")
def test_year(db, user):
    r = Registrar(user=user, start=date(2023, 2, 1), finish=date(2024, 12, 1))
    assert r.year == 1

    r = Registrar(user=user, start=date(2019, 12, 1), finish=date(2024, 12, 1))
    assert r.year == 4


class TestStatus:
    def test_weekday_field(self, db, juniors_db):
        reg = juniors_db[2]
        reg.save()

        s = Status.objects.create(
            registrar=reg,
            start=date(2023, 8, 1),
            end=date(2023, 8, 1),
            type=StatusType.PART_TIME,
            weekdays=[Weekday.FRI],
        )
        assert s.type == StatusType.PART_TIME
        assert s.weekdays == [Weekday.FRI]
        assert s.registrar == reg

    def test_shift_type_field(self, db, juniors_db):
        reg = juniors_db[2]
        reg.save()

        s = Status.objects.create(
            registrar=reg,
            start=date(2023, 8, 1),
            end=date(2023, 8, 1),
            type=StatusType.NA,
            shift_types=[ShiftType.NIGHT],
        )
        assert s.type == StatusType.NA
        assert s.weekdays == []
        assert s.shift_types == [ShiftType.NIGHT]
        assert s.registrar == reg


class TestLeave:
    def test_cancelled_leaves_filtered_by_default(self):
        pass
