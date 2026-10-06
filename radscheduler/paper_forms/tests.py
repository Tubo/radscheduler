import io
from datetime import date

from pypdf import PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from radscheduler.core.models import Leave
from radscheduler.roster.models import LeaveType

from .pdf import (
    combine_consecutive_leaves,
    is_consecutive,
    leaves_to_pdf,
    leaves_to_rows,
    remove_stat_and_weekend_days,
    same_user_different_leave_forms,
)


def test_combine_consecutive_leaves(juniors_db):
    leaves = [
        Leave(date=date(2021, 1, 1), type=LeaveType.ANNUAL, registrar=juniors_db[0]),
        Leave(date=date(2021, 1, 4), type=LeaveType.ANNUAL, registrar=juniors_db[0]),
    ]
    result = combine_consecutive_leaves(leaves)
    assert len(result) == 1

    leaves = [
        Leave(date=date(2021, 1, 4), type=LeaveType.ANNUAL, registrar=juniors_db[0]),
        Leave(date=date(2021, 1, 5), type=LeaveType.ANNUAL, registrar=juniors_db[0]),
        Leave(date=date(2021, 1, 6), type=LeaveType.ANNUAL, registrar=juniors_db[0]),
        Leave(date=date(2021, 1, 7), type=LeaveType.ANNUAL, registrar=juniors_db[0]),
        Leave(date=date(2021, 1, 8), type=LeaveType.ANNUAL, registrar=juniors_db[0]),
        Leave(date=date(2021, 1, 11), type=LeaveType.ANNUAL, registrar=juniors_db[0]),
    ]
    result = combine_consecutive_leaves(leaves)
    assert len(result) == 1


def test_is_consecutive():
    monday = date(2021, 1, 4)
    tuesday = date(2021, 1, 5)
    wednesday = date(2021, 1, 6)
    thursday = date(2021, 1, 7)
    friday = date(2021, 1, 8)
    next_mon = date(2021, 1, 11)

    assert is_consecutive(monday, tuesday) is True
    assert is_consecutive(friday, next_mon) is True
    assert is_consecutive(thursday, next_mon) is False
    assert is_consecutive(wednesday, tuesday) is False


def test_leaves_to_rows(juniors_db):
    l1 = Leave(date=date(2021, 1, 1), type=LeaveType.ANNUAL, registrar=juniors_db[0])  # Friday
    l2 = Leave(date=date(2021, 1, 4), type=LeaveType.ANNUAL, registrar=juniors_db[0])  # Monday
    result = leaves_to_rows([l1, l2])
    assert len(result) == 1

    l1 = Leave(date=date(2021, 1, 1), type=LeaveType.ANNUAL, registrar=juniors_db[0])  # Friday
    l2 = Leave(date=date(2021, 1, 5), type=LeaveType.ANNUAL, registrar=juniors_db[0])  # Tuesday
    result = leaves_to_rows([l1, l2])
    assert len(result) == 2


def test_same_user_different_leave_forms(juniors_db):
    l1 = Leave(date=date(2021, 1, 1), type=LeaveType.ANNUAL, registrar=juniors_db[0])  # Friday
    l2 = Leave(date=date(2021, 1, 5), type=LeaveType.ANNUAL, registrar=juniors_db[0])  # Tuesday
    pdf = PdfWriter()
    same_user_different_leave_forms(pdf, Canvas(io.BytesIO(), pagesize=A4), [l1, l2])
    assert len(pdf.pages) == 1

    l3 = Leave(date=date(2021, 1, 6), type=LeaveType.EDU, registrar=juniors_db[0])  # Wednesday
    pdf = PdfWriter()
    same_user_different_leave_forms(pdf, Canvas(io.BytesIO(), pagesize=A4), [l1, l2, l3])
    assert len(pdf.pages) == 2


def test_leaves_to_pdf(juniors_db):
    l1 = Leave(date=date(2021, 1, 1), type=LeaveType.ANNUAL, registrar=juniors_db[0])  # Friday
    pdf = leaves_to_pdf([l1])
    assert len(pdf.pages) == 1

    l2 = Leave(date=date(2021, 1, 1), type=LeaveType.ANNUAL, registrar=juniors_db[1])  # Friday
    pdf = leaves_to_pdf([l1, l2])
    assert len(pdf.pages) == 2


def test_remove_stat_and_weekend_days(juniors_db):
    leaves = [
        Leave(date=date(2023, 11, 18), type=LeaveType.ANNUAL, registrar=juniors_db[0]),  # Saturday
        Leave(date=date(2021, 12, 25), type=LeaveType.ANNUAL, registrar=juniors_db[0]),  # Xmas
    ]
    assert remove_stat_and_weekend_days(leaves) == []
