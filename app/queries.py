"""
Talking to the Postgres database.
"""

import os
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

import psycopg
from dotenv import load_dotenv
from fastapi import Depends
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from app.storage import (
    CarSize,
    Location,
    Order,
    OrderEvent,
    OrderImage,
    OrderStatus,
    Role,
    Run,
    RunStatus,
    RunStep,
    Urgency,
    User,
    VolunteerLocation,
)

# reads .env to get the url to database
load_dotenv()

# the "" default rather than None keeps this typed as str, which conftest needs
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy your Neon connection string into a .env "
        "file in the project root as DATABASE_URL=postgresql://..."
    )


"""
Opening a connection to Neon costs a round trip + TLS + auth, so we open a
few once and hand the same ones out over and over.
"""
pool: ConnectionPool[psycopg.Connection[DictRow]] = ConnectionPool(
    DATABASE_URL,
    min_size=1,
    max_size=10,
    kwargs={"row_factory": dict_row},
    check=ConnectionPool.check_connection,  # Neon suspends idle connections, so we check before handing one out
    open=False,  # we open later
)


"""
Column lists, one per table, this part from now on is AI generated cuz ceebs. But essentially its required to map
the database rows to the models in storage.py. then all the methods also ai generated, but they are jus SQL statements
"""
_USER_COLUMNS = """
    u.user_id AS id,
    u.name,
    u.email,
    u.password_hash,
    u.role,
    u.created_at,
    vp.car_size
FROM users u
LEFT JOIN volunteer_preferences vp ON vp.volunteer_id = u.user_id
"""

_LOCATION_COLUMNS = """
    location_id AS id, name, latitude, longitude
FROM locations
"""

_RUN_COLUMNS = """
    run_id AS id, volunteer_id, status, created_at, started_at, completed_at
FROM runs
"""

_ORDER_COLUMNS = """
    order_id AS id, run_id, size, description, status, urgency,
    from_location_id, to_location_id, from_organisation_id, to_organisation_id,
    due_at, pickup_notes, dropoff_notes, created_by_id, created_at
FROM orders
"""

_RUN_STEP_COLUMNS = """
    s.run_id, s.order_id, s.type, s.position, s.completed_at
FROM run_steps s
"""

#the location where an order's pickup sits in the route of the run.
_BY_PICKUP_POSITION = """
    (SELECT position FROM run_steps s
     WHERE s.run_id = orders.run_id AND s.order_id = orders.order_id
       AND s.type = 'PICKUP') NULLS LAST, order_id
"""

_ORDER_EVENT_COLUMNS = """
    event_id AS id, order_id, new_status, created_at
FROM order_events
"""

_ORDER_IMAGE_COLUMNS = """
    image_id AS id, order_id, content_type, image_data, created_at
FROM order_images
"""

_VOLUNTEER_LOCATION_COLUMNS = """
    volunteer_id, latitude, longitude, updated_at
FROM volunteer_locations
"""

# a volunteer can take anything up to and including their own car size
_SIZES_UP_TO: dict[CarSize, list[str]] = {
    CarSize.SMALL: [CarSize.SMALL],
    CarSize.MEDIUM: [CarSize.SMALL, CarSize.MEDIUM],
    CarSize.LARGE: [CarSize.SMALL, CarSize.MEDIUM, CarSize.LARGE],
}


