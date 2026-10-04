"""
Converts stored orders into their response shape. These live outside of the orders router so that
other domains (e.g. runs, which return their orders in full) can use them without importing another
router's internals.
"""

from app.common.users import user_ref_from
from app.orders.schemas import OrderOut
from app.queries import Queries
from app.storage import Location, Order, Run, User

"""
Returns the Run an order is on, or None if it isn't assigned to one yet
"""


def order_run(db: Queries, order: Order) -> Run | None:
    return db.get_run(order.run_id) if order.run_id is not None else None


# returns a dictionary of the fields for a location object
def _location_fields(
    locations: dict[int, Location], location_id: int
) -> dict[str, object]:
    location = locations.get(location_id)
    # orders only ever store location ids that were validated to exist at creation time
    assert location is not None
    return {
        "location_id": str(location.id),
        "name": location.name,
        "latitude": location.latitude,
        "longitude": location.longitude,
    }


#converts a single order into a dictionary, using locations, runs and users that were already fetched
def _fields(
    order: Order,
    locations: dict[int, Location],
    runs: dict[int, Run],
    users: dict[int, User],
) -> dict[str, object]:
    # the volunteer is whoever is on the order's run, or None if it isn't on a run yet
    run = runs.get(order.run_id) if order.run_id is not None else None
    return {
        "order_id": str(order.id),
        "run_id": str(order.run_id) if order.run_id is not None else None,
        "size": order.size,
        "description": order.description,
        "status": order.status,
        "urgency": order.urgency,
        "from_": _location_fields(locations, order.from_location_id),
        "to": _location_fields(locations, order.to_location_id),
        "from_organisation": user_ref_from(users, order.from_organisation_id),
        "to_organisation": user_ref_from(users, order.to_organisation_id),
        "volunteer": user_ref_from(users, run.volunteer_id if run else None),
        "due_at": order.due_at,
        "pickup_notes": order.pickup_notes,
        "dropoff_notes": order.dropoff_notes,
        "created_by": user_ref_from(users, order.created_by_id),
        "created_at": order.created_at,
    }


"""
converts many orders from database entries into dictionaries, fetching everything they need in bulk
"""
def orders_fields(db: Queries, orders: list[Order]) -> list[dict[str, object]]:
    locations = db.get_locations(
        {order.from_location_id for order in orders}
        | {order.to_location_id for order in orders}
    )
    runs = db.get_runs({order.run_id for order in orders if order.run_id is not None})
    #must grab all of the users that are mentioned by the db
    user_ids = {order.created_by_id for order in orders}
    user_ids |= {
        org_id
        for order in orders
        for org_id in (order.from_organisation_id, order.to_organisation_id)
        if org_id is not None
    }
    user_ids |= {run.volunteer_id for run in runs.values() if run.volunteer_id}
    users = db.get_users(user_ids)
    return [_fields(order, locations, runs, users) for order in orders]


"""
converts an order from a database entry into a dictionary for use
"""
def order_fields(db: Queries, order: Order) -> dict[str, object]:
    return orders_fields(db, [order])[0]


"""
Converts stored orders into OrderOuts (order objects for response). Used for lists
"""
def orders_out(db: Queries, orders: list[Order]) -> list[OrderOut]:
    return [OrderOut(**fields) for fields in orders_fields(db, orders)]


"""
Converts a stored order into an OrderOut (an order object for response)
"""
def order_out(db: Queries, order: Order) -> OrderOut:
    return orders_out(db, [order])[0]
