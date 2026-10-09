from django import template
from django.urls import reverse

register = template.Library()


@register.inclusion_tag("navbar_link.html", takes_context=True)
def nav_link(context, url_name, label, also="", alias=""):
    """
    A navbar link, marked as the current page when the request resolves to ``url_name``
    or to one of the space-separated url names in ``also``.

    Unpoly keeps the mark up to date after it swaps fragments; ``alias`` is its
    ``up-alias`` pattern for the other URLs that count as this page.
    """
    request = context.get("request")
    match = request.resolver_match if request else None
    current = match is not None and match.url_name in {url_name, *also.split()}
    return {"href": reverse(url_name), "label": label, "current": current, "alias": alias}