class Queries:
    """
    Every SQL statement in the application
    """

    def __init__(self, connection: psycopg.Connection[DictRow]) -> None:
        self._connection = connection

    """
    ---------
    Users
    ---------
    """

    def get_user(self, user_id: int) -> User | None:
        row = self._connection.execute(
            f"SELECT {_USER_COLUMNS} WHERE u.user_id = %s", (user_id,)
        ).fetchone()
        return User(**row) if row else None

    def get_users(self, user_ids: set[int]) -> dict[int, User]:
        # fetch MULTIPLE users
        if not user_ids:
            return {}
        rows = self._connection.execute(
            f"SELECT {_USER_COLUMNS} WHERE u.user_id = ANY(%s)", (list(user_ids),)
        ).fetchall()
        return {row["id"]: User(**row) for row in rows}

    def get_user_by_email(self, email: str) -> User | None:
        # The API agreement says emails are compared ignoring case and surrounding
        # spaces, so both sides get trimmed and lowered
        row = self._connection.execute(
            f"SELECT {_USER_COLUMNS} WHERE lower(u.email) = lower(btrim(%s))", (email,)
        ).fetchone()
        return User(**row) if row else None

    def list_users(self) -> list[User]:
        rows = self._connection.execute(
            f"SELECT {_USER_COLUMNS} ORDER BY u.user_id"
        ).fetchall()
        return [User(**row) for row in rows]

    def list_users_by_role(self, role: Role) -> list[User]:
        # this is what backs GET volunteers/ and GET organisations/
        rows = self._connection.execute(
            f"SELECT {_USER_COLUMNS} WHERE u.role = %s ORDER BY u.user_id", (role,)
        ).fetchall()
        return [User(**row) for row in rows]

    def add_user(self, user: User) -> User:
        # the id on the passed in model is ignored, Postgres assigns the real one.
        # car_size is not here, it lives in its own table, use set_car_size after.
        row = self._connection.execute(
            """
            INSERT INTO users (email, name, password_hash, role, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING user_id
            """,
            (user.email, user.name, user.password_hash, user.role, user.created_at),
        ).fetchone()
        assert row is not None
        return user.model_copy(update={"id": row["user_id"]})

    def update_user(self, user: User) -> None:
        # only touches the users table, car_size is handled by set_car_size
        result = self._connection.execute(
            """
            UPDATE users
            SET email = %s, name = %s, password_hash = %s, role = %s
            WHERE user_id = %s
            """,
            (user.email, user.name, user.password_hash, user.role, user.id),
        )
        if result.rowcount == 0:
            raise KeyError(f"user {user.id} does not exist")

    def set_car_size(self, volunteer_id: int, car_size: CarSize) -> None:
        # a volunteer has at most one preferences row, so setting it twice overwrites
        self._connection.execute(
            """
            INSERT INTO volunteer_preferences (volunteer_id, car_size)
            VALUES (%s, %s)
            ON CONFLICT (volunteer_id) DO UPDATE SET car_size = EXCLUDED.car_size
            """,
            (volunteer_id, car_size),
        )

    def get_volunteer_stats(self, volunteer_id: int) -> dict[str, Any]:
        """
        The stats block on GET volunteers/{userID}. All of it is worked out from the
        volunteer's runs rather than stored anywhere.

        FILTER is the tidy way to count only some of the rows in a group, so the
        completed and cancelled counts come out of a single pass over their runs.
        """
        row = self._connection.execute(
            """
            SELECT
                count(*) FILTER (WHERE status = 'COMPLETED') AS runs_completed,
                count(*) FILTER (WHERE status = 'CANCELLED') AS runs_cancelled,
                max(started_at) AS last_run_at,
                (
                    SELECT count(*)
                    FROM orders o
                    JOIN runs r2 ON r2.run_id = o.run_id
                    WHERE r2.volunteer_id = %(volunteer_id)s AND o.status = 'DELIVERED'
                ) AS orders_delivered
            FROM runs
            WHERE volunteer_id = %(volunteer_id)s
            """,
            {"volunteer_id": volunteer_id},
        ).fetchone()
        assert row is not None
        return dict(row)

    """
    ---------
    Location
    ---------
    """

    def get_location(self, location_id: int) -> Location | None:
        row = self._connection.execute(
            f"SELECT {_LOCATION_COLUMNS} WHERE location_id = %s", (location_id,)
        ).fetchone()
        return Location(**row) if row else None

    def get_locations(self, location_ids: set[int]) -> dict[int, Location]:
        # fetch MULTIPLE locations
        if not location_ids:
            return {}
        rows = self._connection.execute(
            f"SELECT {_LOCATION_COLUMNS} WHERE location_id = ANY(%s)",
            (list(location_ids),),
        ).fetchall()
        return {row["id"]: Location(**row) for row in rows}

    def list_locations(self) -> list[Location]:
        rows = self._connection.execute(
            f"SELECT {_LOCATION_COLUMNS} ORDER BY location_id"
        ).fetchall()
        return [Location(**row) for row in rows]

    def add_location(self, location: Location) -> Location:
        # the id on the passed in model is ignored, Postgres assigns the real one
        row = self._connection.execute(
            """
            INSERT INTO locations (name, latitude, longitude)
            VALUES (%s, %s, %s)
            RETURNING location_id
            """,
            (location.name, location.latitude, location.longitude),
        ).fetchone()
        assert row is not None
        return location.model_copy(update={"id": row["location_id"]})

    """
    ---------
    Runs
    ---------
    """

    def get_run(self, run_id: int) -> Run | None:
        row = self._connection.execute(
            f"SELECT {_RUN_COLUMNS} WHERE run_id = %s", (run_id,)
        ).fetchone()
        return Run(**row) if row else None

    def get_runs(self, run_ids: set[int]) -> dict[int, Run]:
        # fetch MULTIPLE runs
        if not run_ids:
            return {}
        rows = self._connection.execute(
            f"SELECT {_RUN_COLUMNS} WHERE run_id = ANY(%s)", (list(run_ids),)
        ).fetchall()
        return {row["id"]: Run(**row) for row in rows}

    def list_runs(self) -> list[Run]:
        rows = self._connection.execute(
            f"SELECT {_RUN_COLUMNS} ORDER BY run_id"
        ).fetchall()
        return [Run(**row) for row in rows]

    def list_runs_for_volunteer(
        self, volunteer_id: int, status: RunStatus | None = None
    ) -> list[Run]:
        rows = self._connection.execute(
            f"""SELECT {_RUN_COLUMNS}
            WHERE volunteer_id = %(volunteer_id)s
              AND (%(status)s::text IS NULL OR status = %(status)s)
            ORDER BY created_at DESC, run_id DESC""",
            {"volunteer_id": volunteer_id, "status": status},
        ).fetchall()
        return [Run(**row) for row in rows]

    def add_run(self, run: Run) -> Run:
        row = self._connection.execute(
            """
            INSERT INTO runs (volunteer_id, status, created_at, started_at, completed_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING run_id
            """,
            (
                run.volunteer_id,
                run.status,
                run.created_at,
                run.started_at,
                run.completed_at,
            ),
        ).fetchone()
        assert row is not None
        return run.model_copy(update={"id": row["run_id"]})

    def update_run(self, run: Run) -> None:
        result = self._connection.execute(
            """
            UPDATE runs
            SET volunteer_id = %s, status = %s, created_at = %s,
                started_at = %s, completed_at = %s
            WHERE run_id = %s
            """,
            (
                run.volunteer_id,
                run.status,
                run.created_at,
                run.started_at,
                run.completed_at,
                run.id,
            ),
        )
        if result.rowcount == 0:
            raise KeyError(f"run {run.id} does not exist")

    def lock_run(self, run_id: int) -> Run | None:
        """
        get_run, but holds the run until the request finishes, so two requests changing
        the same run (e.g. finishing its last two steps at once) take turns rather than
        each missing what the other did
        """
        row = self._connection.execute(
            f"SELECT {_RUN_COLUMNS} WHERE run_id = %s FOR UPDATE", (run_id,)
        ).fetchone()
        return Run(**row) if row else None

    """
    ---------
    Run steps
    ---------
    """

    def add_run_steps(self, steps: list[RunStep]) -> None:
        with self._connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO run_steps (run_id, order_id, type, position, completed_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        step.run_id,
                        step.order_id,
                        step.type,
                        step.position,
                        step.completed_at,
                    )
                    for step in steps
                ],
            )

    def list_steps_for_runs(self, run_ids: list[int]) -> list[RunStep]:
        """
        The steps of several runs in one query, in route order.

        Only steps for orders still on the run are included. A cancelled run releases
        its orders back into the pool, so like its orders, its steps come back empty.
        """
        if not run_ids:
            return []
        rows = self._connection.execute(
            f"""SELECT {_RUN_STEP_COLUMNS}
            JOIN orders o ON o.order_id = s.order_id AND o.run_id = s.run_id
            WHERE s.run_id = ANY(%s)
            ORDER BY s.run_id, s.position""",
            (run_ids,),
        ).fetchall()
        return [RunStep(**row) for row in rows]

    def list_steps_for_run(self, run_id: int) -> list[RunStep]:
        return self.list_steps_for_runs([run_id])

    def complete_run_step(self, step: RunStep, completed_at: datetime) -> None:
        self._connection.execute(
            """
            UPDATE run_steps SET completed_at = %s
            WHERE run_id = %s AND position = %s
            """,
            (completed_at, step.run_id, step.position),
        )

    """
    ---------
    Orders
    ---------
    """

    def get_order(self, order_id: int) -> Order | None:
        row = self._connection.execute(
            f"SELECT {_ORDER_COLUMNS} WHERE order_id = %s", (order_id,)
        ).fetchone()
        return Order(**row) if row else None

    def list_orders(self) -> list[Order]:
        rows = self._connection.execute(
            f"SELECT {_ORDER_COLUMNS} ORDER BY order_id"
        ).fetchall()
        return [Order(**row) for row in rows]

    def list_orders_for_run(self, run_id: int) -> list[Order]:
        # in the order the volunteer planned to pick them up
        rows = self._connection.execute(
            f"""SELECT {_ORDER_COLUMNS}
            WHERE run_id = %s
            ORDER BY {_BY_PICKUP_POSITION}""",
            (run_id,),
        ).fetchall()
        return [Order(**row) for row in rows]

    def list_orders_for_runs(self, run_ids: list[int]) -> list[Order]:
        # same as list_orders_for_run but does it for multiple runs in a single query
        if not run_ids:
            return []
        rows = self._connection.execute(
            f"""SELECT {_ORDER_COLUMNS}
            WHERE run_id = ANY(%s)
            ORDER BY run_id, {_BY_PICKUP_POSITION}""",
            (run_ids,),
        ).fetchall()
        return [Order(**row) for row in rows]

    def search_orders(
        self,
        *,
        status: OrderStatus | None,
        size: CarSize | None,
        urgency: Urgency | None,
        organisation_id: int | None,
        volunteer_id: int | None,
        unassigned: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Order], int]:
        """
        GET orders/ with all filters done in the database (MUCH faster).

        NB: each filter is skipped when its value is None

        organisationId matches either end of the order (to/from)
        volunteerId matches on any of that volunteer's runs
        """
        where = """
            WHERE (%(status)s::text IS NULL OR status = %(status)s)
              AND (%(size)s::text IS NULL OR size = %(size)s)
              AND (%(urgency)s::text IS NULL OR urgency = %(urgency)s)
              AND (%(organisation_id)s::int IS NULL
                   OR %(organisation_id)s IN (from_organisation_id, to_organisation_id))
              AND (%(volunteer_id)s::int IS NULL OR run_id IN (
                   SELECT run_id FROM runs WHERE volunteer_id = %(volunteer_id)s))
              AND (NOT %(unassigned)s OR run_id IS NULL)
        """
        params = {
            "status": status,
            "size": size,
            "urgency": urgency,
            "organisation_id": organisation_id,
            "volunteer_id": volunteer_id,
            "unassigned": unassigned,
            "limit": limit,
            "offset": offset,
        }
        rows = self._connection.execute(
            f"""SELECT {_ORDER_COLUMNS} {where}
            ORDER BY created_at DESC, order_id DESC
            LIMIT %(limit)s OFFSET %(offset)s""",
            params,
        ).fetchall()
        count = self._connection.execute(
            f"SELECT count(*) AS total FROM orders {where}", params
        ).fetchone()
        assert count is not None
        return [Order(**row) for row in rows], count["total"]

    def list_available_orders(self, car_size: CarSize | None) -> list[Order]:
        """
        The pool a volunteer builds a run from: not on a run, ready for pickup, and
        small enough for their car. Most urgent first, then oldest first within the
        same urgency, which is the order the agreement asks for.

        A volunteer with no car size set is offered nothing, since we cannot tell
        what they can carry.
        """
        if car_size is None:
            return []
        fits = _SIZES_UP_TO[car_size]
        rows = self._connection.execute(
            f"""SELECT {_ORDER_COLUMNS}
            WHERE run_id IS NULL
              AND status = 'READY_FOR_PICKUP'
              AND size = ANY(%s)
            ORDER BY CASE urgency WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END,
                     created_at, order_id""",
            (fits,),
        ).fetchall()
        return [Order(**row) for row in rows]

    def lock_orders_for_run(self, order_ids: list[int]) -> list[Order]:
        """
        Claims orders for a run
        """
        rows = self._connection.execute(
            f"""SELECT {_ORDER_COLUMNS}
            WHERE order_id = ANY(%s)
              AND run_id IS NULL
              AND status = 'READY_FOR_PICKUP'
            FOR UPDATE""",
            (order_ids,),
        ).fetchall()
        return [Order(**row) for row in rows]

    def set_orders_run(
        self, order_ids: list[int], run_id: int | None, status: OrderStatus
    ) -> None:
        # moves a whole run's worth of orders at once. run_id None puts them back in
        # the available pool, which is what a volunteer cancelling a run does.
        self._connection.execute(
            "UPDATE orders SET run_id = %s, status = %s WHERE order_id = ANY(%s)",
            (run_id, status, order_ids),
        )

    def add_order(self, order: Order) -> Order:
        row = self._connection.execute(
            """
            INSERT INTO orders (
                run_id, size, description, status, urgency,
                from_location_id, to_location_id,
                from_organisation_id, to_organisation_id,
                due_at, pickup_notes, dropoff_notes,
                created_by_id, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING order_id
            """,
            (
                order.run_id,
                order.size,
                order.description,
                order.status,
                order.urgency,
                order.from_location_id,
                order.to_location_id,
                order.from_organisation_id,
                order.to_organisation_id,
                order.due_at,
                order.pickup_notes,
                order.dropoff_notes,
                order.created_by_id,
                order.created_at,
            ),
        ).fetchone()
        assert row is not None
        return order.model_copy(update={"id": row["order_id"]})

    def update_order(self, order: Order) -> None:
        result = self._connection.execute(
            """
            UPDATE orders
            SET run_id = %s, size = %s, description = %s, status = %s, urgency = %s,
                from_location_id = %s, to_location_id = %s,
                from_organisation_id = %s, to_organisation_id = %s,
                due_at = %s, pickup_notes = %s, dropoff_notes = %s,
                created_by_id = %s, created_at = %s
            WHERE order_id = %s
            """,
            (
                order.run_id,
                order.size,
                order.description,
                order.status,
                order.urgency,
                order.from_location_id,
                order.to_location_id,
                order.from_organisation_id,
                order.to_organisation_id,
                order.due_at,
                order.pickup_notes,
                order.dropoff_notes,
                order.created_by_id,
                order.created_at,
                order.id,
            ),
        )
        if result.rowcount == 0:
            raise KeyError(f"order {order.id} does not exist")

    """
    ---------
    Order Events
    ---------
    """

    def list_order_events(self, order_id: int) -> list[OrderEvent]:
        # oldest first, this is the delivery timeline the frontend shows
        rows = self._connection.execute(
            f"SELECT {_ORDER_EVENT_COLUMNS} "
            "WHERE order_id = %s ORDER BY created_at, event_id",
            (order_id,),
        ).fetchall()
        return [OrderEvent(**row) for row in rows]

    def add_order_event(self, event: OrderEvent) -> OrderEvent:
        row = self._connection.execute(
            """
            INSERT INTO order_events (order_id, new_status, created_at)
            VALUES (%s, %s, %s)
            RETURNING event_id
            """,
            (event.order_id, event.new_status, event.created_at),
        ).fetchone()
        assert row is not None
        return event.model_copy(update={"id": row["event_id"]})

    """
    ---------
    Order Images
    ---------
    """

    def get_order_image(self, image_id: int) -> OrderImage | None:
        row = self._connection.execute(
            f"SELECT {_ORDER_IMAGE_COLUMNS} WHERE image_id = %s", (image_id,)
        ).fetchone()
        return OrderImage(**row) if row else None

    def list_order_images(self, order_id: int) -> list[OrderImage]:
        rows = self._connection.execute(
            f"SELECT {_ORDER_IMAGE_COLUMNS} WHERE order_id = %s ORDER BY image_id",
            (order_id,),
        ).fetchall()
        return [OrderImage(**row) for row in rows]

    def add_order_image(self, image: OrderImage) -> OrderImage:
        row = self._connection.execute(
            """
            INSERT INTO order_images (order_id, content_type, image_data, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING image_id
            """,
            (image.order_id, image.content_type, image.image_data, image.created_at),
        ).fetchone()
        assert row is not None
        return image.model_copy(update={"id": row["image_id"]})

    """
    ---------
    Volunteer Locations
    ---------
    """

    def get_volunteer_location(self, volunteer_id: int) -> VolunteerLocation | None:
        row = self._connection.execute(
            f"SELECT {_VOLUNTEER_LOCATION_COLUMNS} WHERE volunteer_id = %s",
            (volunteer_id,),
        ).fetchone()
        return VolunteerLocation(**row) if row else None

    def upsert_volunteer_location(self, location: VolunteerLocation) -> None:
        # one row per volunteer, so a later ping overwrites the earlier one
        self._connection.execute(
            """
            INSERT INTO volunteer_locations (volunteer_id, latitude, longitude, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (volunteer_id) DO UPDATE
            SET latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                updated_at = EXCLUDED.updated_at
            """,
            (
                location.volunteer_id,
                location.latitude,
                location.longitude,
                location.updated_at,
            ),
        )


def get_queries() -> Iterator[Queries]:
    """
    Borrows one connection from the pool for one request.
    """
    with pool.connection() as connection:
        yield Queries(connection)


# FastAPI knows to call get_queries() for every request and hand the result to the endpoint function
QueriesDep = Annotated[Queries, Depends(get_queries)]
