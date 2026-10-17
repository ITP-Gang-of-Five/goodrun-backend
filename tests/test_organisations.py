from fastapi.testclient import TestClient

from tests.accounts import ONBOARDING, bearer, code_sent_to, sent_emails

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


def test_admin_can_create_and_then_get_an_organisation(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    created = client.post(
        ORGANISATIONS, json={"email": "new.org@example.com"}, headers=headers
    )

    assert created.status_code == 201
    body = created.json()
    # password should never come back in the response
    assert "password" not in body
    assert body["email"] == "new.org@example.com"
    # they choose their name when they set up their account
    assert body["name"] is None
    assert body["onboarded"] is False
    organisation_id = body["organisationId"]

    fetched = client.get(f"{ORGANISATIONS}{organisation_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_create_organisation_with_taken_email_returns_409(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.post(
        ORGANISATIONS,
        json={"email": ORGANISATION["email"]},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_IN_USE"


def test_create_organisation_forbidden_for_non_admin(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    response = client.post(
        ORGANISATIONS,
        json={"email": "x@example.com"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_create_organisation_requires_auth(client: TestClient) -> None:
    response = client.post(
        ORGANISATIONS,
        json={"email": "x@example.com"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORISED"


def test_get_organisation_not_found_for_missing_id(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.get(f"{ORGANISATIONS}999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANISATION_NOT_FOUND"


# a user id that exists but belongs to a non-organisation role should 404, not leak their profile
def test_get_organisation_not_found_for_non_organisation_user(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.get(f"{ORGANISATIONS}{VOLUNTEER_ID}", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANISATION_NOT_FOUND"


def test_get_organisation_forbidden_for_non_admin(client: TestClient) -> None:
    headers = _auth_headers(client, ORGANISATION)

    response = client.get(f"{ORGANISATIONS}{ORGANISATION_ID}", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_list_organisations(client: TestClient) -> None:
    # retrieve all organisations
    headers = _auth_headers(client, ADMIN)
    response = client.get(ORGANISATIONS, headers=headers)

    assert response.status_code == 200
    organisations = response.json()["organisations"]
    ids = [org["organisationId"] for org in organisations]
    # ensure that only orgs are returned
    assert ids == [str(ORGANISATION_ID)]


NEW_ORG = "new.org@example.com"


def _invite(client: TestClient) -> str:
    created = client.post(
        ORGANISATIONS,
        json={"email": NEW_ORG},
        headers=_auth_headers(client, ADMIN),
    )
    organisation_id: str = created.json()["organisationId"]
    return organisation_id


def _log_in_with_code(client: TestClient) -> dict[str, str]:
    response = client.post(
        LOGIN, json={"email": NEW_ORG, "password": code_sent_to(NEW_ORG)}
    )
    assert response.json()["user"]["onboarded"] is False
    return bearer(response.json()["access_token"])


def test_inviting_an_organisation_emails_them_a_code(client: TestClient) -> None:
    _invite(client)

    [email] = sent_emails
    assert email["To"] == NEW_ORG
    assert len(code_sent_to(NEW_ORG)) == 6


def test_an_organisation_sets_up_with_just_a_name_and_password(
    client: TestClient,
) -> None:
    organisation_id = _invite(client)
    headers = _log_in_with_code(client)

    response = client.post(
        ONBOARDING,
        json={"name": "Brunswick Pantry", "password": "hunter22"},
        headers=headers,
    )

    assert response.status_code == 204
    fetched = client.get(
        f"{ORGANISATIONS}{organisation_id}", headers=_auth_headers(client, ADMIN)
    ).json()
    assert fetched["name"] == "Brunswick Pantry"
    assert fetched["onboarded"] is True
    login = client.post(LOGIN, json={"email": NEW_ORG, "password": "hunter22"})
    assert login.json()["user"]["role"] == "ORGANISATION"


def test_an_organisation_cannot_choose_a_car_size(client: TestClient) -> None:
    _invite(client)
    headers = _log_in_with_code(client)

    response = client.post(
        ONBOARDING,
        json={"name": "Brunswick Pantry", "password": "hunter22", "carSize": "SMALL"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_resending_an_organisations_invite_replaces_the_code(
    client: TestClient,
) -> None:
    organisation_id = _invite(client)
    old_code = code_sent_to(NEW_ORG)

    response = client.post(
        f"{ORGANISATIONS}{organisation_id}/resend-invite",
        headers=_auth_headers(client, ADMIN),
    )

    assert response.status_code == 204
    assert len(sent_emails) == 2
    new_code = code_sent_to(NEW_ORG)
    if new_code != old_code:
        old = client.post(LOGIN, json={"email": NEW_ORG, "password": old_code})
        assert old.status_code == 401
    new = client.post(LOGIN, json={"email": NEW_ORG, "password": new_code})
    assert new.status_code == 200


def test_resending_to_an_organisation_already_set_up_is_refused(
    client: TestClient,
) -> None:
    response = client.post(
        f"{ORGANISATIONS}{ORGANISATION_ID}/resend-invite",
        headers=_auth_headers(client, ADMIN),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_ONBOARDED"
    assert sent_emails == []


def test_resending_to_a_non_organisation_is_not_found(client: TestClient) -> None:
    response = client.post(
        f"{ORGANISATIONS}{VOLUNTEER_ID}/resend-invite",
        headers=_auth_headers(client, ADMIN),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORGANISATION_NOT_FOUND"


def test_only_admins_can_resend_an_organisations_invite(client: TestClient) -> None:
    organisation_id = _invite(client)

    response = client.post(
        f"{ORGANISATIONS}{organisation_id}/resend-invite",
        headers=_auth_headers(client, ORGANISATION),
    )

    assert response.status_code == 403
