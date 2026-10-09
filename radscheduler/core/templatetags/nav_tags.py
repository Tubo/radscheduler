from django import template
from django.urls import reverse

register = template.Library()


@register.inclusion_tag("navbar_link.html", takes_context=True)
def nav_link(context, url_name, label, also="", alias="", prefix=""):
    """
    A navbar link, marked as the current page when the request resolves to ``url_name``
    or to one of the space-separated url names in ``also``.

    Unpoly keeps the mark up to date after it swaps fragments; ``alias`` is its
    ``up-alias`` pattern for the other URLs that count as this page. ``prefix`` goes before the label for
    screen readers only, to tell apart links with the same label in different groups.
    """
    request = context.get("request")
    match = request.resolver_match if request else None
    current = match is not None and match.url_name in {url_name, *also.split()}
    return {
        "href": reverse(url_name),
        "label": label,
        "current": current,
        "alias": alias,
        "prefix": f"{prefix}: " if prefix else "",
    }


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
