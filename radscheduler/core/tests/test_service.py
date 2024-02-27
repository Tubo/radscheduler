from radscheduler.core.service import build_registrar_table


def test_generate_shifts():
    # Some shifts were created previously
    # Generate new shifts
    # Ensure no duplicate shifts were generated
    pass


def test_generate_buddy_shifts():
    pass


def test_build_registrar_table(juniors_db):
    registrars = list()
    for user in juniors_db:
        registrars.append(user)
    result = build_registrar_table(registrars=registrars)
    assert len(result) == len(registrars)
    result_user = list()
    for user in result[0]:
        result_user.append(user)
    assert result_user == registrars
