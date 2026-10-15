from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response
from psycopg.errors import UniqueViolation

from app.api.deps import AdminOrVolunteerUser, AdminUser, VolunteerUser
from app.common.users import user_ref_from
from app.common.validation import RUN_MAX_ORDERS
from app.errors import ApiError
from app.orders.schemas import OrderOut
from app.orders.serializers import orders_out
from app.queries import Queries, QueriesDep
from app.runs.schemas import (
    CreateRunRequest,
    RunIdResponse,
    RunOut,
    RunsResponse,
    RunStepIn,
    RunStepOut,
)
from app.storage import (
    CarSize,
    OrderEvent,
    OrderStatus,
    Role,
    Run,
    RunStatus,
    RunStep,
    RunStepType,
    User,
)

router = APIRouter(prefix="/runs", tags=["runs"])


"""
------------------------------------------------------------------------------------------
HELPER FUNCTIONS
------------------------------------------------------------------------------------------
"""


# converts multiple runs into RunOuts fetching all orders, steps and volunteers in bulk
def _runs_out(db: Queries, runs: list[Run]) -> list[RunOut]:
    run_ids = [run.id for run in runs]
    orders = db.list_orders_for_runs(run_ids)

    # group orders by the run they are in
    orders_by_run: dict[int, list[OrderOut]] = defaultdict(list)
    for order, out in zip(orders, orders_out(db, orders), strict=True):
        assert order.run_id is not None
        orders_by_run[order.run_id].append(out)

    #add each of their steps which come back in the route's order
    steps_by_run: dict[int, list[RunStepOut]] = defaultdict(list)
    for step in db.list_steps_for_runs(run_ids):
        steps_by_run[step.run_id].append(
            RunStepOut(
                order_id=str(step.order_id),
                type=step.type,
                completed_at=step.completed_at,
            )
        )

    volunteers = db.get_users({run.volunteer_id for run in runs if run.volunteer_id})
    return [
        RunOut(
            run_id=str(run.id),
            status=run.status,
            volunteer=user_ref_from(volunteers, run.volunteer_id),
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
            orders=orders_by_run[run.id],
            steps=steps_by_run[run.id],
        )
        for run in runs
    ]


def _run_out(db: Queries, run: Run) -> RunOut:
    return _runs_out(db, [run])[0]


def _record_event(db: Queries, order_id: int, status: OrderStatus) -> None:
    db.add_order_event(
        OrderEvent(
            id=0, order_id=order_id, new_status=status, created_at=datetime.now(UTC)
        )
    )


# a volunteer can view a run assigned to them (or, per the API agreement's literal
# wording, an unassigned one - never happens in practice since volunteer_id is
# always set, but kept for correctness); an admin can view any run
def _can_view(actor: User, run: Run) -> bool:
    if actor.role == Role.ADMIN:
        return True
    return run.volunteer_id is None or run.volunteer_id == actor.id


def _require_visible_run(db: Queries, actor: User, run_id: int) -> Run:
    run = db.get_run(run_id)
    # not found rather than forbidden, so runs can't be probed for existence
    if run is None or not _can_view(actor, run):
        raise ApiError(404, "RUN_NOT_FOUND", "No run with that id")
    return run


"""
A run can only be changed (cancelled, completed or removed) while it's in progress. Once it's
completed or cancelled it's final. Without this, e.g. removing a completed run would turn its
delivered orders into cancelled ones
"""


def _require_in_progress(run: Run) -> None:
    if run.status != RunStatus.IN_PROGRESS:
        raise ApiError(409, "RUN_NOT_IN_PROGRESS", "This run isn't in progress")


"""
Cancels an in progress run, the one place a run is cancelled along with its orders:
- order_status: what each order on it that hasn't been delivered becomes
- release_orders: if true those orders are taken off the run (back into the pool), else
  they stay on it
Orders already delivered are left alone, since a delivery that happened can't be undone
"""
def _cancel_run(
    db: Queries, run: Run, *, order_status: OrderStatus, release_orders: bool = False
) -> None:
    _require_in_progress(run)

    orders = [
        order
        for order in db.list_orders_for_run(run.id)
        if order.status != OrderStatus.DELIVERED
    ]
    db.set_orders_run(
        [order.id for order in orders],
        None if release_orders else run.id,
        order_status,
    )
    for order in orders:
        # only an actual change goes in the order's history
        if order.status != order_status:
            _record_event(db, order.id, order_status)

    db.update_run(run.model_copy(update={"status": RunStatus.CANCELLED}))


