from datetime import date

from freezegun import freeze_time
from radscheduler.core.models import Registrar, Shift, Leave


@freeze_time("2023-8-01")
def test_year():
    r = Registrar(username="test", start=date(2023, 2, 1), finish=date(2024, 12, 1))
    assert r.year == 1

    r = Registrar(username="test", start=date(2019, 12, 1), finish=date(2024, 12, 1))
    assert r.year == 4
