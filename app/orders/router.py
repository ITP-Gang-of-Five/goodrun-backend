import base64
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import AdminOrOrganisationUser, AdminUser, CurrentUser, VolunteerUser
from app.common.schemas import UserRef
from app.errors import ApiError
from app.orders.schemas import (
    CreateOrderRequest,
    ImageIdResponse,
    OrderDetailOut,
    OrderEventOut,
    OrderIdResponse,
    OrderImageOut,
    OrderOut,
    OrdersResponse,
    TrackingResponse,
    UploadImageRequest,
)
from app.storage import (
    CarSize,
    Database,
    Order,
    OrderEvent,
    OrderImage,
    OrderStatus,
    Role,
    Run,
    RunStatus,
    Urgency,
    User,
    get_database,
)

router = APIRouter(prefix="/orders", tags=["orders"])

# hashmap for urgency enum to an integer
_URGENCY_RANK = {Urgency.LOW: 0, Urgency.MEDIUM: 1, Urgency.HIGH: 2}
# list of available car sizes from the enum CarSize
_SIZE_ORDER = list(CarSize)
# max size of an image. NB: this is just here for now, we haven't fully tested images so this is really
# just a presumption.
_MAX_IMAGE_BYTES = 8 * 1024 * 1024


"""
------------------------------------------------------------------------------------------
HELPER FUNCTIONS
------------------------------------------------------------------------------------------
"""


"""
Determines if an order size fits into a parsed car size. A volunteer is able to take
orders up to and including their selected car size
"""


def _fits(car_size: CarSize | None, order_size: CarSize) -> bool:
    return car_size is not None and _SIZE_ORDER.index(order_size) <= _SIZE_ORDER.index(
        car_size
    )


# returns a dictionary of the fields for a location object
def _location_fields(db: Database, location_id: int) -> dict[str, object]:
    location = db.get_location(location_id)
    # orders only ever store location ids that were validated to exist at creation time
    assert location is not None
    return {
        "location_id": str(location.id),
        "name": location.name,
        "latitude": location.latitude,
        "longitude": location.longitude,
    }


"""
Returns a UserRef for a user based on their id
"""


def _user_ref(db: Database, user_id: int) -> UserRef:
    user = db.get_user(user_id)
    return UserRef(user_id=str(user_id), name=user.name if user else "Unknown")


"""
Returns a UserRef or none if userId is none. just a helpful wrapper
"""


def _optional_user_ref(db: Database, user_id: int | None) -> UserRef | None:
    return None if user_id is None else _user_ref(db, user_id)


"""
Returns the Run an order is on, or None if it isn't assigned to one yet
"""


def _order_run(db: Database, order: Order) -> Run | None:
    return db.get_run(order.run_id) if order.run_id is not None else None


"""
Returns a UserRef for the volunteer assigned to an order or None if the order isn't on
a run yet (and thus isn't assigned to a volunteer)
"""


def _volunteer_ref(db: Database, order: Order) -> UserRef | None:
    run = _order_run(db, order)
    return _optional_user_ref(db, run.volunteer_id if run else None)


"""
converts an order from a database entry into a dictionary for use
"""


def _order_fields(db: Database, order: Order) -> dict[str, object]:
    return {
        "order_id": str(order.id),
        "run_id": str(order.run_id) if order.run_id is not None else None,
        "size": order.size,
        "description": order.description,
        "status": order.status,
        "urgency": order.urgency,
        "from_": _location_fields(db, order.from_location_id),
        "to": _location_fields(db, order.to_location_id),
        "from_organisation": _optional_user_ref(db, order.from_organisation_id),
        "to_organisation": _optional_user_ref(db, order.to_organisation_id),
        "volunteer": _volunteer_ref(db, order),
        "due_at": order.due_at,
        "pickup_notes": order.pickup_notes,
        "dropoff_notes": order.dropoff_notes,
        "created_by": _user_ref(db, order.created_by_id),
        "created_at": order.created_at,
    }


"""
Converts a Database order into an OrderOut (an order object for response)
"""


def _order_out(db: Database, order: Order) -> OrderOut:
    return OrderOut(**_order_fields(db, order))


"""
A helper function for who is allowed to view this order. If its any admin they are allowed to.
If its an organisation, they can only view it if they are the 'to' or 'from' organisation
"""


def _can_view(db: Database, actor: User, order: Order) -> bool:
    if actor.role == Role.ADMIN:
        return True
    if actor.role == Role.ORGANISATION:
        return actor.id in (order.from_organisation_id, order.to_organisation_id)
    run = _order_run(db, order)
    return run is not None and run.volunteer_id == actor.id


"""
Fetches an order from the database (based on order id) and returns it only if
the user is able to view it.
"""


def _require_order(db: Database, actor: User, order_id: int) -> Order:
    order = db.get_order(order_id)
    # Not found rather than forbidden, so orders can't be probed for existence.
    if order is None or not _can_view(db, actor, order):
        raise ApiError(404, "ORDER_NOT_FOUND", "No order with that id")
    return order


"""
Takes in an Order object and a status and adds an event to the database for this status change
"""


