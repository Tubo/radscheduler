import io
from datetime import date, timedelta
from itertools import groupby
from math import ceil

import reportlab.pdfgen.canvas as pdf_canvas
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4

from radscheduler.core.models import Leave
from radscheduler.roster import canterbury_holidays
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

    start = leaves[0].date.strftime("%d/%m/%Y")
    end = leaves[-1].date.strftime("%d/%m/%Y")
    leave_type = leaves[0].type
    portion = leaves[0].portion
    total_hours = str(8 * len(leaves) if portion == "ALL" else 4 * len(leaves))
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


annotation_config = {
    "font": "Arial",
    "font_size": "12pt",
    "border_color": None,
    "background_color": None,
}


def fill_header(canvas, fields, user):
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
        canvas.drawString(field.x, field.y, getattr(user_info, field_name))


def fill_row(canvas, row_number, form_class, row):
    canvas.drawString(
        form_class.row_fields(row_number)["start"].x,
        form_class.row_fields(row_number)["start"].y,
        row.start,
    )
    canvas.drawString(
        form_class.row_fields(row_number)["end"].x,
        form_class.row_fields(row_number)["end"].y,
        row.end,
    )
    canvas.drawString(
        form_class.row_fields(row_number)["total_hour"].x,
        form_class.row_fields(row_number)["total_hour"].y,
        row.total_hours,
    )
    canvas.drawString(
        form_class.row_fields(row_number)["type"].x,
        form_class.row_fields(row_number)["type"].y,
        row.leave_type,
    )


def add_stamp(canvas):
    # rect = (10, 10, 200, 50)
    # annotation = FreeText(
    #     text="Registrar approved\nDirector of Training approved",
    #     rect=rect,
    #     font="Times",
    #     font_size="16pt",
    #     border_color="#FF0000",
    # )
    # rectange = Rectangle(rect)
    # pdf.add_annotation(page_number=page_number, annotation=rectange)
    # pdf.add_annotation(page_number=page_number, annotation=annotation)
    pass


def same_user_same_leave_type(pdf, overlay, form_class, leaves):
    if not leaves:
        return

    user = leaves[0].registrar.user
    rows = leaves_to_rows(leaves)

    form_path = form_class.pdf_path
    form = PdfReader(form_path).pages[0]

    rows_per_page = [rows[i : i + form_class.ROW_LIMIT] for i in range(0, len(rows), form_class.ROW_LIMIT)]
    for rel_page_number, rows in enumerate(rows_per_page):
        fill_header(overlay, form_class.header_fields, user)
        for row_number, row in enumerate(rows):
            fill_row(overlay, row_number, form_class, row)
        add_stamp(overlay)
        overlay.showPage()
        pdf.add_page(form)


def dispatch_form(leave_type):
    if leave_type in [LeaveType.ANNUAL, LeaveType.BE, LeaveType.LIEU, LeaveType.SICK]:
        return AnnualLeaveForm
    elif leave_type in [LeaveType.EDU, LeaveType.CONF]:
        return EducationLeaveForm


def same_user_different_leave_forms(pdf, overlay, leaves):
    """
    Append a list of leaves of different types from a single user into the given PDF.
    """
    leaves = sorted(leaves, key=lambda leave: leave.type)
    groups = groupby(leaves, key=lambda leave: leave.type)

    for leave_type, leaves in groups:
        leaves = list(leaves)
        form_class = dispatch_form(leave_type)
        same_user_same_leave_type(pdf, overlay, form_class, leaves)


def leaves_to_pdf(leaves):
    leaves = sorted(leaves, key=lambda leave: leave.registrar.id)
    leaves_grouped_by_registrars = [list(leaves) for _, leaves in groupby(leaves, key=lambda leave: leave.registrar)]

    pdf = PdfWriter()
    canvas_buffer = io.BytesIO()
    canvas = pdf_canvas.Canvas(canvas_buffer, pagesize=A4)

    for leaves in leaves_grouped_by_registrars:
        same_user_different_leave_forms(pdf, canvas, leaves)

    canvas.save()
    canvas_buffer.seek(0)

    overlay = PdfReader(canvas_buffer)
    for page_num, page in enumerate(pdf.pages):
        page.merge_page(overlay.pages[page_num], over=True)
    return pdf


def remove_stat_and_weekend_days(leaves):
    return [leave for leave in leaves if leave.date.weekday() < 5 and leave.date not in canterbury_holidays]


def leaves_to_buffer(leaves: [Leave]):
    """
    Converts a list of leaves from different users into a single PDF.

    The leaves are sorted by registrar.
    """
    buffer = io.BytesIO()
    leaves = remove_stat_and_weekend_days(leaves)
    pdf = leaves_to_pdf(leaves)
    pdf.write(buffer)
    buffer.seek(0)
    return buffer
