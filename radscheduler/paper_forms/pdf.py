import io
from datetime import date, timedelta
from itertools import groupby
from math import ceil

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText

from radscheduler.core.models import Leave
from radscheduler.roster.models import LeaveType

from .forms import AnnualLeaveForm, EducationLeaveForm, LeaveRow, UserInfo


def is_consecutive(before, after):
    if before.weekday() >= 4:
        return before + timedelta(days=3) == after
    return before + timedelta(days=1) == after


def combine_consecutive_leaves(leaves) -> [[Leave]]:
    """
    Combine consecutive leave dates into start and end dates.
    Weekends are skipped.

    If they are not consecutive, then they are in a different group.

    LEAVES are sorted by date and are of same type and portion.
    """
    rows = [[]]
    for leave in leaves:
        group = rows[-1]
        if group:
            last_leave = group[-1]
            if is_consecutive(last_leave.date, leave.date):
                group.append(leave)
                continue
            rows.append([leave])
        else:
            group.append(leave)
    return rows


def leaves_to_row(leaves) -> LeaveRow:
    """
    Convert a list of leaves into a row.
    """
    if not leaves:
        return None

    start = leaves[0].date
    end = leaves[-1].date
    leave_type = leaves[0].type
    portion = leaves[0].portion
    total_hours = 8 * len(leaves) if portion == "ALL" else 4 * len(leaves)
    row = LeaveRow(start=start, end=end, leave_type=leave_type, total_hours=total_hours)
    return row


def leaves_to_rows(leaves) -> [[LeaveRow]]:
    """
    Leaves to be written on the same form.
    Combine them to a row if they are consecutive and of same type and portion.

    All leaves are from the same user. Not required to be sorted.

    Returns a list of list of Leaves.
    """
    sorted_leaves = sorted(leaves, key=lambda leave: leave.date)
    all_day_leaves = [leave for leave in sorted_leaves if leave.portion == "ALL"]
    other_leaves = [[leave] for leave in sorted_leaves if leave.portion != "ALL"]

    combined_leaves = [list(group) for _, group in groupby(all_day_leaves, key=lambda leave: leave.type)]
    consecutive_groups = []
    for group in combined_leaves + other_leaves:
        consecutive_groups += combine_consecutive_leaves(group)
    result = [leaves_to_row(group) for group in consecutive_groups if group]
    return result


def fill_header(pdf, page, fields, user):
    if " " in user.name:
        last, first = user.name.split(" ", 1)
    else:
        last = user.name
        first = ""

    user_info = UserInfo(
        last=last,
        first=first,
        employee_id=user.employee_number if user.employee_number else "",
        contact=user.phone if user.phone else "",
        signature=user.name if user.name else "",
    )

    for field_name, field in fields.items():
        annotation = FreeText(
            text=getattr(user_info, field_name),
            rect=field.rect(),
            font="Arial",
            font_size="12pt",
        )
        pdf.add_annotation(page_number=page, annotation=annotation)


def fill_row(pdf, page_number, row_number, form_class, row):
    start = FreeText(
        text=row.start,
        rect=form_class.row_fields(row_number)["start"].rect(),
        font="Arial",
        font_size="12pt",
    )
    end = FreeText(
        text=row.end,
        rect=form_class.row_fields(row_number)["end"].rect(),
        font="Arial",
        font_size="12pt",
    )
    total_hours = FreeText(
        text=row.total_hours,
        rect=form_class.row_fields(row_number)["total_hour"].rect(),
        font="Arial",
        font_size="12pt",
    )
    leave_type = FreeText(
        text=row.leave_type,
        rect=form_class.row_fields(row_number)["type"].rect(),
        font="Arial",
        font_size="12pt",
    )
    pdf.add_annotation(page_number=page_number, annotation=start)
    pdf.add_annotation(page_number=page_number, annotation=end)
    pdf.add_annotation(page_number=page_number, annotation=total_hours)
    pdf.add_annotation(page_number=page_number, annotation=leave_type)


def same_user_same_leave_type(pdf, form_class, leaves):
    if not leaves:
        return pdf

    user = leaves[0].registrar.user
    rows = leaves_to_rows(leaves)
    init_page_num = len(pdf.pages)
    # new_page_num = ceil(len(rows) / form_class.ROW_LIMIT)

    form_path = form_class.pdf_path
    form = PdfReader(form_path).pages[0]

    rows_per_page = [rows[i : i + form_class.ROW_LIMIT] for i in range(0, len(rows), form_class.ROW_LIMIT)]
    for rel_page_number, rows in enumerate(rows_per_page):
        page_number = init_page_num + rel_page_number
        pdf.add_page(form)
        fill_header(pdf, page_number, form_class.header_fields, user)
        for row_number, row in enumerate(rows):
            fill_row(pdf, page_number, row_number, form_class, row)

    # for page_number in range(init_page_num, init_page_num + new_page_num):
    #     pdf.add_page(form)
    #     fill_header(pdf, page_number, form_class.header_fields, user)
    #     for row_number in range(form_class.ROW_LIMIT):
    #         try:
    #             row = rows[page_number * form_class.ROW_LIMIT + row_number]
    #             fill_row(pdf, page_number, row_number, form_class, row)
    #         except IndexError:
    #             break
    return pdf


def dispatch_form(leave_type):
    if leave_type in [LeaveType.ANNUAL, LeaveType.BE, LeaveType.LIEU, LeaveType.SICK]:
        return AnnualLeaveForm
    elif leave_type in [LeaveType.EDU, LeaveType.CONF]:
        return EducationLeaveForm


def same_user_different_leave_forms(pdf, leaves):
    """
    Append a list of leaves of different types from a single user into the given PDF.
    """
    leaves = sorted(leaves, key=lambda leave: leave.type)
    groups = groupby(leaves, key=lambda leave: leave.type)

    for leave_type, leaves in groups:
        leaves = list(leaves)
        form_class = dispatch_form(leave_type)
        same_user_same_leave_type(pdf, form_class, leaves)

    return pdf


def leaves_to_pdf(leaves):
    leaves = sorted(leaves, key=lambda leave: leave.registrar.id)
    leaves_grouped_by_registrars = [list(leaves) for _, leaves in groupby(leaves, key=lambda leave: leave.registrar)]
    pdf = PdfWriter()
    for leaves in leaves_grouped_by_registrars:
        same_user_different_leave_forms(pdf, leaves)
    return pdf


def leaves_to_buffer(leaves: [Leave]):
    """
    Converts a list of leaves from different users into a single PDF.

    The leaves are sorted by registrar.
    """
    buffer = io.BytesIO()
    pdf = leaves_to_pdf(leaves)
    pdf.write(buffer)
    buffer.seek(0)
    return buffer
