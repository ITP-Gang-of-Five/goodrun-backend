import pytest

from app.auth.exceptions import IncorrectPasswordError, UserNotFoundError
from app.auth.jwt_handler import verify_access_token
from app.auth.login import mock_db
from app.main import login, signup
from app.models.dtos import LoginRequestDto


def test_signup_success() -> None:
    mock_db()
    payload = LoginRequestDto("testuser@email.com", "password")
    res = signup(payload)
    assert res["access_token"]
    token_payload = verify_access_token(res["access_token"])
    assert token_payload is not None
    assert token_payload.get("userId") is not None


def test_signup_and_login_success() -> None:
    mock_db()
    payload = LoginRequestDto("testuser@email.com", "password")
    signup(payload)

    res = login(payload)

    assert res["access_token"]
    token_payload = verify_access_token(res["access_token"])
    assert token_payload is not None
    assert token_payload.get("userId") is not None


def test_login_user_doesnt_exist() -> None:
    mock_db()
    payload = LoginRequestDto("testuser@email.com", "password")
    with pytest.raises(UserNotFoundError) as E:
        login(payload)

    assert E


def test_login_user_incorrect_password() -> None:
    mock_db()
    payload = LoginRequestDto("testuser@email.com", "password")
    signup(payload)
    with pytest.raises(IncorrectPasswordError) as E:
        payload = LoginRequestDto("testuser@email.com", "password123")
        login(payload)

    assert E
