from datetime import date

from django import template
from django.urls import reverse
from django.utils.dateformat import format as format_date

from radscheduler.core.leave_requests import waiting_count
from radscheduler.core.models import Settings
from radscheduler.core.roles import edits_roster, leave_approvers

register = template.Library()


@register.inclusion_tag("navbar_link.html", takes_context=True)
def nav_link(context, url_name, label, also="", alias="", count=None, count_label=""):
    """
    A navbar link, marked as the current page when the request resolves to ``url_name``
    or to one of the space-separated url names in ``also``.

    Unpoly keeps the mark up to date after it swaps fragments; ``alias`` is its
    ``up-alias`` pattern for the other URLs that count as this page. A ``count`` above nought follows the
    label as a pill, read out with ``count_label`` after it ("3 waiting on you").
    """
    request = context.get("request")
    match = request.resolver_match if request else None
    current = match is not None and match.url_name in {url_name, *also.split()}
    return {
        "href": reverse(url_name),
        "label": label,
        "current": current,
        "alias": alias,
        "count": count,
        "count_label": count_label,
    }


@register.simple_tag(takes_context=True)
def navbar_status(context):
    """
    What the navbar needs beyond its links, for a signed-in user: how far the roster is published, whether
    they build the roster, and how many leave requests wait on their decision (None if they decide none).
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    settings = Settings.objects.first()
    approvers = leave_approvers(user)
    return {
        "published_to": settings and settings.publish_end_date,
        "edits_roster": edits_roster(user),
        "waiting": waiting_count(approvers[0]) if approvers else None,
    }


@register.filter
def short_date(day: date) -> str:
    """A day as "Sun 1 Mar", with the year when it isn't this year: "Sun 1 Mar 2027"."""
    return format_date(day, "D j M" if day.year == date.today().year else "D j M Y")


@register.simple_tag(takes_context=True)
def is_own_profile(context):
    """Whether the request is for the signed-in user's profile or its edit page."""
    request = context.get("request")
    match = request.resolver_match if request else None
    if match is None:
        return False
    if match.view_name == "users:update":
        return True
    return match.view_name == "users:detail" and match.kwargs.get("username") == request.user.username
