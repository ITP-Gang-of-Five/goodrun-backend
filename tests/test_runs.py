# tests/test_runs.py
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from psycopg.errors import UniqueViolation

from app.common.validation import RUN_MAX_ORDERS
from app.queries import Queries
from app.storage import Run, RunStatus

RUNS = "/api/v0/runs/"
ORDERS = "/api/v0/orders/"
LOGIN = "/api/v0/auth/login"

ADMIN = {"email": "admin", "password": "admin"}
VOLUNTEER = {"email": "tara@example.com", "password": "volunteer"}
ORGANISATION = {"email": "stores@rmh.example.com", "password": "organisation"}


AVAILABLE_ORDER_ID = "2"
ALREADY_TAKEN_ORDER_ID = "1"


def _auth_headers(client: TestClient, credentials: dict[str, str]) -> dict[str, str]:
    token = client.post(LOGIN, json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _free_volunteer(client: TestClient) -> dict[str, str]:
    # Tara (the seeded volunteer) is already on a run, and a volunteer can only be on one
    # at a time, so anything that starts a run does it as a new volunteer with no run yet
    client.post(
        "/api/v0/volunteers/",
        json={
            "name": "Free Volunteer",
            "email": "free.volunteer@example.com",
            "password": "hunter22",
            "carSize": "LARGE",
        },
        headers=_auth_headers(client, ADMIN),
    )
    return _auth_headers(
        client, {"email": "free.volunteer@example.com", "password": "hunter22"}
    )


def _step(order_id: str, step_type: str) -> dict[str, str]:
    return {"orderId": order_id, "type": step_type}


def _route(*order_ids: str) -> dict[str, Any]:
    # the simplest route: pick everything up, then drop it all off in the same order
    return {
        "route": [_step(order_id, "PICKUP") for order_id in order_ids]
        + [_step(order_id, "DROPOFF") for order_id in order_ids]
    }


def _create_run(client: TestClient, headers: dict[str, str], *order_ids: str) -> str:
    created = client.post(RUNS, json=_route(*order_ids), headers=headers)
    assert created.status_code == 201
    return str(created.json()["runId"])


def _complete_step(
    client: TestClient, headers: dict[str, str], run_id: str, position: int
) -> Response:
    return client.post(f"{RUNS}{run_id}/steps/{position}/complete", headers=headers)


def _new_order(client: TestClient) -> str:
    # another order in the available pool, for runs with more than one
    created = client.post(
        ORDERS,
        json={
            "fromLocationId": "1",
            "toLocationId": "2",
            "size": "SMALL",
            "urgency": "LOW",
            "description": "Test parcel",
        },
        headers=_auth_headers(client, ADMIN),
    )
    return str(created.json()["orderId"])


def _order_status(client: TestClient, order_id: str) -> str:
    order = client.get(f"{ORDERS}{order_id}", headers=_auth_headers(client, ADMIN))
    return str(order.json()["status"])


"""
------------------------------------------------------------------------------------------
CREATING A RUN
------------------------------------------------------------------------------------------
"""


def test_volunteer_can_create_a_run_from_an_available_order(client: TestClient) -> None:
    headers = _free_volunteer(client)

    run_id = _create_run(client, headers, AVAILABLE_ORDER_ID)

    order = client.get(f"{ORDERS}{AVAILABLE_ORDER_ID}", headers=headers).json()
    assert order["runId"] == run_id
    # it's on the run, but nobody has picked it up yet
    assert order["status"] == "READY_FOR_PICKUP"
    available = client.get(f"{ORDERS}available", headers=headers).json()
    assert AVAILABLE_ORDER_ID not in [o["orderId"] for o in available["orders"]]


def test_a_run_comes_back_with_its_route_in_the_planned_order(
    client: TestClient,
) -> None:
    headers = _free_volunteer(client)
    second = _new_order(client)
    route = [
        _step(AVAILABLE_ORDER_ID, "PICKUP"),
        _step(second, "PICKUP"),
        _step(second, "DROPOFF"),
        _step(AVAILABLE_ORDER_ID, "DROPOFF"),
    ]
    run_id = client.post(RUNS, json={"route": route}, headers=headers).json()["runId"]

    run = client.get(f"{RUNS}{run_id}", headers=headers).json()

    assert [{"orderId": s["orderId"], "type": s["type"]} for s in run["steps"]] == route
    assert all(step["completedAt"] is None for step in run["steps"])
    # orders are listed in the order they get picked up
    assert [order["orderId"] for order in run["orders"]] == [AVAILABLE_ORDER_ID, second]


def test_create_run_with_no_orders_returns_400(client: TestClient) -> None:
    headers = _free_volunteer(client)

    response = client.post(RUNS, json={"route": []}, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RUN"


def test_a_route_that_does_not_make_sense_returns_400(client: TestClient) -> None:
    headers = _free_volunteer(client)
    order = AVAILABLE_ORDER_ID
    impossible_routes = [
        # dropped off before it's picked up
        [_step(order, "DROPOFF"), _step(order, "PICKUP")],
        # never dropped off
        [_step(order, "PICKUP")],
        # picked up twice
        [_step(order, "PICKUP"), _step(order, "PICKUP"), _step(order, "DROPOFF")],
        # dropped off twice
        [_step(order, "PICKUP"), _step(order, "DROPOFF"), _step(order, "DROPOFF")],
    ]

    for route in impossible_routes:
        response = client.post(RUNS, json={"route": route}, headers=headers)
        assert response.status_code == 400, route
        assert response.json()["error"]["code"] == "INVALID_RUN"


def test_create_run_with_already_taken_order_returns_409(client: TestClient) -> None:
    headers = _free_volunteer(client)

    response = client.post(RUNS, json=_route(ALREADY_TAKEN_ORDER_ID), headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_ALREADY_TAKEN"


def test_create_run_with_too_many_orders_returns_400(client: TestClient) -> None:
    headers = _free_volunteer(client)
    order_ids = [str(i) for i in range(1, RUN_MAX_ORDERS + 2)]

    response = client.post(RUNS, json=_route(*order_ids), headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RUN"


def test_create_run_without_a_car_size_returns_order_too_large(
    client: TestClient,
) -> None:
    # a volunteer created without a car size can't build a run until they set one
    client.post(
        "/api/v0/volunteers/",
        json={"name": "No Car", "email": "no.car@example.com", "password": "hunter22"},
        headers=_auth_headers(client, ADMIN),
    )
    headers = _auth_headers(
        client, {"email": "no.car@example.com", "password": "hunter22"}
    )

    response = client.post(RUNS, json=_route(AVAILABLE_ORDER_ID), headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_TOO_LARGE"


"""
------------------------------------------------------------------------------------------
DOING A RUN
------------------------------------------------------------------------------------------
"""


def test_picking_up_and_dropping_off_moves_the_order_along(client: TestClient) -> None:
    headers = _free_volunteer(client)
    run_id = _create_run(client, headers, AVAILABLE_ORDER_ID)

    assert _complete_step(client, headers, run_id, 0).status_code == 204
    assert _order_status(client, AVAILABLE_ORDER_ID) == "IN_TRANSIT"
    run = client.get(f"{RUNS}{run_id}", headers=headers).json()
    assert run["steps"][0]["completedAt"] is not None
    assert run["status"] == "IN_PROGRESS"

    assert _complete_step(client, headers, run_id, 1).status_code == 204
    assert _order_status(client, AVAILABLE_ORDER_ID) == "DELIVERED"


def test_the_last_step_completes_the_run(client: TestClient) -> None:
    headers = _free_volunteer(client)
    run_id = _create_run(client, headers, AVAILABLE_ORDER_ID)

    _complete_step(client, headers, run_id, 0)
    _complete_step(client, headers, run_id, 1)

    run = client.get(f"{RUNS}{run_id}", headers=headers).json()
    assert run["status"] == "COMPLETED"
    assert run["completedAt"] is not None


def test_steps_can_be_done_out_of_the_planned_order(client: TestClient) -> None:
    headers = _free_volunteer(client)
    second = _new_order(client)
    # planned: pick up 2, pick up second, drop off 2, drop off second
    run_id = _create_run(client, headers, AVAILABLE_ORDER_ID, second)

    # but they grab the second order first and drop it off straight away
    assert _complete_step(client, headers, run_id, 1).status_code == 204
    assert _complete_step(client, headers, run_id, 3).status_code == 204

    assert _order_status(client, second) == "DELIVERED"
    assert _order_status(client, AVAILABLE_ORDER_ID) == "READY_FOR_PICKUP"


def test_an_order_cannot_be_dropped_off_before_it_is_picked_up(
    client: TestClient,
) -> None:
    headers = _free_volunteer(client)
    run_id = _create_run(client, headers, AVAILABLE_ORDER_ID)

    response = _complete_step(client, headers, run_id, 1)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STEP_OUT_OF_ORDER"
    assert _order_status(client, AVAILABLE_ORDER_ID) == "READY_FOR_PICKUP"


def test_completing_a_step_twice_changes_nothing(client: TestClient) -> None:
    # e.g. the app retrying on bad signal, including after the run has finished
    headers = _free_volunteer(client)
    run_id = _create_run(client, headers, AVAILABLE_ORDER_ID)
    _complete_step(client, headers, run_id, 0)
    _complete_step(client, headers, run_id, 1)
    finished = client.get(f"{RUNS}{run_id}", headers=headers).json()

    assert _complete_step(client, headers, run_id, 1).status_code == 204
    assert client.get(f"{RUNS}{run_id}", headers=headers).json() == finished


def test_a_step_that_does_not_exist_returns_404(client: TestClient) -> None:
    headers = _free_volunteer(client)
    run_id = _create_run(client, headers, AVAILABLE_ORDER_ID)

    response = _complete_step(client, headers, run_id, 2)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "STEP_NOT_FOUND"


def test_only_the_runs_volunteer_can_complete_its_steps(client: TestClient) -> None:
    run_id = _create_run(client, _free_volunteer(client), AVAILABLE_ORDER_ID)

    response = _complete_step(client, _auth_headers(client, VOLUNTEER), run_id, 0)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RUN_NOT_ASSIGNED"


def test_a_volunteer_can_only_be_on_one_run_at_a_time(client: TestClient) -> None:
    # Tara is already part way through the seeded run
    headers = _auth_headers(client, VOLUNTEER)

    response = client.post(RUNS, json=_route(AVAILABLE_ORDER_ID), headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_ON_A_RUN"
    # and the order wasn't taken off anyone else
    assert _order_status(client, AVAILABLE_ORDER_ID) == "READY_FOR_PICKUP"


def test_a_new_run_can_be_started_once_the_last_one_is_finished(
    client: TestClient,
) -> None:
    headers = _free_volunteer(client)
    run_id = _create_run(client, headers, AVAILABLE_ORDER_ID)
    _complete_step(client, headers, run_id, 0)
    _complete_step(client, headers, run_id, 1)

    response = client.post(RUNS, json=_route(_new_order(client)), headers=headers)

    assert response.status_code == 201


def test_the_database_refuses_a_second_run_in_progress(queries: Queries) -> None:
    # the backstop for two runs being started at the same moment. Tara (id 2) is
    # already on the seeded run
    with pytest.raises(UniqueViolation):
        queries.add_run(
            Run(
                id=0,
                status=RunStatus.IN_PROGRESS,
                volunteer_id=2,
                created_at=datetime.now(UTC),
            )
        )


"""
------------------------------------------------------------------------------------------
VIEWING RUNS
------------------------------------------------------------------------------------------
"""


def test_get_current_runs_includes_the_volunteers_in_progress_run(
    client: TestClient,
) -> None:
    headers = _auth_headers(client, VOLUNTEER)

    response = client.get(f"{RUNS}current", headers=headers)

    assert response.status_code == 200
    runs = {run["runId"]: run for run in response.json()["runs"]}
    # the seeded run, with order 1 picked up but not yet dropped off
    seeded = runs["1"]
    assert [step["type"] for step in seeded["steps"]] == ["PICKUP", "DROPOFF"]
    assert seeded["steps"][0]["completedAt"] is not None
    assert seeded["steps"][1]["completedAt"] is None


def test_get_runs_forbidden_for_organisation(client: TestClient) -> None:
    headers = _auth_headers(client, ORGANISATION)

    response = client.get(RUNS, headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


"""
------------------------------------------------------------------------------------------
CANCELLING AND REMOVING RUNS
------------------------------------------------------------------------------------------
"""


def test_cancel_run_returns_its_order_to_the_available_pool(client: TestClient) -> None:
    headers = _free_volunteer(client)
    admin_headers = _auth_headers(client, ADMIN)
    run_id = _create_run(client, headers, AVAILABLE_ORDER_ID)

    cancelled = client.post(f"{RUNS}{run_id}/cancel", headers=headers)
    assert cancelled.status_code == 204

    # once unassigned, the volunteer no longer has view access to it (per
    # get_order's access rules) - check via admin instead
    order = client.get(f"{ORDERS}{AVAILABLE_ORDER_ID}", headers=admin_headers).json()
    assert order["runId"] is None
    assert order["status"] == "READY_FOR_PICKUP"
    # like its orders, a cancelled run's route is released with them
    run = client.get(f"{RUNS}{run_id}", headers=admin_headers).json()
    assert run["orders"] == []
    assert run["steps"] == []


def test_a_run_cannot_be_cancelled_once_something_is_picked_up(
    client: TestClient,
) -> None:
    # it's in the volunteer's car, so it can't go back in the pool for someone else
    headers = _free_volunteer(client)
    run_id = _create_run(client, headers, AVAILABLE_ORDER_ID)
    _complete_step(client, headers, run_id, 0)

    response = client.post(f"{RUNS}{run_id}/cancel", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_ALREADY_PICKED_UP"
    assert _order_status(client, AVAILABLE_ORDER_ID) == "IN_TRANSIT"


def test_admin_can_remove_a_run_without_returning_orders_to_the_pool(
    client: TestClient,
) -> None:
    volunteer_headers = _free_volunteer(client)
    admin_headers = _auth_headers(client, ADMIN)
    run_id = _create_run(client, volunteer_headers, AVAILABLE_ORDER_ID)

    removed = client.post(f"{RUNS}{run_id}/remove", headers=admin_headers)
    assert removed.status_code == 204

    order = client.get(
        f"{ORDERS}{AVAILABLE_ORDER_ID}", headers=volunteer_headers
    ).json()
    assert order["status"] == "CANCELLED"
    available = client.get(f"{ORDERS}available", headers=volunteer_headers).json()
    assert order["orderId"] not in [o["orderId"] for o in available["orders"]]


def test_removing_a_run_part_way_keeps_what_was_already_delivered(
    client: TestClient,
) -> None:
    volunteer_headers = _free_volunteer(client)
    second = _new_order(client)
    run_id = _create_run(client, volunteer_headers, AVAILABLE_ORDER_ID, second)
    # pick up and drop off the first order only
    _complete_step(client, volunteer_headers, run_id, 0)
    _complete_step(client, volunteer_headers, run_id, 2)

    client.post(f"{RUNS}{run_id}/remove", headers=_auth_headers(client, ADMIN))

    assert _order_status(client, AVAILABLE_ORDER_ID) == "DELIVERED"
    assert _order_status(client, second) == "CANCELLED"


# a finished run is final: removing a completed one must not turn its delivered orders into cancelled ones
def test_admin_cannot_remove_a_completed_run(client: TestClient) -> None:
    volunteer_headers = _free_volunteer(client)
    admin_headers = _auth_headers(client, ADMIN)
    run_id = _create_run(client, volunteer_headers, AVAILABLE_ORDER_ID)
    _complete_step(client, volunteer_headers, run_id, 0)
    _complete_step(client, volunteer_headers, run_id, 1)

    removed = client.post(f"{RUNS}{run_id}/remove", headers=admin_headers)

    assert removed.status_code == 409
    assert removed.json()["error"]["code"] == "RUN_NOT_IN_PROGRESS"
    assert _order_status(client, AVAILABLE_ORDER_ID) == "DELIVERED"
