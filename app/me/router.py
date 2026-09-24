from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.errors import ApiError
from app.me.schemas import ProfileOut, UpdateProfileRequest
from app.queries import QueriesDep
from app.storage import Role

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/")
def get_my_profile(actor: CurrentUser) -> ProfileOut:
    # return a ProfileOut object of the profile
    return ProfileOut(
        user_id=str(actor.id),
        name=actor.name,
        email=actor.email,
        role=actor.role,
        car_size=actor.car_size,
        created_at=actor.created_at,
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
        exclude_unset=True
    )
    # copy the actor and update it with these changed fields
    updated = actor.model_copy(update=changes)
    # update the user in the database
    queries.update_user(updated)

    # car_size is not a column on users any more, it lives in volunteer_preferences,
    # so update_user above does not touch it and it needs its own write
    if changes.get("car_size") is not None:
        queries.set_car_size(actor.id, changes["car_size"])
