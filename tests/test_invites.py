import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient

from app.auth.invites import MAX_FAILED_ATTEMPTS
from app.common.mail import deliver
from app.errors import ApiError
from app.queries import Queries
from tests.accounts import (
    LOGIN,
    ONBOARDING,
    VOLUNTEERS,
    admin_headers,
    bearer,
    code_sent_to,
    sent_emails,
    set_up_volunteer,
)

ME = "/api/v0/me/"
AVAILABLE = "/api/v0/orders/available"
NEW = "new.volunteer@example.com"
SETUP = {"name": "Jo Bloggs", "password": "hunter22", "carSize": "SMALL"}

# seeded as invited but not set up yet, with the code 123456
SEEDED_INVITED = {"email": "invited@example.com", "password": "123456"}


def _invite(client: TestClient, email: str = NEW) -> dict[str, Any]:
    response = client.post(
        VOLUNTEERS, json={"email": email}, headers=admin_headers(client)
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def _log_in_with_code(client: TestClient, email: str = NEW) -> dict[str, Any]:
    response = client.post(
        LOGIN, json={"email": email, "password": code_sent_to(email)}
    )
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def _from(ip: str) -> dict[str, str]:
    return {"X-Forwarded-For": ip}


def test_inviting_a_volunteer_emails_them_a_code(client: TestClient) -> None:
    created = _invite(client)

    assert created["onboarded"] is False
    assert created["name"] is None
    [email] = sent_emails
    assert email["To"] == NEW
    assert len(code_sent_to(NEW)) == 6
    # the admin can see they haven't set up yet
    listed = client.get(VOLUNTEERS, headers=admin_headers(client)).json()["volunteers"]
    assert created in listed


def test_the_code_logs_them_in_once(client: TestClient) -> None:
    _invite(client)
    code = code_sent_to(NEW)

    first = client.post(LOGIN, json={"email": NEW, "password": code})
    second = client.post(LOGIN, json={"email": NEW, "password": code})

    assert first.status_code == 200
    assert first.json()["user"]["onboarded"] is False
    assert first.json()["user"]["name"] is None
    assert second.status_code == 401
    assert second.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_the_code_works_with_spaces_copied_around_it(client: TestClient) -> None:
    _invite(client)

    response = client.post(
        LOGIN, json={"email": NEW, "password": f" {code_sent_to(NEW)} "}
    )

    assert response.status_code == 200


def test_they_cant_do_anything_until_they_set_up(client: TestClient) -> None:
    _invite(client)
    headers = bearer(_log_in_with_code(client)["access_token"])

    # but they can see their own profile, so the app knows where they're at
    profile = client.get(ME, headers=headers)
    assert profile.status_code == 200
    assert profile.json()["onboarded"] is False

    for response in (
        client.get(AVAILABLE, headers=headers),
        client.patch(ME, json={"name": "Sneaky"}, headers=headers),
    ):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "NOT_ONBOARDED"


def test_setting_up_lets_them_in_with_their_own_password(client: TestClient) -> None:
    _invite(client)
    headers = bearer(_log_in_with_code(client)["access_token"])

    response = client.post(ONBOARDING, json=SETUP, headers=headers)

    assert response.status_code == 204
    profile = client.get(ME, headers=headers).json()
    assert profile["name"] == "Jo Bloggs"
    assert profile["carSize"] == "SMALL"
    assert profile["onboarded"] is True
    # the token from the code keeps working, now for everything
    assert client.get(AVAILABLE, headers=headers).status_code == 200
    login = client.post(LOGIN, json={"email": NEW, "password": "hunter22"})
    assert login.json()["user"] == {
        "userId": profile["userId"],
        "name": "Jo Bloggs",
        "role": "VOLUNTEER",
        "onboarded": True,
    }


def test_setting_up_twice_is_refused(client: TestClient) -> None:
    headers = set_up_volunteer(client, NEW)

    response = client.post(ONBOARDING, json=SETUP, headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_ONBOARDED"


@pytest.mark.parametrize(
    "overrides",
    [
        {"carSize": None},
        {"name": "   "},
        {"password": "short"},
        {"carSize": "HUGE"},
    ],
)
def test_setting_up_needs_proper_details(
    client: TestClient, overrides: dict[str, Any]
) -> None:
    _invite(client)
    headers = bearer(_log_in_with_code(client)["access_token"])

    response = client.post(ONBOARDING, json={**SETUP, **overrides}, headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get(ME, headers=headers).json()["onboarded"] is False


def test_too_many_wrong_codes_kills_the_invite_from_any_ip(client: TestClient) -> None:
    _invite(client)
    code = code_sent_to(NEW)

    # each from a different address, so the per IP login limit never kicks in
    for number in range(MAX_FAILED_ATTEMPTS):
        client.post(
            LOGIN,
            json={"email": NEW, "password": "000000" if code != "000000" else "111111"},
            headers=_from(f"10.0.0.{number}"),
        )
    response = client.post(LOGIN, json={"email": NEW, "password": code})

    assert response.status_code == 401


def test_an_expired_code_is_refused(client: TestClient, queries: Queries) -> None:
    created = _invite(client)
    invite = queries.get_invite(int(created["volunteerId"]))
    assert invite is not None
    queries.set_invite(
        invite.model_copy(
            update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
        )
    )

    response = client.post(LOGIN, json={"email": NEW, "password": code_sent_to(NEW)})

    assert response.status_code == 401


def test_resending_replaces_the_old_code(client: TestClient) -> None:
    created = _invite(client)
    old_code = code_sent_to(NEW)

    response = client.post(
        f"{VOLUNTEERS}{created['volunteerId']}/resend-invite",
        headers=admin_headers(client),
    )

    assert response.status_code == 204
    assert len(sent_emails) == 2
    new_code = code_sent_to(NEW)
    if new_code != old_code:
        assert (
            client.post(LOGIN, json={"email": NEW, "password": old_code}).status_code
            == 401
        )
    assert (
        client.post(LOGIN, json={"email": NEW, "password": new_code}).status_code == 200
    )


def test_resending_also_revives_a_killed_invite(client: TestClient) -> None:
    created = _invite(client)
    for _ in range(MAX_FAILED_ATTEMPTS):
        client.post(LOGIN, json={"email": NEW, "password": "not-a-code"})

    client.post(
        f"{VOLUNTEERS}{created['volunteerId']}/resend-invite",
        headers=admin_headers(client),
    )
    response = client.post(
        LOGIN,
        json={"email": NEW, "password": code_sent_to(NEW)},
        headers=_from("10.9.9.9"),
    )

    assert response.status_code == 200


def test_resending_to_someone_already_set_up_is_refused(client: TestClient) -> None:
    response = client.post(
        f"{VOLUNTEERS}2/resend-invite", headers=admin_headers(client)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_ONBOARDED"
    assert sent_emails == []


def test_resending_to_a_non_volunteer_is_not_found(client: TestClient) -> None:
    response = client.post(
        f"{VOLUNTEERS}3/resend-invite", headers=admin_headers(client)
    )

    assert response.status_code == 404


def test_only_admins_can_resend(client: TestClient) -> None:
    headers = set_up_volunteer(client, NEW)

    response = client.post(f"{VOLUNTEERS}4/resend-invite", headers=headers)

    assert response.status_code == 403


def test_the_seeded_invited_volunteer_can_log_in_with_its_code(
    client: TestClient,
) -> None:
    response = client.post(LOGIN, json=SEEDED_INVITED)

    assert response.status_code == 200
    assert response.json()["user"]["onboarded"] is False


def test_an_invited_account_has_no_password_to_guess(client: TestClient) -> None:
    _invite(client)

    # any normal password is just a wrong code
    response = client.post(LOGIN, json={"email": NEW, "password": "hunter22"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_the_invite_fails_cleanly_when_the_email_cant_be_sent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(message: EmailMessage) -> None:
        raise ApiError(502, "EMAIL_NOT_SENT", "Couldn't send the email")

    monkeypatch.setattr("app.common.mail.deliver", broken)

    response = client.post(
        VOLUNTEERS, json={"email": NEW}, headers=admin_headers(client)
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "EMAIL_NOT_SENT"


"""
The real sender. These never reach Gmail, smtplib is faked
"""


def _message() -> EmailMessage:
    message = EmailMessage()
    message["To"] = NEW
    message.set_content("hello")
    return message


class _FakeSmtp:
    sent: ClassVar[list[EmailMessage]] = []
    logins: ClassVar[list[tuple[str, str]]] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        assert (host, port) == ("smtp.gmail.com", 465)

    def __enter__(self) -> _FakeSmtp:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def login(self, user: str, password: str) -> None:
        self.logins.append((user, password))

    def send_message(self, message: EmailMessage) -> None:
        self.sent.append(message)


def test_it_sends_through_gmail_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMTP_USER", "goodrun@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setattr(_FakeSmtp, "sent", [])
    monkeypatch.setattr(_FakeSmtp, "logins", [])
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSmtp)

    deliver(_message())

    assert _FakeSmtp.logins == [("goodrun@gmail.com", "app-password")]
    assert [message["To"] for message in _FakeSmtp.sent] == [NEW]


def test_a_gmail_failure_is_a_502(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise smtplib.SMTPAuthenticationError(535, b"bad app password")

    monkeypatch.setenv("SMTP_USER", "goodrun@gmail.com")
    monkeypatch.setattr(smtplib, "SMTP_SSL", refuse)

    with pytest.raises(ApiError) as error:
        deliver(_message())
    assert error.value.code == "EMAIL_NOT_SENT"


def test_without_gmail_set_up_it_prints_the_email(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    deliver(_message())

    assert "hello" in capsys.readouterr().out
