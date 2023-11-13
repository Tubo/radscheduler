from datetime import date

import pytest

from radscheduler.core.models import Registrar as Registrar_db
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
