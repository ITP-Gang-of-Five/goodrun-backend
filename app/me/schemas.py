from datetime import datetime

from app.common.schemas import CamelModel
from app.common.validation import Name, Password
from app.storage import CarSize, Role


# the calling user's own profile to be sent out on response
class ProfileOut(CamelModel):
    user_id: str
    # None until an invited account is set up
    name: str | None
    email: str
    role: Role
    car_size: CarSize | None
    created_at: datetime
    onboarded: bool


# input request for updating a user's own profile (so the id is already known, since they are making the request)
class UpdateProfileRequest(CamelModel):
    name: Name | None = None
    car_size: CarSize | None = None


# what someone who was invited chooses the first time they log in
class OnboardingRequest(CamelModel):
    name: Name
    password: Password
    car_size: CarSize | None = None
