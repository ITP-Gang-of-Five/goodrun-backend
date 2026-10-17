import pytest
from fastapi.testclient import TestClient

from app.auth.limits import (
    LOCKOUT_WINDOW,
    MAX_FAILED_PER_ACCOUNT,
    MAX_FAILED_PER_IP,
    LoginAttempts,
)
from app.auth.passwords import hash_password, verify_password
from app.auth.tokens import load_secret
from app.errors import ApiError
from app.queries import Queries
from tests.accounts import set_up_volunteer

LOGIN = "/api/v0/auth/login"
REFRESH = "/api/v0/auth/refresh-token"

# hard code the only creds we have for test cases
ADMIN = {"email": "admin", "password": "admin"}
WRONG = {"email": "admin", "password": "not-the-password"}


def test_login_returns_tokens_and_the_user(client: TestClient) -> None:
    response = client.post(LOGIN, json=ADMIN)

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"] == {
        "userId": "1",
        "name": "Admin",
        "role": "ADMIN",
        "onboarded": True,
    }


def test_wrong_password_and_unknown_email_get_the_same_error(
    client: TestClient,
) -> None:
    wrong_password = client.post(LOGIN, json={"email": "admin", "password": "nope"})
    unknown_email = client.post(LOGIN, json={"email": "nobody", "password": "nope"})

    assert wrong_password.status_code == 401
    assert wrong_password.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert unknown_email.json() == wrong_password.json()


def test_refresh_gives_a_new_token_pair(client: TestClient) -> None:
    tokens = client.post(LOGIN, json=ADMIN).json()

    response = client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "refresh_token"}


def test_an_access_token_cannot_be_used_to_refresh(client: TestClient) -> None:
    tokens = client.post(LOGIN, json=ADMIN).json()

    response = client.post(REFRESH, json={"refresh_token": tokens["access_token"]})

    assert response.status_code == 401


def test_a_made_up_token_is_rejected(client: TestClient) -> None:
    response = client.post(REFRESH, json={"refresh_token": "not-a-token"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORISED"


def test_passwords_are_stored_hashed_and_still_work(
    client: TestClient, queries: Queries
) -> None:
    new_account = {"email": "hashed@example.com", "password": "hunter22"}
    set_up_volunteer(client, **new_account)

    stored = queries.get_user_by_email(new_account["email"])
    assert stored is not None
    assert stored.password_hash is not None
    assert stored.password_hash != new_account["password"]
    assert stored.password_hash.startswith("$argon2id$")
    assert client.post(LOGIN, json=new_account).status_code == 200


def test_a_plain_text_password_left_in_the_database_never_matches() -> None:
    # accounts made before hashing hold the password itself, which isn't a valid hash
    assert not verify_password("admin", "admin")
    assert verify_password("admin", hash_password("admin"))


def _from(ip: str) -> dict[str, str]:
    # pretend the request came through Render's proxy from this address
    return {"X-Forwarded-For": f"{ip}, 10.0.0.1"}


def test_too_many_wrong_passwords_locks_that_person_out(client: TestClient) -> None:
    for _ in range(MAX_FAILED_PER_ACCOUNT):
        assert (
            client.post(LOGIN, json=WRONG, headers=_from("1.1.1.1")).status_code == 401
        )

    # even the right password is refused now, otherwise guessing could carry on
    response = client.post(LOGIN, json=ADMIN, headers=_from("1.1.1.1"))

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "TOO_MANY_LOGIN_ATTEMPTS"


def test_someone_else_can_still_log_in_to_that_account(client: TestClient) -> None:
    # otherwise anyone could lock a real user out just by knowing their email
    for _ in range(MAX_FAILED_PER_ACCOUNT):
        client.post(LOGIN, json=WRONG, headers=_from("1.1.1.1"))

    assert client.post(LOGIN, json=ADMIN, headers=_from("2.2.2.2")).status_code == 200


def test_trying_lots_of_accounts_locks_that_person_out_of_all_of_them(
    client: TestClient,
) -> None:
    for number in range(MAX_FAILED_PER_IP):
        client.post(
            LOGIN,
            json={"email": f"guess{number}@example.com", "password": "nope"},
            headers=_from("1.1.1.1"),
        )

    assert client.post(LOGIN, json=ADMIN, headers=_from("1.1.1.1")).status_code == 429
    assert client.post(LOGIN, json=ADMIN, headers=_from("2.2.2.2")).status_code == 200


def test_unknown_emails_are_locked_the_same_way(client: TestClient) -> None:
    # so being locked out doesn't give away whether an account exists
    nobody = {"email": "nobody", "password": "nope"}
    for _ in range(MAX_FAILED_PER_ACCOUNT):
        client.post(LOGIN, json=nobody)

    assert client.post(LOGIN, json=nobody).status_code == 429


def test_logging_in_clears_the_failed_attempts(client: TestClient) -> None:
    for _ in range(MAX_FAILED_PER_ACCOUNT - 1):
        client.post(LOGIN, json=WRONG)
    assert client.post(LOGIN, json=ADMIN).status_code == 200

    for _ in range(MAX_FAILED_PER_ACCOUNT - 1):
        client.post(LOGIN, json=WRONG)

    assert client.post(LOGIN, json=ADMIN).status_code == 200


def test_a_lockout_ends_once_the_failures_are_old_enough() -> None:
    now = 0.0
    attempts = LoginAttempts(clock=lambda: now)
    for _ in range(MAX_FAILED_PER_ACCOUNT):
        attempts.record_failure("1.1.1.1", "Admin ")

    # emails are matched ignoring case and spaces, so this is the same account
    with pytest.raises(ApiError) as locked:
        attempts.check("1.1.1.1", "admin")
    assert locked.value.description.endswith("15 minutes")

    now += LOCKOUT_WINDOW + 1
    attempts.check("1.1.1.1", "admin")


def test_a_huge_password_is_rejected_before_it_is_hashed(client: TestClient) -> None:
    response = client.post(LOGIN, json={"email": "admin", "password": "a" * 10_000})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_the_server_refuses_to_start_without_a_proper_jwt_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        load_secret()

    monkeypatch.setenv("JWT_SECRET", "too-short")
    with pytest.raises(RuntimeError):
        load_secret()

    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    assert load_secret() == "x" * 32
