import pytest
from django.contrib.auth import get_user_model

from radscheduler.core.models import Registrar


YEAR2 = ["Erika", "Will", "Kelly", "Carol", "Edward"]
YEAR3 = ["Sam", "Connor", "Michael", "Aaron", "Liam"]
YEAR4 = ["Angelo", "Waleed", "Nick", "Ben", "Tubo"]


def registrar(name, senior=False):
    user = Registrar(username=name, senior=senior)
    return user


@pytest.fixture
def juniors():
    result = []
    for name in YEAR2:
        result.append(registrar(name, senior=False))
    return result


@pytest.fixture
def seniors():
    result = []
    for name in YEAR3 + YEAR4:
        result.append(registrar(name, senior=True))
    return result