def _already_on_a_run() -> ApiError:
    return ApiError(
        409, "ALREADY_ON_A_RUN", "You're already on a run, finish or cancel it first"
    )


def _invalid_run(description: str) -> ApiError:
    return ApiError(400, "INVALID_RUN", description)


"""
Checks a route is one a volunteer could actually do: every order is picked up exactly once
and dropped off exactly once, and never dropped off before it's been picked up. Returns the
orders it's made of (in pickup order) alongside its steps with the ids turned into numbers
"""
def _parse_route(
    route: list[RunStepIn],
) -> tuple[list[int], list[tuple[int, RunStepType]]]:
    # order ids arrive as strings per the API agreement
    try:
        steps = [(int(step.order_id), step.type) for step in route]
    except ValueError as exc:
        raise ApiError(
            422, "VALIDATION_ERROR", "route orderIds must be numeric ids"
        ) from exc

    picked_up: list[int] = []
    dropped_off: set[int] = set()
    for order_id, step_type in steps:
        if step_type == RunStepType.PICKUP:
            if order_id in picked_up:
                raise _invalid_run(f"Order {order_id} is picked up more than once")
            picked_up.append(order_id)
        elif order_id not in picked_up:
            raise _invalid_run(f"Order {order_id} is dropped off before it's picked up")
        elif order_id in dropped_off:
            raise _invalid_run(f"Order {order_id} is dropped off more than once")
        else:
            dropped_off.add(order_id)

    if not picked_up:
        raise _invalid_run("A run needs at least one order")
    never_dropped_off = [
        order_id for order_id in picked_up if order_id not in dropped_off
    ]
    if never_dropped_off:
        raise _invalid_run(f"Order {never_dropped_off[0]} is never dropped off")
    if len(picked_up) > RUN_MAX_ORDERS:
        raise _invalid_run(f"A run can have at most {RUN_MAX_ORDERS} orders")

    return picked_up, steps


# fetches a run only if it exists and is assigned to the calling volunteer, used by
# anything a volunteer does to their run. the run is locked until the request finishes
# so two changes to it at once (e.g. finishing the last two steps) can't miss each other
def _require_own_run(db: Queries, volunteer: User, run_id: int) -> Run:
    run = db.lock_run(run_id)
    if run is None:
        raise ApiError(404, "RUN_NOT_FOUND", "No run with that id")
    if run.volunteer_id != volunteer.id:
        raise ApiError(403, "RUN_NOT_ASSIGNED", "This run isn't assigned to you")
    return run


"""
------------------------------------------------------------------------------------------
API ENDPOINTS
------------------------------------------------------------------------------------------
"""


# volunteers get their own runs (history + in progress); admins get everyone's,
# optionally filtered to one volunteer via ?volunteerId=
@router.get("/")
def get_runs(
    actor: AdminOrVolunteerUser,
    db: QueriesDep,
    volunteer_id: Annotated[int | None, Query(alias="volunteerId")] = None,
) -> RunsResponse:
    if actor.role == Role.VOLUNTEER:
        # volunteerId is ignored for a volunteer, they only ever see their own
        runs = db.list_runs_for_volunteer(actor.id)
    elif volunteer_id is not None:
        runs = db.list_runs_for_volunteer(volunteer_id)
    else:
        runs = db.list_runs()

    return RunsResponse(runs=_runs_out(db, runs))


@router.get("/current")
def get_current_runs(volunteer: VolunteerUser, db: QueriesDep) -> RunsResponse:
    runs = db.list_runs_for_volunteer(volunteer.id, RunStatus.IN_PROGRESS)
    return RunsResponse(runs=_runs_out(db, runs))


@router.get("/{run_id}")
def get_run(run_id: int, actor: AdminOrVolunteerUser, db: QueriesDep) -> RunOut:
    return _run_out(db, _require_visible_run(db, actor, run_id))


