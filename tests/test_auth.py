import pytest

from app.auth.jwt_handler import verify_access_token
from app.auth.login import *
from app.common.exceptions import *
from app.main import *


def test_signup_success():
    mock_db()
    payload = LoginRequestDto("testuser@email.com", "password")
    res = signup(payload)
    assert res["access_token"]
    payload = verify_access_token(res["access_token"])
    assert payload is not None
    assert payload.get("userId") is not None


def test_signup_and_login_success():
    mock_db()
    payload = LoginRequestDto("testuser@email.com", "password")
    signup(payload)

    res = login(payload)

    assert res["access_token"]
    payload = verify_access_token(res["access_token"])
    assert payload is not None
    assert payload.get("userId") is not None


def test_login_user_doesnt_exist():
    mock_db()
    payload = LoginRequestDto("testuser@email.com", "password")
    with pytest.raises(UserNotFoundError) as E:
        login(payload)

    assert E


def test_login_user_incorrect_password():
    mock_db()
    payload = LoginRequestDto("testuser@email.com", "password")
    signup(payload)
    with pytest.raises(IncorrectPasswordError) as E:
        payload = LoginRequestDto("testuser@email.com", "password123")
        login(payload)

    assert E
