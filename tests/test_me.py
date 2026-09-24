from fastapi.testclient import TestClient

ME = "/api/v0/me/"
LOGIN = "/api/v0/auth/login"

# like Max I hard coded these for testing cause no one has implemented the real users yet
ADMIN = {"email": "admin", "password": "admin"}
VOLUNTEER = {"email": "tara@example.com", "password": "volunteer"}


# copied from test_orders
def _auth_headers(client: TestClient, credentials: dict[str, str]) -> dict[str, str]:
    token = client.post(LOGIN, json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_my_profile_returns_the_calling_users_details(client: TestClient) -> None:
    # get the volunteer profile
    headers = _auth_headers(client, VOLUNTEER)
    response = client.get(ME, headers=headers)

    # should be a 200 code because its valid
    assert response.status_code == 200
    body = response.json()
    # should match the hard coded details of the calling user
    assert body["userId"] == "2"
    assert body["name"] == "Tara Nguyen"
    assert body["role"] == "VOLUNTEER"
    assert body["carSize"] == "MEDIUM"


def test_update_my_profile_changes_only_the_fields_sent(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    # ran the patch request to change car size to large, should have 204 response
    response = client.patch(ME, json={"carSize": "LARGE"}, headers=headers)
    assert response.status_code == 204

    # getting the user now, the rest should be the same but the size should change
    fetched = client.get(ME, headers=headers)
    body = fetched.json()
    assert body["carSize"] == "LARGE"


def test_non_volunteers_cannot_set_a_car_size(client: TestClient) -> None:
    # admin makes a request to change their car size
    headers = _auth_headers(client, ADMIN)
    response = client.patch(ME, json={"carSize": "LARGE"}, headers=headers)
    # 401 cause admins don't have cars, only volunteers
    assert response.status_code == 403
