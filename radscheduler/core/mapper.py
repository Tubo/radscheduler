import radscheduler.core.models as db
import radscheduler.roster.models as py


def registrar_from_db(registrar):
    if registrar is None:
        return None

    r = py.Registrar(
        username=registrar.user.username,
        senior=registrar.senior,
        start=registrar.start,
        finish=registrar.finish,
        pk=registrar.pk,
    )
    return r


def leave_from_db(leave):
    l = py.Leave(
        date=leave.date,
        type=py.LeaveType(leave.type),
        registrar=registrar_from_db(leave.registrar),
        no_abutting_weekend=leave.no_abutting_weekend,
    )
    return l


def status_from_db(status):
    s = py.Status(
        registrar=registrar_from_db(status.registrar),
        type=py.StatusType(status.type),
        start=status.start,
        end=status.end,
        weekdays=[py.Weekday(weekday) for weekday in status.weekdays],
        shift_types=[py.ShiftType(shift_type) for shift_type in status.shift_types],
    )
    return s


def shift_from_db(shift):
    s = py.Shift(
        date=shift.date,
        type=py.ShiftType(shift.type),
        registrar=registrar_from_db(shift.registrar),
        stat_day=shift.stat_day,
        extra_duty=shift.extra_duty,
        fatigue_override=shift.fatigue_override,
        series=shift.series,
        pk=shift.pk,
    )
    return s


def shift_to_db(shift):
    s = db.Shift(
        registrar_id=shift.registrar.pk,
        date=shift.date,
        type=shift.type.value,
        stat_day=shift.stat_day,
        extra_duty=shift.extra_duty,
        fatigue_override=shift.fatigue_override,
        series=shift.series,
    )
    return s


def shift_to_dict(shift):
    return {
        "date": str(shift.date),
        "type": py.ShiftType(shift.type).label,
        "registrar": shift.registrar.pk if shift.registrar else None,
        "username": shift.registrar.user.username if shift.registrar else None,
        "extra_duty": shift.extra_duty,
    }


def leave_to_dict(leave):
    return {
        "date": str(leave.date),
        "type": py.LeaveType(leave.type).label,
        "registrar": leave.registrar.pk if leave.registrar else None,
        "portion": leave.portion,
    }


def status_to_dict(status):
    return {
        "start": str(status.start),
        "end": str(status.end),
        "type": py.StatusType(status.type).label,
        "registrar": status.registrar.pk,
        "weekdays": status.weekdays,
        "shift_types": status.shift_types,
    }
