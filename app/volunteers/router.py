from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import AdminUser
from app.errors import ApiError
from app.queries import Queries, QueriesDep
from app.storage import Role, User
from app.volunteers.schemas import CreateVolunteerRequest, VolunteerOut, VolunteersOut

router = APIRouter(prefix="/volunteers", tags=["volunteers"])


def _volunteer_out(user: User) -> VolunteerOut:
    return VolunteerOut(
        volunteer_id=str(user.id),
        name=user.name,
        email=user.email,
        car_size=user.car_size,
        created_at=user.created_at,
    )


# fetches a user by id, but only if they're actually a volunteer
def _require_volunteer(db: Queries, volunteer_id: int) -> User:
    user = db.get_user(volunteer_id)
    if user is None or user.role != Role.VOLUNTEER:
        raise ApiError(404, "VOLUNTEER_NOT_FOUND", "No volunteer with that id")
    return user


# fetch every volunteer account
@router.get("/")
def list_volunteers(admin: AdminUser, db: QueriesDep) -> VolunteersOut:
    return VolunteersOut(
        # literally just get all of the users that are volunteers
        volunteers=[
            _volunteer_out(user) for user in db.list_users_by_role(Role.VOLUNTEER)
        ]
    )


# fetch a single volunteer's profile
@router.get("/{volunteer_id}")
def get_volunteer(volunteer_id: int, admin: AdminUser, db: QueriesDep) -> VolunteerOut:
    return _volunteer_out(_require_volunteer(db, volunteer_id))


# register a new volunteer account
@router.post("/", status_code=201)
def create_volunteer(
    body: CreateVolunteerRequest, admin: AdminUser, db: QueriesDep
) -> VolunteerOut:
    if db.get_user_by_email(body.email) is not None:
        raise ApiError(409, "EMAIL_TAKEN", "A user with that email already exists")

    user = db.add_user(
        User(
            id=0,
            name=body.name,
            email=body.email,
            password_hash=body.password,
            role=Role.VOLUNTEER,
            created_at=datetime.now(UTC),
        )
    )
    # car_size lives in volunteer_preferences, so it's saved separately from the user
    if body.car_size is not None:
        db.set_car_size(user.id, body.car_size)
        user = user.model_copy(update={"car_size": body.car_size})
    return _volunteer_out(user)
