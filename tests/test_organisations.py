from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.storage import DB_FILE

ORGANISATIONS = "/api/v0/organisations/"
LOGIN = "/api/v0/auth/login"

ADMIN = {"email": "admin", "password": "admin"}
VOLUNTEER = {"email": "tara@example.com", "password": "volunteer"}
ORGANISATION = {"email": "stores@rmh.example.com", "password": "organisation"}
ORGANISATION_ID = 3  # Royal Melbourne Hospital in the seed db
VOLUNTEER_ID = 2  # Tara Nguyen in the seed db, not an organisation


def _auth_headers(client: TestClient, credentials: dict[str, str]) -> dict[str, str]:
    token = client.post(LOGIN, json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def preserve_db() -> Iterator[None]:
    original = DB_FILE.read_text()
    yield
    DB_FILE.write_text(original)


def test_admin_can_create_and_then_get_an_organisation(
    client: TestClient, preserve_db: None
) -> None:
    headers = _auth_headers(client, ADMIN)

    created = client.post(
        ORGANISATIONS,
        json={
            "name": "New Organisation",
            "email": "new.org@example.com",
            "password": "hunter2",
        },
        headers=headers,
    )

    assert created.status_code == 201
    body = created.json()
    # password should never come back in the response
    assert "password" not in body
    assert body["name"] == "New Organisation"
    assert body["email"] == "new.org@example.com"
    organisation_id = body["organisationId"]

    fetched = client.get(f"{ORGANISATIONS}{organisation_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_create_organisation_with_taken_email_returns_409(
    client: TestClient, preserve_db: None
) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.post(
        ORGANISATIONS,
        json={
            "name": "Duplicate",
            "email": ORGANISATION["email"],
            "password": "hunter2",
        },
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"


def test_create_organisation_forbidden_for_non_admin(
    client: TestClient, preserve_db: None
) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    response = client.post(
        ORGANISATIONS,
        json={"name": "New Organisation", "email": "x@example.com", "password": "x"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_create_organisation_requires_auth(
    client: TestClient, preserve_db: None
) -> None:
    response = client.post(
        ORGANISATIONS,
        json={"name": "New Organisation", "email": "x@example.com", "password": "x"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORISED"


def test_get_organisation_not_found_for_missing_id(
    client: TestClient, preserve_db: None
) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.get(f"{ORGANISATIONS}999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANISATION_NOT_FOUND"


# a user id that exists but belongs to a non-organisation role should 404, not leak their profile
def test_get_organisation_not_found_for_non_organisation_user(
    client: TestClient, preserve_db: None
) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.get(f"{ORGANISATIONS}{VOLUNTEER_ID}", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANISATION_NOT_FOUND"


def test_get_organisation_forbidden_for_non_admin(
    client: TestClient, preserve_db: None
) -> None:
    headers = _auth_headers(client, ORGANISATION)

    response = client.get(f"{ORGANISATIONS}{ORGANISATION_ID}", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
