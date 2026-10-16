import pytest
from fastapi.testclient import TestClient

ORDERS = "/api/v0/orders/"
LOGIN = "/api/v0/auth/login"

"""
NB: some test cases here are hard coded to the seeded data in app/seed.sql. In the future
every test case should create the users, orders and runs it needs rather than relying on
what happens to be seeded.

Nothing a test writes survives it: conftest wraps each one in a transaction that is
rolled back, which is what the old preserve_db fixture used to do by hand.
"""
ADMIN = {"email": "admin", "password": "admin"}
VOLUNTEER = {"email": "tara@example.com", "password": "volunteer"}
ORGANISATION = {"email": "stores@rmh.example.com", "password": "organisation"}


# constructs auth headers for a request
def _auth_headers(client: TestClient, credentials: dict[str, str]) -> dict[str, str]:
    token = client.post(LOGIN, json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_create_and_then_get_an_order(
    client: TestClient,
) -> None:
    # get headers for an admin user (so API key correctly corresponds to an admin)
    headers = _auth_headers(client, ADMIN)

    # post an example order from the admin
    created = client.post(
        ORDERS,
        json={
            "fromLocationId": "1",
            "toLocationId": "2",
            "size": "SMALL",
            "urgency": "HIGH",
            "description": "Test parcel",
        },
        headers=headers,
    )

    # ensure 201 is returned for creating the order
    assert created.status_code == 201
    order_id = created.json()["orderId"]

    # ensure we can fetch with code 200 returned for success
    fetched = client.get(f"{ORDERS}{order_id}", headers=headers)
    assert fetched.status_code == 200

    # ensure the values correspond to what we pushed in (important for camel case conversion)
    body = fetched.json()
    assert body["status"] == "READY_FOR_PICKUP"
    assert body["runId"] is None
    assert body["from"] == {
        "locationId": "1",
        "name": "Royal Melbourne Hospital",
        "latitude": -37.79867,
        "longitude": 144.95597,
    }
    # there should only be a single event, which is the 'change' to READY_FOR_PICKUP when isntantiating the order
    assert len(body["events"]) == 1
    assert body["events"][0]["newStatus"] == "READY_FOR_PICKUP"


def test_only_admin_can_create_orders(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)
    response = client.post(
        ORDERS,
        json={
            "fromLocationId": "1",
            "toLocationId": "2",
            "size": "SMALL",
            "urgency": "HIGH",
            "description": "Test parcel",
        },
        headers=headers,
    )
    # volunteer should get 403
    assert response.status_code == 403

    headers = _auth_headers(client, ORGANISATION)
    response = client.post(
        ORDERS,
        json={
            "fromLocationId": "1",
            "toLocationId": "2",
            "size": "SMALL",
            "urgency": "HIGH",
            "description": "Test parcel",
        },
        headers=headers,
    )
    # organisation should get 403
    assert response.status_code == 403


def test_creating_an_order_rejects_an_unknown_location(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)
    response = client.post(
        ORDERS,
        # this is a location that doesn't exist in the dataabse. this isn't allowed
        # the frontend will instead call create locations endpoints when an admin fills out the order
        # creation form first, then will call create order
        json={
            "fromLocationId": "999",
            "toLocationId": "2",
            "size": "SMALL",
            "urgency": "HIGH",
            "description": "Test parcel",
        },
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LOCATION_NOT_FOUND"


def test_volunteer_only_sees_available_orders_that_fit_their_car_size(
    client: TestClient,
) -> None:

    admin_headers = _auth_headers(client, ADMIN)
    # create an order that will fit the volunteer (smallO)
    fitting = client.post(
        ORDERS,
        json={
            "fromLocationId": "1",
            "toLocationId": "2",
            "size": "SMALL",
            "urgency": "HIGH",
            "description": "Test parcel",
        },
        headers=admin_headers,
    )
    assert fitting.status_code == 201
    fitting_id = fitting.json()["orderId"]

    # create an order that wont fit the volunteer (large)
    too_big = client.post(
        ORDERS,
        json={
            "fromLocationId": "1",
            "toLocationId": "2",
            "size": "LARGE",
            "urgency": "HIGH",
            "description": "Test parcel",
        },
        headers=admin_headers,
    )
    assert too_big.status_code == 201
    too_big_id = too_big.json()["orderId"]

    # volunteer has a medium car
    headers = _auth_headers(client, VOLUNTEER)
    response = client.get(f"{ORDERS}available", headers=headers)

    assert response.status_code == 200
    orders = response.json()["orders"]
    # the order that does fit must be returned
    assert any(order["orderId"] == fitting_id for order in orders)
    # the order that doees not fit must not be returned
    assert not any(order["orderId"] == too_big_id for order in orders)


def test_organisation_only_sees_its_own_orders(client: TestClient) -> None:
    headers = _auth_headers(client, ORGANISATION)
    response = client.get(ORDERS, headers=headers)
    assert response.status_code == 200
    body = response.json()

    # hard coded based on current db
    assert all(
        order["fromOrganisation"]["userId"] == "3"
        or (order["toOrganisation"] or {}).get("userId") == "3"
        for order in body["orders"]
    )


def test_removing_an_order_already_on_a_run_is_rejected(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, ADMIN)
    response = client.post(f"{ORDERS}1/remove", headers=headers)
    # 409 should be returned as order with id 1 has a runa ssigned to it
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_NOT_AVAILABLE"


def test_track_order_returns_the_volunteers_last_position(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)
    response = client.get(f"{ORDERS}1/tracking", headers=headers)
    # 200 should be returned as order with id 1 is in progress in the db
    assert response.status_code == 200
    body = response.json()
    # it thus must also have a location assigned to it
    assert body["volunteer"] == {"userId": "2", "name": "Tara Nguyen"}
    assert body["latitude"] == -37.795


# a valid order body, each rule test below breaks one thing about it
def _order(**overrides: object) -> dict[str, object]:
    return {
        "fromLocationId": "1",
        "toLocationId": "2",
        "size": "SMALL",
        "urgency": "HIGH",
        "description": "Test parcel",
        **overrides,
    }


def test_an_order_cannot_go_to_where_it_came_from(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.post(ORDERS, json=_order(toLocationId="1"), headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_ORDER"


@pytest.mark.parametrize(
    "overrides",
    [
        {"description": "   "},
        {"description": "x" * 501},
        {"pickupNotes": "x" * 301},
        {"dueAt": "2000-01-01T00:00:00Z"},
    ],
)
def test_create_order_rejects_invalid_fields(
    client: TestClient, overrides: dict[str, str]
) -> None:
    headers = _auth_headers(client, ADMIN)

    response = client.post(ORDERS, json=_order(**overrides), headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_cancelled_order_cannot_be_removed_again(client: TestClient) -> None:
    headers = _auth_headers(client, ADMIN)
    order_id = client.post(ORDERS, json=_order(), headers=headers).json()["orderId"]

    assert client.post(f"{ORDERS}{order_id}/remove", headers=headers).status_code == 204
    again = client.post(f"{ORDERS}{order_id}/remove", headers=headers)

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ORDER_NOT_AVAILABLE"
