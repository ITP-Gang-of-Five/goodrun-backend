import json
from datetime import UTC, datetime

from app.storage import (
    DB_FILE,
    CarSize,
    Location,
    Order,
    OrderStatus,
    Role,
    Run,
    RunStatus,
    Urgency,
    get_database,
)


def test_the_admin_exists() -> None:
    admin = get_database().get_user_by_email("admin")
    assert admin is not None
    assert admin.password == "admin"
    assert admin.role == Role.ADMIN
    assert get_database().get_user(admin.id) == admin


def test_unknown_users_are_none() -> None:
    # Ensure that random users that don't exist just return None
    assert get_database().get_user(999) is None
    assert get_database().get_user_by_email("nobody") is None
    assert get_database().get_user_by_email("i am not real") is None


def test_runs_can_be_added_and_updated() -> None:
    # store reference to the original database
    original = _reset_db()
    try:
        run = get_database().add_run(
            Run(
                id=0,
                status=RunStatus.NOT_STARTED,
                created_at=datetime.now(UTC),
            )
        )
        #ensure the run now exists
        assert get_database().get_run(run.id) == run
        #start the run
        started = run.model_copy(update={"status": RunStatus.IN_PROGRESS})
        get_database().update_run(started)
        #ensure ti started
        assert get_database().get_run(run.id) == started
    finally:
        # then restore the original, in case we fail assertions
        _restore_db(original)


def test_locations_are_seeded_and_can_be_added() -> None:
    original = _reset_db()
    try:
        # get all current locations
        seeded = get_database().list_locations()
        # add a new location
        added = get_database().add_location(
            Location(
                id=0,
                name="Test Depot",
                latitude=-37.8,
                longitude=144.9,
            )
        )
        # check that the id didn't already exist, as the id should be bumped to a new one automatically
        assert added.id not in {location.id for location in seeded}
        # check that the location was added
        assert get_database().get_location(added.id) == added
    finally:
        _restore_db(original)


def test_orders_can_be_added_and_updated() -> None:
    original = _reset_db()
    try:
        order = get_database().add_order(
            Order(
                id=0,
                size=CarSize.SMALL,
                description="Test parcel",
                status=OrderStatus.PENDING,
                urgency=Urgency.LOW,
                from_location_id=1,
                to_location_id=2,
                created_by_id=1,
                created_at=datetime.now(UTC),
            )
        )
        #ensure run was made
        assert get_database().get_order(order.id) == order
        #ensure its status can be updated
        updated = order.model_copy(update={"status": OrderStatus.CANCELLED})
        get_database().update_order(updated)
        assert get_database().get_order(order.id) == updated
    finally:
        _restore_db(original)


def _reset_db() -> str:
    return DB_FILE.read_text()


def _restore_db(original: str) -> None:
    DB_FILE.write_text(original)
    json.loads(DB_FILE.read_text())  # sanity check the file is still valid JSON
