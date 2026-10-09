from datetime import date

import pytest
from django.contrib.auth.models import Group

from radscheduler.core.models import Registrar as Registrar_db
from radscheduler.core.roles import DIRECTOR_OF_TRAINING, OFFICE_STAFF
from radscheduler.roster.models import Registrar as Registrar_py
from radscheduler.users.models import User
from radscheduler.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def app(django_app_factory):
    return django_app_factory(csrf_checks=False)


@pytest.fixture
def user(db) -> User:
    return UserFactory()


def _in_group(name: str) -> User:
    user = UserFactory(is_staff=True)
    # get_or_create: live-server tests empty the database, the groups made by migrations included
    user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


@pytest.fixture
def director(db) -> User:
    """The Director of Training: staff who make only the Director's decision on leave."""
    return _in_group(DIRECTOR_OF_TRAINING)


@pytest.fixture
def office_staff(db) -> User:
    """Office staff: they see leave but don't decide it."""
    return _in_group(OFFICE_STAFF)


YEAR2 = ["Erika", "Will", "Kelly", "Carol", "Edward"]
YEAR3 = ["Sam", "Connor", "Michael", "Aaron", "Liam"]
YEAR4 = ["Angelo", "Waleed", "Nick", "Ben", "Tubo"]


def registrar_factories(name, senior=False):
    user = UserFactory(username=name)
    registrar = Registrar_db.objects.create(user=user, senior=senior, start=date(2022, 1, 1))
    return registrar


@pytest.fixture
def juniors():
    result = []
    for name in YEAR2:
        result.append(Registrar_py(name, senior=False, start=date(2022, 1, 1)))
    return result


@pytest.fixture
def seniors():
    result = []
    for name in YEAR3:
        result.append(Registrar_py(name, senior=True, start=date(2021, 1, 1)))
    for name in YEAR4:
        result.append(Registrar_py(name, senior=True, start=date(2019, 12, 1)))
    return result


@pytest.fixture
def juniors_db(db):
    result = []
    for name in YEAR2:
        result.append(registrar_factories(name, senior=False))
    return result


@pytest.fixture
def seniors_db(db):
    result = []
    for name in YEAR3 + YEAR4:
        result.append(registrar_factories(name, senior=True))
    return result
