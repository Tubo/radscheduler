import io
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from radscheduler.roster.models import LeaveType

form_dir = Path(__file__).parent / "forms"


@dataclass
class UserInfo:
    last: str  # required
    first: str = ""
    employee_id: str = ""
    contact: str = ""
    position: str = "Registrar"
    rotation: str = "Radiology"
    training_programme: str = "Diagnostic Radiology"
    supervisor: str = "Andrew McLaughlin"
    signature: str = ""
    sign_date: date = date.today()


@dataclass
class Field:
    x: int
    y: int
    width: int = 250
    height: int = 15

    def rect(self):
        return (self.x, self.y, self.x + self.width, self.y + self.height)


@dataclass
class LeaveRow:
    start: date
    end: date
    leave_type: LeaveType
    total_hours: int


@dataclass
class AnnualLeaveForm:
    pdf_path = form_dir / "usual_leaves.pdf"

    header_fields = {
        "last": Field(160, 707),
        "first": Field(425, 707),
        "employee_id": Field(160, 658),
        "contact": Field(425, 658),
        "position": Field(160, 682),
        "rotation": Field(425, 682),
        "signature": Field(115, 360),
        "sign_date": Field(350, 360),
    }

    ROW_X_COLS = {
        "start": 40,
        "end": 115,
        "total_hour": 260,
        "type": 325,
    }
    ROW_LIMIT = 6
    ROW_Y = 530
    ROW_Y_STEP = 20

    @classmethod
    def row_fields(cls, index):
        y = cls.ROW_Y - index * cls.ROW_Y_STEP
        return {
            "start": Field(cls.ROW_X_COLS["start"], y),
            "end": Field(cls.ROW_X_COLS["end"], y),
            "total_hour": Field(cls.ROW_X_COLS["total_hour"], y),
            "type": Field(cls.ROW_X_COLS["type"], y),
        }


@dataclass
class EducationLeaveForm:
    pdf_path = form_dir / "mel_and_conf_leaves.pdf"

    header_fields = {
        "last": Field(170, 740),
        "first": Field(440, 740),
        "position": Field(170, 715),
        "contact": Field(440, 695),
        "rotation": Field(440, 715),
        "training_programme": Field(170, 690),
        "supervisor": Field(440, 690),
        "signature": Field(170, 230),
        "sign_date": Field(460, 230),
    }

    ROW_X_COLS = {
        "start": 48,
        "end": 118,
        "total_hour": 265,
        "type": 325,
    }
    ROW_LIMIT = 2
    ROW_Y = 610
    ROW_Y_STEP = 20

    @classmethod
    def row_fields(cls, index):
        y = cls.ROW_Y - index * cls.ROW_Y_STEP
        return {
            "start": Field(cls.ROW_X_COLS["start"], y),
            "end": Field(cls.ROW_X_COLS["end"], y),
            "total_hour": Field(cls.ROW_X_COLS["total_hour"], y),
            "type": Field(cls.ROW_X_COLS["type"], y),
        }
