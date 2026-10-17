from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import CurrentUser, SignedInUser
from app.auth.passwords import hash_password
from app.errors import ApiError
from app.me.schemas import OnboardingRequest, ProfileOut, UpdateProfileRequest
from app.queries import QueriesDep
from app.storage import Role

router = APIRouter(prefix="/me", tags=["me"])


# NB: this also works for someone who hasn't completed onboarding
@router.get("/")
def get_my_profile(actor: SignedInUser) -> ProfileOut:
    # return a ProfileOut object of the profile
    return ProfileOut(
        user_id=str(actor.id),
        name=actor.name,
        email=actor.email,
        role=actor.role,
        car_size=actor.car_size,
        created_at=actor.created_at,
        onboarded=actor.onboarded_at is not None,
    )


@router.patch("/", status_code=204)
def update_my_profile(
    body: UpdateProfileRequest, actor: CurrentUser, queries: QueriesDep
) -> None:
    # you can't change car_size for non-volunteers because they dont have that
    if "car_size" in body.model_fields_set and actor.role != Role.VOLUNTEER:
        raise ApiError(403, "FORBIDDEN", "Only volunteers can set a car size")

    # model_dump converts the UpdateProfileRequest into a dict
    changes = body.model_dump(
        # excludes any fields that weren't in the response body
        exclude_unset=True,
        # and any sent as null, so e.g. {"name": null} can't blank out someone's name
        exclude_none=True,
    )
    # copy the actor and update it with these changed fields
    updated = actor.model_copy(update=changes)
    # update the user in the database
    queries.update_user(updated)

    # car_size is not a column on users any more, it lives in volunteer_preferences,
    # so update_user above does not touch it and it needs its own write
    if changes.get("car_size") is not None:
        queries.set_car_size(actor.id, changes["car_size"])


# The endpoint to trigger for someone who has logged in but hasn't completed onboarding. Until onboarding
# is completed every endpoint will refuse them with 403 NOT_ONBOARDED
@router.post("/onboarding", status_code=204)
def onboard(body: OnboardingRequest, actor: SignedInUser, queries: QueriesDep) -> None:
    if actor.onboarded_at is not None:
        raise ApiError(409, "ALREADY_ONBOARDED", "Your account is already set up")

    # only volunteer's have a car size
    if actor.role == Role.VOLUNTEER and body.car_size is None:
        raise ApiError(422, "VALIDATION_ERROR", "carSize: volunteers must choose one")
    if actor.role != Role.VOLUNTEER and body.car_size is not None:
        raise ApiError(403, "FORBIDDEN", "Only volunteers can set a car size")

    queries.update_user(
        actor.model_copy(
            update={
                "name": body.name,
                "password_hash": hash_password(body.password),
                "onboarded_at": datetime.now(UTC),
            }
        )
    )
    if body.car_size is not None:
        queries.set_car_size(actor.id, body.car_size)
