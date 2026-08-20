import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("post", "/api/v0/location/", 204),
        ("get", "/api/v0/runs/", 200),
        ("post", "/api/v0/runs/", 200),
        ("get", "/api/v0/runs/current", 200),
        ("get", "/api/v0/runs/abc", 200),
        ("post", "/api/v0/runs/abc/accept", 204),
        ("post", "/api/v0/runs/abc/cancel", 204),
        ("post", "/api/v0/runs/abc/complete", 204),
        ("post", "/api/v0/runs/abc/remove", 204),
    ],
)
def test_stub_endpoints(
    client: TestClient, method: str, path: str, status: int
) -> None:
    response = client.request(method, path)
    assert response.status_code == status
