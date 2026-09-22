from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_api_route_is_not_found(client: TestClient) -> None:
    response = client.get("/api/v0/does-not-exist")

    assert response.status_code == 404
