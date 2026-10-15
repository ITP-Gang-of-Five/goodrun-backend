"""
Models for each table in the data model.

These are the shapes the rest of the application works with. app/queries.py builds
them from Postgres rows and takes them apart again on the way back in.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

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


class RunStepType(StrEnum):
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


"""
-----------------------------------------------------------------------------------------------------------------------
Below are the models corresponding to each table in the data model. One model per
table, with the same fields, so a row maps straight onto one of these.
"""


class User(BaseModel):
    id: int
    name: str
    email: str
    # an Argon2 hash of the password (see app/auth/passwords.py), never the password itself
    password_hash: str
    role: Role
    # lives in the volunteer_preferences table, so it is None for admins and orgs
    car_size: CarSize | None = None
    created_at: datetime


class Location(BaseModel):
    id: int
    name: str
    # TODO: I've made this optional based on the data model, but the data model might need to change cause this seems peculiar
    address: str | None = None
    latitude: float
    longitude: float


class Run(BaseModel):
    id: int
    status: RunStatus
    # a run only exists because a volunteer made it, so this is never null
    volunteer_id: int
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


#A single stop on a runs route (either picking up or dropping off one of its orders)
class RunStep(BaseModel):
    run_id: int
    order_id: int
    type: RunStepType
    #the index of this step in the route
    position: int
    completed_at: datetime | None = None


class OrderEvent(BaseModel):
    id: int
    order_id: int
    new_status: OrderStatus
    created_at: datetime


class OrderImage(BaseModel):
    id: int
    order_id: int
    content_type: str
    # raw bytes, not base64. The upload endpoint decodes once on the way in so the
    # download endpoint can serve them straight back out.
    image_data: bytes
    created_at: datetime


# NB: latest known positiion of a volunteer (where each volunteer gets a single row in the table for this)
class VolunteerLocation(BaseModel):
    volunteer_id: int
    latitude: float
    longitude: float
    updated_at: datetime
