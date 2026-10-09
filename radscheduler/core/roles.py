"""
Who may decide leave. Two decisions are needed: the chief registrar's ("reg") and the Director of Training's
("dot"). Roles come from groups: the Director of Training makes only their own decision, office staff only
view and print, and other staff (the chief registrars) make both, recording the Director's on their behalf
when asked.
"""

DIRECTOR_OF_TRAINING = "Director of Training"
OFFICE_STAFF = "Office Staff"
ROSTER_MASTER = "Roster master"

APPROVERS = ("reg", "dot")


def leave_approvers(user) -> tuple[str, ...]:
    """The decisions `user` may make, from "reg" and "dot"."""
    if not (user.is_active and user.is_staff):
        return ()
    if user.is_superuser:
        return APPROVERS
    groups = set(user.groups.values_list("name", flat=True))
    if DIRECTOR_OF_TRAINING in groups:
        return ("dot",)
    if OFFICE_STAFF in groups:
        return ()
    return APPROVERS
