import json
from datetime import UTC, datetime

from app.storage import (
    Role,
    get_database,
)


def test_the_admin_exists() -> None:
    admin = get_database().get_user_by_email("admin")
    assert admin is not None
    assert admin.password == "admin"
    assert admin.role == Role.ADMIN
    assert get_database().get_user(admin.id) == admin


def test_unknown_users_are_none() -> None:
    #Ensure that random users that don't exist just return None
    assert get_database().get_user(999) is None
    assert get_database().get_user_by_email("nobody") is None
    assert get_database().get_user_by_email("i am not real") is None

