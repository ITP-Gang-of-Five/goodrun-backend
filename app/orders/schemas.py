from datetime import datetime
from typing import Literal

from pydantic import Field

from app.common.schemas import CamelModel, UserRef
from app.locations.schemas import LocationOut
from app.storage import CarSize, OrderStatus, Urgency

"""
General schemas to be used for the api endpoints. Note that these all inherent CamelModel, which is requried
to allow us to convert between snake case (in code) and camel case (for JSON and the databsae)
"""


# Order object as a response to a request (out)
class OrderOut(CamelModel):
    order_id: str
    run_id: str | None
    size: CarSize
    description: str
    status: OrderStatus
    urgency: Urgency
    # NB: needed to use from_ here instead of from, since from is a python keyword
    # this might occur in other cases as well.
    from_: LocationOut = Field(alias="from")
    to: LocationOut
    from_organisation: UserRef | None
    to_organisation: UserRef | None
    volunteer: UserRef | None
    due_at: datetime | None
    pickup_notes: str | None
    dropoff_notes: str | None
    created_by: UserRef
    created_at: datetime


# OrderEvent object as a response to a request (out)
class OrderEventOut(CamelModel):
    event_id: str
    new_status: OrderStatus
    created_at: datetime


# OrderImage object as a response to a request (out)
class OrderImageOut(CamelModel):
    image_id: str
    created_at: datetime


# OrderDetails object as a response to a request (out)
class OrderDetailOut(OrderOut):
    # details involve the events within the order and the images
    events: list[OrderEventOut]
    images: list[OrderImageOut]


# wrapper for any endpoint that returns a list of orders
class OrdersResponse(CamelModel):
    orders: list[OrderOut]
    total: int | None = None


# Order object as a request (in)
class CreateOrderRequest(CamelModel):
    from_location_id: int
    to_location_id: int
    size: CarSize
    description: str
    urgency: Urgency
    from_organisation_id: int | None = None
    to_organisation_id: int | None = None
    due_at: datetime | None = None
    pickup_notes: str | None = None
    dropoff_notes: str | None = None


# response with an OrderID
class OrderIdResponse(CamelModel):
    order_id: str


# reponse for tracking request
class TrackingResponse(CamelModel):
    volunteer: UserRef
    latitude: float
    longitude: float
    updated_at: datetime


# request for uploading an image
class UploadImageRequest(CamelModel):
    content_type: Literal["image/jpeg", "image/png"]
    data: str


# image id response
class ImageIdResponse(CamelModel):
    image_id: str
