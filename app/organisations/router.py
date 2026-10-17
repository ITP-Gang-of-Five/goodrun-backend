from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import AdminUser
from app.auth.invites import send_invite
from app.common.users import require_unused_email
from app.errors import ApiError
from app.organisations.schemas import (
    CreateOrganisationRequest,
    OrganisationOut,
    OrganisationsResponse,
)
from app.queries import Queries, QueriesDep
from app.storage import Role, User

router = APIRouter(prefix="/organisations", tags=["organisations"])


def _organisation_out(user: User) -> OrganisationOut:
    return OrganisationOut(
        organisation_id=str(user.id),
        name=user.name,
        email=user.email,
        created_at=user.created_at,
        onboarded=user.onboarded_at is not None,
    )


# fetches a user by id, but only if they're actually an organisation
def _require_organisation(db: Queries, organisation_id: int) -> User:
    user = db.get_user(organisation_id)
    if user is None or user.role != Role.ORGANISATION:
        raise ApiError(404, "ORGANISATION_NOT_FOUND", "No organisation with that id")
    return user


@router.get("/")
def list_organisations(admin: AdminUser, db: QueriesDep) -> OrganisationsResponse:
    # simply return all organisations, admin only of course
    return OrganisationsResponse(
        organisations=[
            _organisation_out(user) for user in db.list_users_by_role(Role.ORGANISATION)
        ]
    )


# fetch a single organisation's profile
# TODO: I might have made a mistake in the API agreement, pretty sure that volunteer's are going to need to be able
# to grab organisations in the future..... we shall return to this later
@router.get("/{organisation_id}")
def get_organisation(
    organisation_id: int, admin: AdminUser, db: QueriesDep
) -> OrganisationOut:
    return _organisation_out(_require_organisation(db, organisation_id))


@router.post("/", status_code=201)
def create_organisation(
    body: CreateOrganisationRequest, admin: AdminUser, db: QueriesDep
) -> OrganisationOut:
    require_unused_email(db, body.email)

    user = db.add_user(
        User(
            id=0,
            email=body.email,
            role=Role.ORGANISATION,
            created_at=datetime.now(UTC),
        )
    )
    send_invite(db, user)
    return _organisation_out(user)


#Sends an organisation a new codeif it was lost or expired
@router.post("/{organisation_id}/resend-invite", status_code=204)
def resend_invite(organisation_id: int, admin: AdminUser, db: QueriesDep) -> None:
    user = _require_organisation(db, organisation_id)
    if user.onboarded_at is not None:
        raise ApiError(
            409,
            "ALREADY_ONBOARDED",
            "This organisation has already set up their account",
        )
    send_invite(db, user)
