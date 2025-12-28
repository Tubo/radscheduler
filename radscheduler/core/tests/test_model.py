from datetime import date

import pytest
from django.db import IntegrityError
from freezegun import freeze_time

from radscheduler.core.models import Leave, Registrar, Shift, Status
from radscheduler.roster.models import ShiftType, StatusType, Weekday

pytestmark = pytest.mark.django_db


class TestRegistrar:
    @freeze_time("2023-8-01")
    def test_year(self, user):
        r = Registrar(user=user, start=date(2023, 2, 1), finish=date(2024, 12, 1))
        assert r.year == 1

        r = Registrar(user=user, start=date(2019, 12, 1), finish=date(2024, 12, 1))
        assert r.year == 4


class TestShift:
    def test_one_shift_per_day(self, juniors_db):
        # Only one type of shift allowed per day, other than extra-duty
        # This may need to be changed in future if double oncall
        pass

    def test_one_shift_per_registrar(self, juniors_db):
        reg = juniors_db[0]
        # TODO: Test that only one shift per day is allowed
        Shift.objects.create(date=date(2023, 8, 1), type=ShiftType.LONG, registrar=reg)
        with pytest.raises(IntegrityError):
            Shift.objects.create(date=date(2023, 8, 1), type=ShiftType.LONG, registrar=reg)


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


class TestSettings:
    def test_singleton_enforced(self):
        # Test that only one Settings instance can be created
        from radscheduler.core.models import Settings

        Settings.objects.create(publish_start_date=date(2023, 1, 1), publish_end_date=date(2023, 12, 31))
        with pytest.raises(IntegrityError):
            Settings.objects.create(publish_start_date=date(2024, 1, 1), publish_end_date=date(2024, 12, 31))
            
    def test_settings_limits_shift_queryset(self, db, juniors_db):
        from radscheduler.core.models import Settings, Shift

        # Create settings that limit published shifts to 2023-06-01 to 2023-06-30
        Settings.objects.create(publish_start_date=date(2023, 6, 1), publish_end_date=date(2023, 6, 30))

        reg = juniors_db[0]
        reg.save()

        # Create shifts on various dates
        Shift.objects.create(date=date(2023, 5, 31), type=ShiftType.LONG, registrar=reg)
        Shift.objects.create(date=date(2023, 6, 15), type=ShiftType.LONG, registrar=reg)
        Shift.objects.create(date=date(2023, 7, 1), type=ShiftType.LONG, registrar=reg)

        # Query shifts using the custom manager
        shifts = Shift.objects.all()

        # Only the shift on 2023-06-15 should be returned
        assert len(shifts) == 1
        assert shifts[0].date == date(2023, 6, 15)