from django.middleware.csrf import get_token
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from radscheduler.core.roles import leave_approvers
from radscheduler.core.views.decorators import staff_required
from radscheduler.core.views.editor import type_choices


@staff_required
@require_GET
def page(request):
    """
    Leave requests waiting for the chief registrar's or the Director of Training's decision, each beside the
    roster it affects. An Elm page that loads them from /api/editor/leave-requests.
    """
    flags = {
        "csrfToken": get_token(request),
        "editorUrl": reverse("editor_next"),
        **type_choices(),
        "leaveApprovers": leave_approvers(request.user),
    }
    return render(request, "leave_requests/page.html", {"flags": flags})
