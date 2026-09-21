from fastapi.testclient import TestClient

LOGIN = "/api/v0/auth/login"
REFRESH = "/api/v0/auth/refresh-token"

#hard code the only creds we have for test cases
ADMIN = {"email": "admin", "password": "admin"}


def test_login_returns_tokens_and_the_user(client: TestClient) -> None:
    response = client.post(LOGIN, json=ADMIN)

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"] == {"userId": "1", "name": "Admin", "role": "ADMIN"}


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