# builds and immediately starts a run out of the volunteer's chosen orders
@router.post("/", status_code=201)
def create_run(
    body: CreateRunRequest, volunteer: VolunteerUser, db: QueriesDep
) -> RunIdResponse:
    order_ids, route = _parse_route(body.route)

    # one run at a time, they have to finish (or cancel) the one they're on first
    if db.list_runs_for_volunteer(volunteer.id, RunStatus.IN_PROGRESS):
        raise _already_on_a_run()

    if volunteer.car_size is None:
        raise ApiError(
            409, "ORDER_TOO_LARGE", "You must set a car size before building a run"
        )

    # only returns the ones still unassigned & READY_FOR_PICKUP (locked FOR UPDATE),
    # so a short list back means someone else took one in the meantime
    locked = db.lock_orders_for_run(order_ids)
    if len(locked) != len(order_ids):
        raise ApiError(
            409,
            "ORDER_ALREADY_TAKEN",
            "One of the selected orders is no longer available",
        )

    car_sizes = list(CarSize)
    volunteer_rank = car_sizes.index(volunteer.car_size)
    if any(car_sizes.index(order.size) > volunteer_rank for order in locked):
        raise ApiError(
            409, "ORDER_TOO_LARGE", "One of the selected orders doesn't fit your car"
        )

    try:
        run = db.add_run(
            Run(
                id=0,
                status=RunStatus.IN_PROGRESS,
                volunteer_id=volunteer.id,
                created_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
            )
        )
    except UniqueViolation:
        # another request started a run for them since the check above (e.g. a double
        # tap), and the database's one run at a time rule caught it
        raise _already_on_a_run() from None
    # the orders are now on this run, so nobody else is offered them. they stay
    # READY_FOR_PICKUP until the volunteer actually picks each one up
    db.set_orders_run(order_ids, run.id, OrderStatus.READY_FOR_PICKUP)
    db.add_run_steps(
        [
            RunStep(run_id=run.id, order_id=order_id, type=step_type, position=position)
            for position, (order_id, step_type) in enumerate(route)
        ]
    )

    return RunIdResponse(run_id=str(run.id))


@router.post("/{run_id}/cancel", status_code=204)
def cancel_run(run_id: int, volunteer: VolunteerUser, db: QueriesDep) -> Response:
    run = _require_own_run(db, volunteer, run_id)
    _require_in_progress(run)
    # once something's been picked up it's in the volunteer's car, so putting it back
    # in the pool would offer it to someone else. they have to finish dropping off
    if any(step.completed_at for step in db.list_steps_for_run(run.id)):
        raise ApiError(
            409,
            "ORDER_ALREADY_PICKED_UP",
            "Something on this run has already been picked up, so it can't be cancelled",
        )
    # cancelling releases every order back into the available pool
    _cancel_run(db, run, order_status=OrderStatus.READY_FOR_PICKUP, release_orders=True)
    return Response(status_code=204)


"""
The volunteer has done one step of their route, picking up or dropping off an order. Steps
can be done in any order, except an order can't be dropped off before it's been picked up.
Picking up puts the order IN_TRANSIT, dropping off makes it DELIVERED, and once every step
is done the run is COMPLETED.
"""


@router.post("/{run_id}/steps/{position}/complete", status_code=204)
def complete_run_step(
    run_id: int, position: int, volunteer: VolunteerUser, db: QueriesDep
) -> Response:
    run = _require_own_run(db, volunteer, run_id)
    steps = db.list_steps_for_run(run.id)
    step = next((step for step in steps if step.position == position), None)
    if step is None:
        raise ApiError(404, "STEP_NOT_FOUND", "This run has no step at that position")

    # doing a step that's already done changes nothing, so an app retrying on bad
    # signal can't break anything (even once it has completed the run)
    if step.completed_at is not None:
        return Response(status_code=204)
    _require_in_progress(run)

    if step.type == RunStepType.DROPOFF and not any(
        other.completed_at
        for other in steps
        if other.order_id == step.order_id and other.type == RunStepType.PICKUP
    ):
        raise ApiError(
            409,
            "STEP_OUT_OF_ORDER",
            "This order has to be picked up before it's dropped off",
        )

    now = datetime.now(UTC)
    db.complete_run_step(step, now)
    new_status = (
        OrderStatus.IN_TRANSIT
        if step.type == RunStepType.PICKUP
        else OrderStatus.DELIVERED
    )
    db.set_orders_run([step.order_id], run.id, new_status)
    _record_event(db, step.order_id, new_status)

    # that was the last step, so the run is done
    if all(other.completed_at or other is step for other in steps):
        db.update_run(
            run.model_copy(update={"status": RunStatus.COMPLETED, "completed_at": now})
        )
    return Response(status_code=204)


# admin kill switch - unlike a volunteer cancel, orders do NOT return to the pool
@router.post("/{run_id}/remove", status_code=204)
def remove_run(run_id: int, admin: AdminUser, db: QueriesDep) -> Response:
    run = db.get_run(run_id)
    if run is None:
        raise ApiError(404, "RUN_NOT_FOUND", "No run with that id")
    # unlike a volunteer cancelling, the orders stay on the run and are cancelled with it
    # (apart from any already delivered)
    _cancel_run(db, run, order_status=OrderStatus.CANCELLED)
    return Response(status_code=204)
