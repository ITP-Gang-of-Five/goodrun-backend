from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.locations import locations as locations_api

LOCATIONS = "/api/v0/locations/"
AUTOCOMPLETE = "/api/v0/locations/autocomplete"
GEOCODE = "/api/v0/locations/geocode"
LOGIN = "/api/v0/auth/login"

ADMIN = {"email": "admin", "password": "admin"}
VOLUNTEER = {"email": "tara@example.com", "password": "volunteer"}

# aws mixes Place and Query items into one list, only the Place ones are useful
SUGGEST_RESULT = {
    "ResultItems": [
        {
            "SuggestResultItemType": "Place",
            "Title": "The Royal Melbourne Hospital",
            "Place": {
                "PlaceId": "place-abc",
                "Address": {
                    "Label": (
                        "The Royal Melbourne Hospital, 300 Grattan St, "
                        "Parkville VIC 3000, Australia"
                    )
                },
            },
        },
        {"SuggestResultItemType": "Query", "Title": "royal melbourne hospital"},
    ]
}

# aws returns Position as [longitude, latitude]
GEOCODE_RESULT = {
    "ResultItems": [
        {
            "Title": "Royal Melbourne Hospital",
            "Address": {"Label": "300 Grattan St, Parkville VIC 3050, Australia"},
            "Position": [144.956776, -37.799572],
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


def _fake_aws(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> None:
    monkeypatch.setenv("AWS_LOCATION_KEY", "test-key")
    response = _FakeResponse(payload)
    monkeypatch.setattr(locations_api._session, "get", lambda *a, **k: response)
    monkeypatch.setattr(locations_api._session, "post", lambda *a, **k: response)


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


def test_autocomplete_returns_suggestions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_aws(monkeypatch, SUGGEST_RESULT)
    headers = _auth_headers(client, ADMIN)

    response = client.get(
        AUTOCOMPLETE, params={"query": "royal melbourne"}, headers=headers
    )

    assert response.status_code == 200
    # the Query item is dropped, only the Place one comes back
    assert response.json() == {
        "suggestions": [
            {
                "suggestionId": "place-abc",
                "label": (
                    "The Royal Melbourne Hospital, 300 Grattan St, "
                    "Parkville VIC 3000, Australia"
                ),
            }
        ]
    }


def test_geocode_requires_a_parameter(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.get(GEOCODE, headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_geocode_rejects_both_parameters(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.get(
        GEOCODE,
        params={"suggestionId": "place-abc", "address": "300 Grattan St"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_geocode_by_address_returns_a_location(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_aws(monkeypatch, GEOCODE_RESULT)
    headers = _auth_headers(client, ADMIN)

    response = client.get(
        GEOCODE, params={"address": "300 Grattan St, Parkville"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json() == {
        "address": "300 Grattan St, Parkville VIC 3050, Australia",
        "latitude": -37.799572,
        "longitude": 144.956776,
    }


def test_geocode_with_no_results_is_not_found(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_aws(monkeypatch, {"ResultItems": []})
    headers = _auth_headers(client, ADMIN)

    response = client.get(
        GEOCODE, params={"address": "nowhere at all"}, headers=headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LOCATION_NOT_FOUND"
