from fastapi.testclient import TestClient

VOLUNTEERS = "/api/v0/volunteers/"
LOGIN = "/api/v0/auth/login"

ADMIN = {"email": "admin", "password": "admin"}
VOLUNTEER = {"email": "tara@example.com", "password": "volunteer"}
VOLUNTEER_ID = 2  # Tara Nguyen in the seed db
ORGANISATION_ID = 3  # Royal Melbourne Hospital in the seed db, not a volunteer


def _auth_headers(client: TestClient, credentials: dict[str, str]) -> dict[str, str]:
    token = client.post(LOGIN, json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_create_and_then_get_a_volunteer(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    created = client.post(
        VOLUNTEERS,
        json={
            "name": "New Volunteer",
            "email": "new.volunteer@example.com",
            "password": "hunter2",
            "carSize": "SMALL",
        },
        headers=headers,
    )

    assert created.status_code == 201
    body = created.json()
    # password should never come back in the response
    assert "password" not in body
    assert body["name"] == "New Volunteer"
    assert body["email"] == "new.volunteer@example.com"
    assert body["carSize"] == "SMALL"
    volunteer_id = body["volunteerId"]

    fetched = client.get(f"{VOLUNTEERS}{volunteer_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_create_volunteer_with_taken_email_returns_409(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.post(
        VOLUNTEERS,
        json={
            "name": "Duplicate",
            "email": VOLUNTEER["email"],
            "password": "hunter2",
        },
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_TAKEN"


def test_create_volunteer_forbidden_for_non_admin(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    response = client.post(
        VOLUNTEERS,
        json={"name": "New Volunteer", "email": "x@example.com", "password": "x"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_create_volunteer_requires_auth(client: TestClient) -> None:
    response = client.post(
        VOLUNTEERS,
        json={"name": "New Volunteer", "email": "x@example.com", "password": "x"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORISED"


def test_get_volunteer_not_found_for_missing_id(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.get(f"{VOLUNTEERS}999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VOLUNTEER_NOT_FOUND"


# a user id that exists but belongs to a non-volunteer role should 404, not leak their profile
def test_get_volunteer_not_found_for_non_volunteer_user(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.get(f"{VOLUNTEERS}{ORGANISATION_ID}", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VOLUNTEER_NOT_FOUND"


def test_get_volunteer_forbidden_for_non_admin(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    response = client.get(f"{VOLUNTEERS}{VOLUNTEER_ID}", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_list_volunteers(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)
    response = client.get(VOLUNTEERS, headers=headers)

    assert response.status_code == 200
    volunteers = response.json()["volunteers"]
    #only volunteers should be listed, never admins or organisations
    ids = [v["volunteerId"] for v in volunteers]
    assert str(VOLUNTEER_ID) in ids
    assert str(ORGANISATION_ID) not in ids
    tara = next(v for v in volunteers if v["volunteerId"] == str(VOLUNTEER_ID))
    assert tara["email"] == VOLUNTEER["email"]
    assert "password" not in tara


def test_list_volunteers_includes_newly_created_volunteer(client: TestClient) -> None:
    #create a new volunteer
    headers = _auth_headers(client, ADMIN)
    created = client.post(
        VOLUNTEERS,
        json={
            "name": "New Volunteer",
            "email": "new.volunteer@example.com",
            "password": "hunter2",
            "carSize": "LARGE",
        },
        headers=headers,
    ).json()

    response = client.get(VOLUNTEERS, headers=headers)
    #our new volunteer should be in there
    assert created in response.json()["volunteers"]