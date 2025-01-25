from datetime import date

from dacite import from_dict

import radscheduler.core.domain_mapper as domain_mapper
import radscheduler.core.models as orm
import radscheduler.roster.models as domain


def test_registrar_from_db(juniors_db):
    reg_in_db = juniors_db[0]
    mapped = domain_mapper.RegistrarDomainSchema.from_orm(reg_in_db).dict()
    reg_in_domain = domain.Registrar(
        username=reg_in_db.user.username, senior=False, start=reg_in_db.start, id=reg_in_db.pk
    )
    assert from_dict(domain.Registrar, mapped) == reg_in_domain


def test_leave_from_db(juniors_db):
    leave_in_db = orm.Leave.objects.create(
        date=date(2021, 1, 1),
        type=domain.LeaveType.ANNUAL,
        registrar=juniors_db[0],
    )
    mapped = domain_mapper.LeaveDomainSchema.from_orm(leave_in_db).dict()
    leave_in_domain = domain.Leave(
        date=leave_in_db.date,
        type=domain.LeaveType(leave_in_db.type),
        registrar=domain.Registrar(
            username=leave_in_db.registrar.user.username,
            senior=False,
            start=leave_in_db.registrar.start,
            id=juniors_db[0].pk,
        ),
    )
    assert from_dict(domain.Leave, mapped) == leave_in_domain


def test_status_from_db(juniors_db):
    status_in_db = orm.Status.objects.create(
        start=date(2021, 1, 1),
        end=date(2021, 1, 2),
        type=domain.StatusType.BUDDY,
        registrar=juniors_db[0],
        weekdays=[0, 1, 2, 3, 4, 5, 6],
        shift_types=[domain.ShiftType.LONG],
    )
    mapped = domain_mapper.StatusDomainSchema.from_orm(status_in_db).dict()
    registrar_in_domain = domain.Registrar(
        username=juniors_db[0].user.username, senior=False, start=juniors_db[0].start, id=juniors_db[0].pk
    )
    status_in_domain = domain.Status(
        start=status_in_db.start,
        end=status_in_db.end,
        type=domain.StatusType(domain.StatusType.BUDDY),
        registrar=registrar_in_domain,
        weekdays=[domain.Weekday(x) for x in status_in_db.weekdays],
        shift_types=[domain.ShiftType.LONG],
    )
    assert from_dict(domain.Status, mapped) == status_in_domain


def test_shift_from_db(juniors_db):
    shift_in_db = orm.Shift.objects.create(
        date=date(2021, 1, 1),
        type=domain.ShiftType.LONG,
        registrar=juniors_db[0],
    )
    mapped = domain_mapper.ShiftDomainSchema.from_orm(shift_in_db).dict()
    registrar_in_domain = domain.Registrar(
        username=juniors_db[0].user.username, senior=False, start=juniors_db[0].start, id=juniors_db[0].pk
    )
    shift_in_domain = domain.Shift(
        id=shift_in_db.pk,
        date=date(2021, 1, 1),
        type=domain.ShiftType.LONG,
        registrar=registrar_in_domain,
    )
    assert from_dict(domain.Shift, mapped) == shift_in_domain


def test_shift_to_db(juniors_db):
    registrar_in_domain = domain.Registrar(
        username=juniors_db[0].user.username, senior=False, start=juniors_db[0].start, id=juniors_db[0].pk
    )
    shift_in_domain = domain.Shift(
        date=date(2021, 1, 1),
        type=domain.ShiftType.LONG,
        registrar=registrar_in_domain,
    )
    shift_in_db = domain_mapper.shift_to_db(shift_in_domain)
    assert shift_in_db.registrar_id == juniors_db[0].pk
