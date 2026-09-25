from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import AdminUser
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


# register a new organisation account
@router.post("/", status_code=201)
def create_organisation(
    body: CreateOrganisationRequest, admin: AdminUser, db: QueriesDep
) -> OrganisationOut:
    if db.get_user_by_email(body.email) is not None:
        raise ApiError(409, "EMAIL_TAKEN", "A user with that email already exists")

    user = db.add_user(
        User(
            id=0,
            name=body.name,
            email=body.email,
            password_hash=body.password,
            role=Role.ORGANISATION,
            created_at=datetime.now(UTC),
        )
    )
    return _organisation_out(user)
