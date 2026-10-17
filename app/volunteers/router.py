from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import AdminUser
from app.auth.invites import send_invite
from app.common.users import require_unused_email
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
        onboarded=user.onboarded_at is not None,
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


# invite a new volunteer. the account is made with just their email, and they're emailed
# a code to log in with, after which they set up the rest themselves (see app/auth/invites.py)
@router.post("/", status_code=201)
def create_volunteer(
    body: CreateVolunteerRequest, admin: AdminUser, db: QueriesDep
) -> VolunteerOut:
    require_unused_email(db, body.email)

    user = db.add_user(
        User(
            id=0,
            email=body.email,
            role=Role.VOLUNTEER,
            created_at=datetime.now(UTC),
        )
    )
    send_invite(db, user)
    return _volunteer_out(user)


# Sends a volunteer a new code if they lost it or it timed out
@router.post("/{volunteer_id}/resend-invite", status_code=204)
def resend_invite(volunteer_id: int, admin: AdminUser, db: QueriesDep) -> None:
    user = _require_volunteer(db, volunteer_id)
    if user.onboarded_at is not None:
        raise ApiError(
            409, "ALREADY_ONBOARDED", "This volunteer has already set up their account"
        )
    send_invite(db, user)
