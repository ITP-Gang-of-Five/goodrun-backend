from datetime import datetime

from app.common.schemas import CamelModel
from app.common.validation import Email
from app.storage import CarSize


# a volunteer's profile as seen by an admin (never includes the password)
class VolunteerOut(CamelModel):
    volunteer_id: str
    name: str | None
    email: str
    car_size: CarSize | None
    created_at: datetime
    onboarded: bool


# every volunteer account, wrapped in an object as per the api agreement
class VolunteersOut(CamelModel):
    volunteers: list[VolunteerOut]


# input for inviting a new volunteer
class CreateVolunteerRequest(CamelModel):
    email: Email
