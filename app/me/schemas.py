from datetime import datetime

from app.common.schemas import CamelModel
from app.storage import CarSize, Role


# the calling user's own profile to be sent out on response
class ProfileOut(CamelModel):
    user_id: str
    name: str
    email: str
    role: Role
    car_size: CarSize | None
    created_at: datetime


# input request for updating a user's own profile (so the id is already known, since they are making the request)
class UpdateProfileRequest(CamelModel):
    name: str | None = None
    car_size: CarSize | None = None
