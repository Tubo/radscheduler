from datetime import date

import radscheduler.core.mapper as mapper
import radscheduler.core.models as db
import radscheduler.roster.models as py


def test_registrar_from_db(juniors_db):
    r_db = juniors_db[0]
    r_py = mapper.registrar_from_db(r_db)
    r = py.Registrar(username=r_db.user.username, senior=False, start=r_db.start)
    assert r_py == r


def test_leave_from_db(juniors_db):
    l_db = db.Leave.objects.create(
        date=date(2021, 1, 1),
        type=py.LeaveType.ANNUAL,
        registrar=juniors_db[0],
    )
    l_py = mapper.leave_from_db(l_db)
    l = py.Leave(
        date=l_db.date,
        type=py.LeaveType(l_db.type),
        registrar=py.Registrar(username=l_db.registrar.user.username, senior=False, start=l_db.registrar.start),
    )
    assert l_py == l


def test_status_from_db(juniors_db):
    s_db = db.Status.objects.create(
        start=date(2021, 1, 1),
        end=date(2021, 1, 2),
        type=py.StatusType.BUDDY,
        registrar=juniors_db[0],
        weekdays=[0, 1, 2, 3, 4, 5, 6],
        shift_types=[py.ShiftType.LONG],
    )
    s_py = mapper.status_from_db(s_db)
    s = py.Status(
        start=s_db.start,
        end=s_db.end,
        type=py.StatusType(py.StatusType.BUDDY),
        registrar=py.Registrar(username=juniors_db[0].user.username, senior=False, start=juniors_db[0].start),
        weekdays=[py.Weekday(x) for x in s_db.weekdays],
        shift_types=[py.ShiftType.LONG],
    )
    assert s_py == s


def test_shift_from_db(juniors_db):
    s_db = db.Shift.objects.create(
        date=date(2021, 1, 1),
        type=py.ShiftType.LONG,
        registrar=juniors_db[0],
    )
    s_py = mapper.shift_from_db(s_db)
    s = py.Shift(
        date=date(2021, 1, 1),
        type=py.ShiftType.LONG,
        registrar=py.Registrar(username=juniors_db[0].user.username, senior=False, start=juniors_db[0].start),
    )
    assert s.same_shift(s_py)
