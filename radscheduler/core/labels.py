"""How the pages name shift, leave and status types: the short labels the compact grids and chips use."""

from radscheduler import roster

# How the compact grids and chips name each type, and the key that adds or changes to each shift type in the editor.
SHIFT_SHORT = {"SWING": "Swing", "HELP": "Help", "LONG": "Long", "RDO": "RDO", "NIGHT": "Night", "SLEEP": "Sleep"}
SHIFT_KEYS = {"SWING": "s", "HELP": "h", "LONG": "l", "RDO": "r", "NIGHT": "n", "SLEEP": "z"}
STATUS_SHORT = {
    "PRECALL": "Pre-call",
    "RELIEVER": "Reliever",
    "PART": "Part-time",
    "PREEXAM": "Exam",
    "BUDDY": "Buddy",
    "NA": "Away",
}
LEAVE_SHORT = {
    "ANNUAL": "AL",
    "EDU": "Edu",
    "CONF": "Conf",
    "LIEU": "Lieu",
    "SICK": "Sick",
    "PAR": "Parental",
    "BE": "Bereav",
}


def type_choices() -> dict:
    """The shift, leave and status types as the Elm pages name them: value, label, short label and key."""
    return {
        "shiftTypes": [
            {"value": value, "label": label, "short": SHIFT_SHORT[value], "key": SHIFT_KEYS[value]}
            for value, label in roster.ShiftType.choices
        ],
        "leaveTypes": [
            {"value": value, "label": label, "short": LEAVE_SHORT[value], "key": ""}
            for value, label in roster.LeaveType.choices
        ],
        "statusTypes": [
            {"value": value, "label": label, "short": STATUS_SHORT[value], "key": ""}
            for value, label in roster.StatusType.choices
        ],
    }
