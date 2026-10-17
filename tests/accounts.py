"""
Helpers for tests that need new accounts.

No test ever sends a real email: conftest catches every one into sent_emails instead, so
a test can read the invite code out of it like the person would.
"""

import re
from email.message import EmailMessage

from fastapi.testclient import TestClient

LOGIN = "/api/v0/auth/login"
VOLUNTEERS = "/api/v0/volunteers/"
ONBOARDING = "/api/v0/me/onboarding"
ADMIN = {"email": "admin", "password": "admin"}

# every email "sent" during the current test, oldest first
sent_emails: list[EmailMessage] = []


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_headers(client: TestClient) -> dict[str, str]:
    return bearer(client.post(LOGIN, json=ADMIN).json()["access_token"])


def code_sent_to(email: str) -> str:
    # the code from the latest invite sent to that address
    for message in reversed(sent_emails):
        if message["To"] == email:
            content = message.get_content()
            assert isinstance(content, str)
            found = re.search(r"\b\d{6}\b", content)
            assert found, "the invite email has no code in it"
            return found.group()
    raise AssertionError(f"no email was sent to {email}")


def set_up_volunteer(
    client: TestClient,
    email: str,
    password: str = "hunter22",
    car_size: str = "LARGE",
) -> dict[str, str]:
    """
    Invites a volunteer and sets up their account the way the app would, returning the
    headers to make requests as them.
    """
    client.post(VOLUNTEERS, json={"email": email}, headers=admin_headers(client))
    token = client.post(
        LOGIN, json={"email": email, "password": code_sent_to(email)}
    ).json()["access_token"]
    client.post(
        ONBOARDING,
        json={"name": "New Volunteer", "password": password, "carSize": car_size},
        headers=bearer(token),
    )
    return bearer(token)
