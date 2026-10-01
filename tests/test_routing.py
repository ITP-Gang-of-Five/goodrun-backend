from typing import Any

import pytest
import requests
from fastapi.testclient import TestClient

from app.routing import routing

ROUTE = "/api/v0/routing/route"
LOGIN = "/api/v0/auth/login"

VOLUNTEER = {"email": "tara@example.com", "password": "volunteer"}

RMH = {"locationId": "1", "latitude": -37.79867, "longitude": 144.95597}
FOOTSCRAY = {"locationId": "2", "latitude": -37.80000, "longitude": 144.90000}
BOX_HILL = {"locationId": "3", "latitude": -37.81900, "longitude": 145.12000}

# two legs, and the point where they join is repeated, same as the real thing
AWS_ROUTE = {
    "Routes": [
        {
            "Summary": {"Distance": 30867, "Duration": 2965},
            "Legs": [
                {"Geometry": {"LineString": [[144.95597, -37.79867], [144.9, -37.8]]}},
                {"Geometry": {"LineString": [[144.9, -37.8], [145.12, -37.819]]}},
            ],
        }
    ]
}


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def _fake_aws(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]
) -> dict[str, Any]:
    # returns the body we sent aws, so a test can check what went out
    monkeypatch.setenv("AWS_LOCATION_KEY", "test-key")
    sent: dict[str, Any] = {}

    def post(url: str, **kwargs: Any) -> _FakeResponse:
        sent.update(kwargs["json"])
        return _FakeResponse(payload)

    monkeypatch.setattr(routing._session, "post", post)
    return sent


def _auth_headers(client: TestClient, credentials: dict[str, str]) -> dict[str, str]:
    token = client.post(LOGIN, json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_route_through_three_stops(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _fake_aws(monkeypatch, AWS_ROUTE)
    headers = _auth_headers(client, VOLUNTEER)

    response = client.post(
        ROUTE, json={"stops": [RMH, FOOTSCRAY, BOX_HILL]}, headers=headers
    )

    assert response.status_code == 200
    assert response.json() == {
        "distanceMeters": 30867,
        "durationSeconds": 2965,
        "geometry": {
            "type": "LineString",
            # the joining point appears once, not twice
            "coordinates": [[144.95597, -37.79867], [144.9, -37.8], [145.12, -37.819]],
        },
        "provider": "aws",
    }
    # the middle stop went to aws as a waypoint, in the order we were given
    assert sent["Origin"] == [144.95597, -37.79867]
    assert sent["Waypoints"] == [{"Position": [144.90000, -37.80000]}]
    assert sent["Destination"] == [145.12000, -37.81900]


def test_route_with_two_stops_sends_no_waypoints(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _fake_aws(monkeypatch, AWS_ROUTE)
    headers = _auth_headers(client, VOLUNTEER)

    response = client.post(ROUTE, json={"stops": [RMH, BOX_HILL]}, headers=headers)

    assert response.status_code == 200
    assert "Waypoints" not in sent


def test_route_rejects_too_few_or_too_many_stops(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    one = client.post(ROUTE, json={"stops": [RMH]}, headers=headers)
    too_many = client.post(ROUTE, json={"stops": [RMH] * 26}, headers=headers)

    assert one.status_code == 422
    assert one.json()["error"]["code"] == "VALIDATION_ERROR"
    assert too_many.status_code == 422
    assert too_many.json()["error"]["code"] == "VALIDATION_ERROR"


def test_route_provider_failure_is_a_routing_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AWS_LOCATION_KEY", "test-key")

    def blow_up(url: str, **kwargs: Any) -> None:
        raise requests.ConnectionError("aws is down")

    monkeypatch.setattr(routing._session, "post", blow_up)
    headers = _auth_headers(client, VOLUNTEER)

    response = client.post(ROUTE, json={"stops": [RMH, BOX_HILL]}, headers=headers)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ROUTING_ERROR"
