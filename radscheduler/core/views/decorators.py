from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def staff_required(view):
    """
    For the roster and extra-duty editors. Signed-out visitors go to the site's sign-in page and come back
    afterwards; signed-in registrars who aren't staff get a 403 that says why.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_active and request.user.is_staff):
            raise PermissionDenied(
                "Only staff who edit the roster can open this page. Ask the senior registrar if you need access."
            )
        return view(request, *args, **kwargs)

    return wrapper
