"""
This module provides mapping from Django ORM to the domain models
"""

import dacite
from ninja import Field, ModelSchema

import radscheduler.core.models as orm
import radscheduler.roster.models as domain


class RegistrarDomainSchema(ModelSchema):
    id: int = Field(..., alias="pk")
    username: str = Field(..., alias="user.username")
    contract: domain.Contract

    class Meta:
        model = orm.Registrar
        fields = ["senior", "start", "finish", "contract"]


class LeaveDomainSchema(ModelSchema):
    type: domain.LeaveType
    registrar: RegistrarDomainSchema

    class Meta:
        model = orm.Leave
        fields = ["date", "type", "registrar", "no_abutting_weekend", "created", "portion"]


class StatusDomainSchema(ModelSchema):
    registrar: RegistrarDomainSchema
    type: domain.StatusType
    weekdays: list[domain.Weekday]
    shift_types: list[domain.ShiftType]

    class Meta:
        model = orm.Status
        fields = ["registrar", "type", "weekdays", "shift_types", "start", "end"]


class ShiftDomainSchema(ModelSchema):
    id: int = Field(..., alias="pk")
    type: domain.ShiftType
    registrar: RegistrarDomainSchema

    class Meta:
        model = orm.Shift
        fields = ["date", "type", "registrar", "stat_day", "extra_duty", "fatigue_override", "series"]


class ShiftOrmSchema(ModelSchema):
    type: domain.ShiftType
    registrar_id: int = Field(None, alias="registrar.id")

    class Meta:
        model = orm.Shift
        fields = ["date", "type", "stat_day", "extra_duty", "fatigue_override", "series"]
        optional_fields = ["registrar"]


def shift_to_db(shift: domain.Shift):
    return orm.Shift(
        registrar_id=shift.registrar.id,
        date=shift.date,
        type=shift.type.value,
        stat_day=shift.stat_day,
        extra_duty=shift.extra_duty,
        fatigue_override=shift.fatigue_override,
        series=shift.series,
    )


def shift_from_db(shift: orm.Shift):
    return dacite.from_dict(domain.Shift, ShiftDomainSchema.from_orm(shift).dict())


def registrar_from_db(registrar: orm.Registrar):
    return dacite.from_dict(domain.Registrar, RegistrarDomainSchema.from_orm(registrar).dict())


def leave_from_db(leave: orm.Leave):
    return dacite.from_dict(domain.Leave, LeaveDomainSchema.from_orm(leave).dict())


def status_from_db(status: orm.Leave):
    return dacite.from_dict(domain.Status, StatusDomainSchema.from_orm(status).dict())


def roster_from_db(shifts, leaves, statuses):
    """
    Domain shifts, leave and statuses from querysets, for checking a roster. Builds the dataclasses straight
    from the rows, sharing one Registrar per person: the schema-based converters above validate every row,
    which made checking the editor's weeks several times slower.
    """
    registrars = {}

    def registrar(pk):
        return registrars[pk]

    shift_rows = list(
        shifts.values_list(
            "pk", "date", "type", "registrar_id", "stat_day", "extra_duty", "fatigue_override", "series"
        )
    )
    leave_rows = list(leaves.values_list("date", "type", "registrar_id", "no_abutting_weekend", "created", "portion"))
    status_rows = list(statuses.values_list("registrar_id", "type", "weekdays", "shift_types", "start", "end"))

    ids = {row[3] for row in shift_rows} | {row[2] for row in leave_rows} | {row[0] for row in status_rows}
    for pk, username, senior, start, finish, contract in orm.Registrar.objects.filter(pk__in=ids).values_list(
        "pk", "user__username", "senior", "start", "finish", "contract"
    ):
        registrars[pk] = domain.Registrar(username, senior, start, finish, pk, domain.Contract(contract))

    return (
        [
            domain.Shift(day, domain.ShiftType(kind), registrar(rid), stat, extra, fatigue, series, pk)
            for pk, day, kind, rid, stat, extra, fatigue, series in shift_rows
        ],
        [
            domain.Leave(day, domain.LeaveType(kind), registrar(rid), abutting, created, portion)
            for day, kind, rid, abutting, created, portion in leave_rows
        ],
        [
            domain.Status(
                start,
                end,
                domain.StatusType(kind),
                registrar(rid),
                [domain.Weekday(d) for d in weekdays],
                [domain.ShiftType(t) for t in shift_types],
            )
            for rid, kind, weekdays, shift_types, start, end in status_rows
        ],
    )


def shift_to_dict(shift):
    return {
        "date": str(shift.date),
        "type": domain.ShiftType(shift.type).label,
        "registrar": shift.registrar.pk if shift.registrar else None,
        "username": shift.registrar.user.username if shift.registrar else None,
        "extra_duty": shift.extra_duty,
    }


def leave_to_dict(leave):
    return {
        "date": str(leave.date),
        "type": domain.LeaveType(leave.type).label,
        "registrar": leave.registrar.pk if leave.registrar else None,
        "portion": leave.portion,
    }


def status_to_dict(status):
    return {
        "start": str(status.start),
        "end": str(status.end),
        "type": domain.StatusType(status.type).label,
        "registrar": status.registrar.pk,
        "weekdays": status.weekdays,
        "shift_types": status.shift_types,
    }
