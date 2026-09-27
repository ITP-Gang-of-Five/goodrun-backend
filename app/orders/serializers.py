"""
Converts stored orders into their response shape. These live outside of the orders router so that
other domains (e.g. runs, which return their orders in full) can use them without importing another
router's internals.
"""

from app.common.schemas import UserRef
from app.common.users import optional_user_ref, user_ref
from app.orders.schemas import OrderOut
from app.queries import Queries
from app.storage import Order, Run


# returns a dictionary of the fields for a location object
def _location_fields(db: Queries, location_id: int) -> dict[str, object]:
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
Returns the Run an order is on, or None if it isn't assigned to one yet
"""


def order_run(db: Queries, order: Order) -> Run | None:
    return db.get_run(order.run_id) if order.run_id is not None else None


"""
Returns a UserRef for the volunteer assigned to an order or None if the order isn't on
a run yet (and thus isn't assigned to a volunteer)
"""


def _volunteer_ref(db: Queries, order: Order) -> UserRef | None:
    run = order_run(db, order)
    return optional_user_ref(db, run.volunteer_id if run else None)


"""
converts an order from a database entry into a dictionary for use
"""


def order_fields(db: Queries, order: Order) -> dict[str, object]:
    return {
        "order_id": str(order.id),
        "run_id": str(order.run_id) if order.run_id is not None else None,
        "size": order.size,
        "description": order.description,
        "status": order.status,
        "urgency": order.urgency,
        "from_": _location_fields(db, order.from_location_id),
        "to": _location_fields(db, order.to_location_id),
        "from_organisation": optional_user_ref(db, order.from_organisation_id),
        "to_organisation": optional_user_ref(db, order.to_organisation_id),
        "volunteer": _volunteer_ref(db, order),
        "due_at": order.due_at,
        "pickup_notes": order.pickup_notes,
        "dropoff_notes": order.dropoff_notes,
        "created_by": user_ref(db, order.created_by_id),
        "created_at": order.created_at,
    }


"""
Converts a stored order into an OrderOut (an order object for response)
"""


def order_out(db: Queries, order: Order) -> OrderOut:
    return OrderOut(**order_fields(db, order))
