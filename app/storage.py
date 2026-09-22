import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

DB_FILE = Path(__file__).parent / "db.json"

"""
I'm not sure how much of this is going to be needed once we've got the database setup. I've tried to make it
as adaptable as possible in case. But if not I'm happy to scrap all this code. It defines all the enums and models
corresponding to our tables from the data model, then has its own database interface for our code to interact with. 

"""


"""
-----------------------------------------------------------------------------------------------------------------------
Below are all of the ENUMs based on the data model, including things like statuses, user roles, etc
"""
class Role(StrEnum):
    ADMIN = "ADMIN"
    VOLUNTEER = "VOLUNTEER"
    ORGANISATION = "ORGANISATION"


class CarSize(StrEnum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


class Urgency(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RunStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


"""
-----------------------------------------------------------------------------------------------------------------------
Bellow are Models corresponding to each table in the data model. We would (I presume) re-use these once we have our
implementation with the real database, but for now they are good for enforcing rules on types and structure in our
JSON version
"""


class User(BaseModel):
    id: int
    name: str
    email: str
    password: (
        str  # storing in plain text for now, will change when we do the actual databse
    )
    role: Role
    car_size: CarSize | None = None
    created_at: datetime


class Location(BaseModel):
    id: int
    name: str
    #TODO: I've made this optional based on the data model, but the data model might need to change cause this seems peculiar
    address: str | None = None
    latitude: float
    longitude: float


class Run(BaseModel):
    id: int
    status: RunStatus
    volunteer_id: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Order(BaseModel):
    id: int
    run_id: int | None = None
    size: CarSize
    description: str
    status: OrderStatus
    urgency: Urgency
    from_location_id: int
    to_location_id: int
    from_organisation_id: int | None = None
    to_organisation_id: int | None = None
    due_at: datetime | None = None
    pickup_notes: str | None = None
    dropoff_notes: str | None = None
    created_by_id: int
    created_at: datetime


class OrderEvent(BaseModel):
    id: int
    order_id: int
    new_status: OrderStatus
    created_at: datetime


class OrderImage(BaseModel):
    id: int
    order_id: int
    content_type: str
    data_base64: str
    created_at: datetime


#NB: latest known positiion of a volunteer (where each volunteer gets a single row in the table for this)
class VolunteerLocation(BaseModel):
    volunteer_id: int
    latitude: float
    longitude: float
    updated_at: datetime


"""
-----------------------------------------------------------------------------------------------------------------------

Database class. This contains the entire fake JSON database, with one function per table.

I presume that this is how we will interact with the database, but Maxim is the expert on that, so, like I said, if 
it ends up being different we can scrap this code idc.

Note that all of these functions are almost identical, they are just working on different objects and different
'tables' within the 'database'. They are all very elemetnray, get, put, update
"""

class Database:
    def _read(self) -> dict[str, Any]:
        return json.loads(DB_FILE.read_text())

    def _write(self, data: dict[str, Any]) -> None:
        DB_FILE.write_text(json.dumps(data, indent=2))

    #helper to grab the next id for a table (I think this dumbly simulates what real databases do)
    def _next_id(self, rows: list[dict[str, Any]]) -> int:
        return max((row["id"] for row in rows), default=0) + 1


    """
    ---------
    Users
    ---------
    """
    def get_user(self, user_id: int) -> User | None:
        #Return the full User row based on user id
        for user in self.list_users():
            if user.id == user_id:
                return user
        return None

    def get_user_by_email(self, email: str) -> User | None:
        #same as above but with email
        for user in self.list_users():
            if user.email == email:
                return user
        return None

    def list_users(self) -> list[User]:
        #returns a list of User objects constructed from the users portion of the JSON database
        return [User(**row) for row in self._read()["users"]]


    """
    ---------
    Location
    ---------
    """
    def get_location(self, location_id: int) -> Location | None:
        #return Location object from id
        for location in self.list_locations():
            if location.id == location_id:
                return location
        return None

    def list_locations(self) -> list[Location]:
        #return list of Location objects, constructed from location portion of the JSON db (same as w users)
        return [Location(**row) for row in self._read()["locations"]]

    def add_location(self, location: Location) -> Location:
        data = self._read()
        #take the parsed in location and update its id
        stored = location.model_copy(update={"id": self._next_id(data["locations"])})
        #append a JSON conversion of the location object
        data["locations"].append(json.loads(stored.model_dump_json()))
        self._write(data)
        return stored

    """
    ---------
    Runs
    ---------
    """

    def get_run(self, run_id: int) -> Run | None:
        #same as all else get run object by id
        for run in self.list_runs():
            if run.id == run_id:
                return run
        return None

    def list_runs(self) -> list[Run]:
        return [Run(**row) for row in self._read()["runs"]]

    def add_run(self, run: Run) -> Run:
        data = self._read()
        #overwrite with the next id and save to db by converting the Run object into json
        stored = run.model_copy(update={"id": self._next_id(data["runs"])})
        data["runs"].append(json.loads(stored.model_dump_json()))
        self._write(data)
        return stored

    def update_run(self, run: Run) -> None:
        data = self._read()
        for index, row in enumerate(data["runs"]):
            if row["id"] == run.id:
                #write to json
                data["runs"][index] = json.loads(run.model_dump_json())
                self._write(data)
                return
        raise KeyError(f"run {run.id} does not exist")

    """
    ---------
    Orders
    ---------
    """

    def get_order(self, order_id: int) -> Order | None:
        #same as all others
        for order in self.list_orders():
            if order.id == order_id:
                return order
        return None

    def list_orders(self) -> list[Order]:
        return [Order(**row) for row in self._read()["orders"]]

    def add_order(self, order: Order) -> Order:
        data = self._read()
        stored = order.model_copy(update={"id": self._next_id(data["orders"])})
        data["orders"].append(json.loads(stored.model_dump_json()))
        self._write(data)
        return stored

    def update_order(self, order: Order) -> None:
        data = self._read()
        for index, row in enumerate(data["orders"]):
            if row["id"] == order.id:
                data["orders"][index] = json.loads(order.model_dump_json())
                self._write(data)
                return
        raise KeyError(f"order {order.id} does not exist")

    """
    ---------
    Order Events
    ---------
    """

    def list_order_events(self, order_id: int) -> list[OrderEvent]:
        events = [
            OrderEvent(**row)
            for row in self._read()["order_events"]
            if row["order_id"] == order_id
        ]
        #sort by the oldest event first
        return sorted(events, key=lambda event: event.created_at)

    def add_order_event(self, event: OrderEvent) -> OrderEvent:
        data = self._read()
        stored = event.model_copy(update={"id": self._next_id(data["order_events"])})
        data["order_events"].append(json.loads(stored.model_dump_json()))
        self._write(data)
        return stored

    """
    ---------
    Order Images
    ---------
    """

    def get_order_image(self, image_id: int) -> OrderImage | None:
        for row in self._read()["order_images"]:
            if row["id"] == image_id:
                return OrderImage(**row)
        return None

    def list_order_images(self, order_id: int) -> list[OrderImage]:
        return [
            OrderImage(**row)
            for row in self._read()["order_images"]
            if row["order_id"] == order_id
        ]

    def add_order_image(self, image: OrderImage) -> OrderImage:
        data = self._read()
        stored = image.model_copy(update={"id": self._next_id(data["order_images"])})
        data["order_images"].append(json.loads(stored.model_dump_json()))
        self._write(data)
        return stored

    """
    ---------
    Volunteer Locations
    ---------
    """

    def get_volunteer_location(self, volunteer_id: int) -> VolunteerLocation | None:
        for row in self._read()["volunteer_locations"]:
            if row["volunteer_id"] == volunteer_id:
                return VolunteerLocation(**row)
        return None

    def upsert_volunteer_location(self, location: VolunteerLocation) -> None:
        #update or insert. if the location exists just ovewrite it
        data = self._read()
        rows = [
            row
            for row in data["volunteer_locations"]
            if row["volunteer_id"] != location.volunteer_id
        ]
        rows.append(json.loads(location.model_dump_json()))
        data["volunteer_locations"] = rows
        self._write(data)


def get_database() -> Database:
    return Database()
