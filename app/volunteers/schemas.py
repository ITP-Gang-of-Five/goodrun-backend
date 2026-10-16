from datetime import datetime

from app.common.schemas import CamelModel
from app.common.validation import Email, Name, Password
from app.storage import CarSize


# a volunteer's profile as seen by an admin (never includes the password)
class VolunteerOut(CamelModel):
    volunteer_id: str
    name: str
    email: str
    car_size: CarSize | None
    created_at: datetime


# every volunteer account, wrapped in an object as per the api agreement
class VolunteersOut(CamelModel):
    volunteers: list[VolunteerOut]


# input for registering a new volunteer account
class CreateVolunteerRequest(CamelModel):
    name: Name
    email: Email
    password: Password
    car_size: CarSize | None = None