def _record_event(db: Database, order: Order, status: OrderStatus) -> None:
    db.add_order_event(
        OrderEvent(
            id=0, order_id=order.id, new_status=status, created_at=datetime.now(UTC)
        )
    )


"""
------------------------------------------------------------------------------------------
API ENDPOINTS
------------------------------------------------------------------------------------------
"""


"""
Returns an OrdersResponse for the current Volunteer containing the list of available orders, meaning:
- the order is ready for pickup
- the order fits in the volunteers vehcile
"""


@router.get("/available")
def get_available_orders(volunteer: VolunteerUser) -> OrdersResponse:
    db = get_database()

    # retrieve all orders with the ready for pickup status
    ready_orders = [
        order
        for order in db.list_orders()
        if order.status == OrderStatus.READY_FOR_PICKUP and order.run_id is None
    ]
    # filter the orders based on if they fit in the volunteer's car AND sort by urgency
    fitting = sorted(
        (order for order in ready_orders if _fits(volunteer.car_size, order.size)),
        key=lambda order: (-_URGENCY_RANK[order.urgency], order.created_at, order.id),
    )
    # convert all of the orders into OrderOut objects
    orders_out = [_order_out(db, order) for order in fitting]
    return OrdersResponse(orders=orders_out)


"""
Returns an OrdersResponse containing all orders filteted on the parsed params. This endpoints works only for Admins or Organisations.
For Organisations it will only return the orders they are assigned to in some regard
"""


