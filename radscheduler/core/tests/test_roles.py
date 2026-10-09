import pytest

from radscheduler.core.roles import leave_approvers
from radscheduler.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_leave_approvers(admin_user, director, office_staff):
    assert leave_approvers(admin_user) == ("reg", "dot")
    assert leave_approvers(UserFactory(is_staff=True)) == ("reg", "dot")  # a chief registrar
    assert leave_approvers(director) == ("dot",)
    assert leave_approvers(office_staff) == ()
    assert leave_approvers(UserFactory()) == ()  # a registrar
