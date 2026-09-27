from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import AdminOrVolunteerUser, AdminUser, VolunteerUser
from app.common.users import user_ref
from app.errors import ApiError
from app.orders.serializers import order_out
from app.queries import Queries, QueriesDep
from app.runs.schemas import CreateRunRequest, RunIdResponse, RunOut, RunsResponse
from app.storage import CarSize, OrderEvent, OrderStatus, Role, Run, RunStatus, User

router = APIRouter(prefix="/runs", tags=["runs"])


"""
------------------------------------------------------------------------------------------
HELPER FUNCTIONS
------------------------------------------------------------------------------------------
"""


def _run_out(db: Queries, run: Run) -> RunOut:
    return RunOut(
        run_id=str(run.id),
        status=run.status,
        volunteer=user_ref(db, run.volunteer_id),
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        orders=[order_out(db, order) for order in db.list_orders_for_run(run.id)],
    )


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


# fetches a run only if it exists and is assigned to the calling volunteer,
# used by cancel/complete
def _require_own_run(db: Queries, volunteer: User, run_id: int) -> Run:
    run = db.get_run(run_id)
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

    return RunsResponse(runs=[_run_out(db, run) for run in runs])


@router.get("/current")
def get_current_runs(volunteer: VolunteerUser, db: QueriesDep) -> RunsResponse:
    runs = db.list_runs_for_volunteer(volunteer.id, RunStatus.IN_PROGRESS)
    return RunsResponse(runs=[_run_out(db, run) for run in runs])


@router.get("/{run_id}")
def get_run(run_id: int, actor: AdminOrVolunteerUser, db: QueriesDep) -> RunOut:
    return _run_out(db, _require_visible_run(db, actor, run_id))


# builds and immediately starts a run out of the volunteer's chosen orders
@router.post("/", status_code=201)
def create_run(
    body: CreateRunRequest, volunteer: VolunteerUser, db: QueriesDep
) -> RunIdResponse:
    # order ids arrive as strings per the API agreement
    try:
        order_ids = [int(order_id) for order_id in body.order_ids]
    except ValueError as exc:
        raise ApiError(422, "VALIDATION_ERROR", "orderIds must be numeric ids") from exc

    if not order_ids or len(set(order_ids)) != len(order_ids):
        raise ApiError(
            400, "INVALID_RUN", "orderIds must be non-empty with no duplicates"
        )

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

    run = db.add_run(
        Run(
            id=0,
            status=RunStatus.IN_PROGRESS,
            volunteer_id=volunteer.id,
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
        )
    )
    db.set_orders_run(order_ids, run.id, OrderStatus.IN_TRANSIT)
    for sequence, order_id in enumerate(order_ids):
        # the volunteer's intended delivery order; not required by the agreement's
        # text but the column already exists, so it's worth populating
        db.set_order_sequence(order_id, sequence)
        _record_event(db, order_id, OrderStatus.IN_TRANSIT)

    return RunIdResponse(run_id=str(run.id))


@router.post("/{run_id}/cancel", status_code=204)
def cancel_run(run_id: int, volunteer: VolunteerUser, db: QueriesDep) -> Response:
    run = _require_own_run(db, volunteer, run_id)
    if run.status != RunStatus.IN_PROGRESS:
        raise ApiError(409, "RUN_NOT_IN_PROGRESS", "This run isn't in progress")

    order_ids = [order.id for order in db.list_orders_for_run(run.id)]
    # cancelling releases every order back into the available pool
    db.set_orders_run(order_ids, None, OrderStatus.READY_FOR_PICKUP)
    for order_id in order_ids:
        _record_event(db, order_id, OrderStatus.READY_FOR_PICKUP)

    db.update_run(run.model_copy(update={"status": RunStatus.CANCELLED}))
    return Response(status_code=204)


@router.post("/{run_id}/complete", status_code=204)
def complete_run(run_id: int, volunteer: VolunteerUser, db: QueriesDep) -> Response:
    run = _require_own_run(db, volunteer, run_id)
    if run.status != RunStatus.IN_PROGRESS:
        raise ApiError(409, "RUN_NOT_IN_PROGRESS", "This run isn't in progress")

    order_ids = [order.id for order in db.list_orders_for_run(run.id)]
    db.set_orders_run(order_ids, run.id, OrderStatus.DELIVERED)
    for order_id in order_ids:
        _record_event(db, order_id, OrderStatus.DELIVERED)

    db.update_run(
        run.model_copy(
            update={"status": RunStatus.COMPLETED, "completed_at": datetime.now(UTC)}
        )
    )
    return Response(status_code=204)


# admin kill switch - unlike a volunteer cancel, orders do NOT return to the pool
@router.post("/{run_id}/remove", status_code=204)
def remove_run(run_id: int, admin: AdminUser, db: QueriesDep) -> Response:
    run = db.get_run(run_id)
    if run is None:
        raise ApiError(404, "RUN_NOT_FOUND", "No run with that id")

    order_ids = [order.id for order in db.list_orders_for_run(run.id)]
    db.set_orders_run(order_ids, run.id, OrderStatus.CANCELLED)
    for order_id in order_ids:
        _record_event(db, order_id, OrderStatus.CANCELLED)

    db.update_run(run.model_copy(update={"status": RunStatus.CANCELLED}))
    return Response(status_code=204)
