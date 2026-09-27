from fastapi.testclient import TestClient

LOCATIONS = "/api/v0/locations/"
LOGIN = "/api/v0/auth/login"

ADMIN = {"email": "admin", "password": "admin"}
VOLUNTEER = {"email": "tara@example.com", "password": "volunteer"}


def _auth_headers(client: TestClient, credentials: dict[str, str]) -> dict[str, str]:
    token = client.post(LOGIN, json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_list_locations(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.get(LOCATIONS, headers=headers)

    assert response.status_code == 200
    # the seed db has the hospital, and every location has the agreement's fields
    locations = response.json()["locations"]
    assert "Royal Melbourne Hospital" in [location["name"] for location in locations]
    assert set(locations[0]) == {"locationId", "name", "latitude", "longitude"}


def test_list_locations_forbidden_for_non_admin(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    response = client.get(LOCATIONS, headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
