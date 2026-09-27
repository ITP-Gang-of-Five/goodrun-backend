# tests/test_runs.py
from fastapi.testclient import TestClient

RUNS = "/api/v0/runs/"
ORDERS = "/api/v0/orders/"
LOGIN = "/api/v0/auth/login"

ADMIN = {"email": "admin", "password": "admin"}
VOLUNTEER = {"email": "tara@example.com", "password": "volunteer"}
ORGANISATION = {"email": "stores@rmh.example.com", "password": "organisation"}

# from app/seed.sql: run 1 is Tara's existing IN_PROGRESS run with order 1 on it,
# order 2 is the one sitting unassigned in the available pool.
AVAILABLE_ORDER_ID = "2"
ALREADY_TAKEN_ORDER_ID = "1"


def _auth_headers(client: TestClient, credentials: dict[str, str]) -> dict[str, str]:
    token = client.post(LOGIN, json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_volunteer_can_create_a_run_from_an_available_order(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    created = client.post(RUNS, json={"orderIds": [AVAILABLE_ORDER_ID]}, headers=headers)
    assert created.status_code == 201
    run_id = created.json()["runId"]

    order = client.get(f"{ORDERS}{AVAILABLE_ORDER_ID}", headers=headers).json()
    assert order["runId"] == run_id
    assert order["status"] == "IN_TRANSIT"


def test_create_run_with_no_orders_returns_400(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    response = client.post(RUNS, json={"orderIds": []}, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RUN"


def test_create_run_with_already_taken_order_returns_409(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    response = client.post(RUNS, json={"orderIds": [ALREADY_TAKEN_ORDER_ID]}, headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_ALREADY_TAKEN"


def test_get_current_runs_includes_the_volunteers_in_progress_run(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    response = client.get(f"{RUNS}current", headers=headers)

    assert response.status_code == 200
    run_ids = [run["runId"] for run in response.json()["runs"]]
    assert "1" in run_ids  # the seeded run


def test_cancel_run_returns_its_order_to_the_available_pool(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)
    admin_headers = _auth_headers(client, ADMIN)
    run_id = client.post(RUNS, json={"orderIds": [AVAILABLE_ORDER_ID]}, headers=headers).json()["runId"]

    cancelled = client.post(f"{RUNS}{run_id}/cancel", headers=headers)
    assert cancelled.status_code == 204

    # once unassigned, the volunteer no longer has view access to it (per
    # get_order's access rules) - check via admin instead
    order = client.get(f"{ORDERS}{AVAILABLE_ORDER_ID}", headers=admin_headers).json()
    assert order["runId"] is None
    assert order["status"] == "READY_FOR_PICKUP"


def test_complete_run_marks_its_order_delivered(client: TestClient) -> None:
    headers = _auth_headers(client, VOLUNTEER)
    run_id = client.post(RUNS, json={"orderIds": [AVAILABLE_ORDER_ID]}, headers=headers).json()["runId"]

    completed = client.post(f"{RUNS}{run_id}/complete", headers=headers)
    assert completed.status_code == 204

    order = client.get(f"{ORDERS}{AVAILABLE_ORDER_ID}", headers=headers).json()
    assert order["status"] == "DELIVERED"


def test_admin_can_remove_a_run_without_returning_orders_to_the_pool(
    client: TestClient,
) -> None:
    volunteer_headers = _auth_headers(client, VOLUNTEER)
    admin_headers = _auth_headers(client, ADMIN)
    run_id = client.post(
        RUNS, json={"orderIds": [AVAILABLE_ORDER_ID]}, headers=volunteer_headers
    ).json()["runId"]

    removed = client.post(f"{RUNS}{run_id}/remove", headers=admin_headers)
    assert removed.status_code == 204

    order = client.get(f"{ORDERS}{AVAILABLE_ORDER_ID}", headers=volunteer_headers).json()
    assert order["status"] == "CANCELLED"
    available = client.get(f"{ORDERS}available", headers=volunteer_headers).json()
    assert order["orderId"] not in [o["orderId"] for o in available["orders"]]


def test_get_runs_forbidden_for_organisation(client: TestClient) -> None:
    headers = _auth_headers(client, ORGANISATION)

    response = client.get(RUNS, headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
