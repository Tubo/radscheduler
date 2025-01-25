import dataclasses
from datetime import date
from typing import List, Optional

import dacite
from ninja import Field, ModelSchema, Schema

import radscheduler.core.models as orm
import radscheduler.roster.models as domain

"""
This module provides mapping from Django ORM to the domain models
"""


class RegistrarDomainSchema(ModelSchema):
    id: int = Field(..., alias="pk")
    username: str = Field(..., alias="user.username")

    class Meta:
        model = orm.Registrar
        fields = ["senior", "start", "finish"]


class LeaveDomainSchema(ModelSchema):
    type: domain.LeaveType
    registrar: RegistrarDomainSchema

    class Meta:
        model = orm.Leave
        fields = ["date", "type", "registrar", "no_abutting_weekend"]


class StatusDomainSchema(ModelSchema):
    registrar: RegistrarDomainSchema
    type: domain.StatusType
    weekdays: List[domain.Weekday]
    shift_types: List[domain.ShiftType]

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
