import pytest

from radscheduler.core.models import Registrar as DjRegistrar
from radscheduler.roster.models import Registrar as PyRegistrar
from radscheduler.users.models import User
from radscheduler.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db) -> User:
    return UserFactory()


YEAR2 = ["Erika", "Will", "Kelly", "Carol", "Edward"]
YEAR3 = ["Sam", "Connor", "Michael", "Aaron", "Liam"]
YEAR4 = ["Angelo", "Waleed", "Nick", "Ben", "Tubo"]


def registrar_factories(name, senior=False):
    user = UserFactory(username=name)
    registrar = DjRegistrar(user=user, senior=senior)
    return registrar


@pytest.fixture
def juniors():
    result = []
    for name in YEAR2:
        result.append(PyRegistrar(name, senior=False))
    return result


@pytest.fixture
def seniors():
    result = []
    for name in YEAR3 + YEAR4:
        result.append(PyRegistrar(name, senior=True))
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