@router.get("/")
def get_orders(
    actor: AdminOrOrganisationUser,
    status: OrderStatus | None = None,
    size: CarSize | None = None,
    urgency: Urgency | None = None,
    organisation_id: Annotated[int | None, Query(alias="organisationId")] = None,
    volunteer_id: Annotated[int | None, Query(alias="volunteerId")] = None,
    unassigned: bool = False,
    # api limits
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    # offset for pagination
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OrdersResponse:
    db = get_database()

    # set organisation_id to this actor.
    if actor.role == Role.ORGANISATION:
        organisation_id = actor.id
        # remove the id of the volunteer (as per the API spec)
        volunteer_id = None
        # don't let the org see the assigned status (as per the API spec)
        unassigned = False

    # If a volunteer_id is set grab all runs where the volunteer is assigned to it
    volunteer_run_ids: set[int] = set()
    if volunteer_id is not None:
        volunteer_run_ids = {
            run.id for run in db.list_runs() if run.volunteer_id == volunteer_id
        }

    # filter all of the orders based on the parsed params
    matching = sorted(
        (
            order
            for order in db.list_orders()
            # filter on status if set
            if (status is None or order.status == status)
            # filter on size if set
            and (size is None or order.size == size)
            # etc
            and (urgency is None or order.urgency == urgency)
            # match on an organisation_id if set to match on either the 'from' or 'to' org
            and (
                organisation_id is None
                or organisation_id
                in (order.from_organisation_id, order.to_organisation_id)
            )
            # match only on the orders that exist in a run where the volunteer with volunteer_id is assigned to that run
            and (volunteer_id is None or order.run_id in volunteer_run_ids)
            # return only unassigned (if flag set)
            and (not unassigned or order.run_id is None)
        ),
        key=lambda order: (order.created_at, order.id),
        # return newest first
        reverse=True,
    )
    # set the page based on our defined offset and limit, allowing for pagination
    page = matching[offset : offset + limit]
    return OrdersResponse(
        orders=[_order_out(db, order) for order in page], total=len(matching)
    )


"""
Endpoint to create a run
"""


@router.post("/", status_code=201)
def create_order(body: CreateOrderRequest, admin: AdminUser) -> OrderIdResponse:
    db = get_database()

    # Step 1: extract all the locations that are set for the order. raise error if those locations aren't found
    for location_id in (body.from_location_id, body.to_location_id):
        if db.get_location(location_id) is None:
            raise ApiError(404, "LOCATION_NOT_FOUND", f"no location witj {location_id}")

    # Setp 2: for the 'to' and 'from' orgs, existance check them
    for organisation_id in (body.from_organisation_id, body.to_organisation_id):
        if organisation_id is None:
            continue
        organisation = db.get_user(organisation_id)
        # we must check that these user ids (which we presume to be orgs) actually correspond to the org role
        # this is because we use a universal user table and id system
        if organisation is None or organisation.role != Role.ORGANISATION:
            raise ApiError(
                404,
                "ORGANISATION_NOT_FOUND",
                f"no org with id {organisation_id}",
            )

    # add the order to the database
    order = db.add_order(
        Order(
            id=0,
            size=body.size,
            description=body.description,
            status=OrderStatus.READY_FOR_PICKUP,
            urgency=body.urgency,
            from_location_id=body.from_location_id,
            to_location_id=body.to_location_id,
            from_organisation_id=body.from_organisation_id,
            to_organisation_id=body.to_organisation_id,
            due_at=body.due_at,
            pickup_notes=body.pickup_notes,
            dropoff_notes=body.dropoff_notes,
            created_by_id=admin.id,
            created_at=datetime.now(UTC),
        )
    )
    # record the initalisation event of the order, where it becomes ready for pickup
    _record_event(db, order, OrderStatus.READY_FOR_PICKUP)
    # construct an orderIdResponse object for the order. NB: for now its jsut
    # an id, but in future ew can expand it
    return OrderIdResponse(order_id=str(order.id))


"""
Get a single order based on its id
"""


@router.get("/{order_id}")
def get_order(order_id: int, actor: CurrentUser) -> OrderDetailOut:
    db = get_database()
    # NB: _require_order will raise an API error if the order doesn't exist
    order = _require_order(db, actor, order_id)

    # construct the list of OrderEvents for this. each order has 0 to many status changes (even outs)
    events = []
    for event in db.list_order_events(order.id):
        events.append(
            OrderEventOut(
                event_id=str(event.id),
                new_status=event.new_status,
                created_at=event.created_at,
            )
        )

    # construct the list of images assosciated with the order
    images = []
    for image in db.list_order_images(order.id):
        images.append(
            OrderImageOut(image_id=str(image.id), created_at=image.created_at)
        )

    order_fields = _order_fields(db, order)
    # use these kwards plus the list of events and list of images to consturct the OrderDetailOut (response object)
    return OrderDetailOut(**order_fields, events=events, images=images)


"""
Remove a specified order
"""


@router.post("/{order_id}/remove", status_code=204)
def remove_order(order_id: int, admin: AdminUser) -> Response:
    db = get_database()
    order = _require_order(db, admin, order_id)
    # only an order that is not in a run can be removed
    if order.run_id is not None:
        raise ApiError(
            409,
            "ORDER_NOT_AVAILABLE",
            "Only orders that are not on a run can be removed",
        )
    # update the order with the cancelled status and record the event for it
    db.update_order(order.model_copy(update={"status": OrderStatus.CANCELLED}))
    _record_event(db, order, OrderStatus.CANCELLED)
    return Response(status_code=204)


"""
Get a TrackingResponse for a defined order (admin only)
"""


@router.get("/{order_id}/tracking")
def track_order(order_id: int, actor: AdminOrOrganisationUser) -> TrackingResponse:
    db = get_database()
    # NB: _require_order will raise an API error if the order doesn't exist
    order = _require_order(db, actor, order_id)

    # an order cannot have tracking if its not part of a run
    run = _order_run(db, order)
    # it must also be in progress (an IN_PROGRESS run always has a volunteer assigned)
    if run is None or run.status != RunStatus.IN_PROGRESS or run.volunteer_id is None:
        raise ApiError(409, "RUN_NOT_IN_PROGRESS", "The order's run is not in progress")

    # grab the volunteer location
    position = db.get_volunteer_location(run.volunteer_id)
    if position is None:
        raise ApiError(
            409, "TRACKING_UNAVAILABLE", "No recent location for this volunteer"
        )

    # construct and return a tracking response
    return TrackingResponse(
        volunteer=_user_ref(db, run.volunteer_id),
        latitude=position.latitude,
        longitude=position.longitude,
        updated_at=position.updated_at,
    )


"""
Upload an image for the order
"""


@router.post("/{order_id}/images", status_code=201)
def upload_order_image(
    order_id: int, body: UploadImageRequest, volunteer: VolunteerUser
) -> ImageIdResponse:
    db = get_database()
    order = _require_order(db, volunteer, order_id)

    # image can only be uploaded to an in progress run
    run = _order_run(db, order)
    if run is None or run.status != RunStatus.IN_PROGRESS:
        raise ApiError(
            409,
            "RUN_NOT_IN_PROGRESS",
            "Photos can only be added while the run is in progress",
        )

    # ensure the parsed data is base64
    try:
        raw = base64.b64decode(body.data, validate=True)
    except ValueError as exc:
        raise ApiError(422, "VALIDATION_ERROR", "data is not valid base64") from exc
    if not raw or len(raw) > _MAX_IMAGE_BYTES:
        raise ApiError(422, "VALIDATION_ERROR", "image must be between 1 byte and 8MB")

    # add an order image to the order with the base64 blob of image data
    image = db.add_order_image(
        OrderImage(
            id=0,
            order_id=order.id,
            content_type=body.content_type,
            data_base64=body.data,
            created_at=datetime.now(UTC),
        )
    )
    return ImageIdResponse(image_id=str(image.id))


"""
Get a specific image for an order based on order id and image id
"""


@router.get("/{order_id}/images/{image_id}", response_class=Response)
def get_order_image(order_id: int, image_id: int, actor: CurrentUser) -> Response:
    # NB: this endpoint returns RAW BYTES rather than JSON!!!!
    db = get_database()
    order = _require_order(db, actor, order_id)
    image = db.get_order_image(image_id)
    if image is None or image.order_id != order.id:
        raise ApiError(404, "ORDER_NOT_FOUND", "No image with that id on this order")
    # we must construct our own response for this
    return Response(
        # content is set to the base64 of the image blob and media type is set to an iamge
        content=base64.b64decode(image.data_base64),
        media_type=image.content_type,
    )
