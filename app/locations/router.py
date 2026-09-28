from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminUser
from app.locations import locations
from app.locations.schemas import (
    CreateLocationRequest,
    LocationIdResponse,
    LocationOut,
    LocationsResponse,
    LocationSuggestionsResponse,
    ResolvedLocationOut,
)
from app.queries import QueriesDep
from app.storage import Location

router = APIRouter(prefix="/locations", tags=["locations"])


# fetch every saved location, so the admin can pick pickup and dropoff points when creating an order
# TODO: this is temporary until the real locations api is in place
@router.get("/")
def list_locations(admin: AdminUser, db: QueriesDep) -> LocationsResponse:
    return LocationsResponse(
        locations=[
            LocationOut(
                location_id=str(location.id),
                name=location.name,
                latitude=location.latitude,
                longitude=location.longitude,
            )
            for location in db.list_locations()
        ]
    )


@router.post("/", status_code=201)
def create_location(
    body: CreateLocationRequest, admin: AdminUser, db: QueriesDep
) -> LocationIdResponse:
    resolved = locations.resolve_location(
        suggestion_id=body.suggestion_id,
        address=body.address,
        storage=True,
    )

    location = db.add_location(
        Location(
            id=0,
            name=body.name,
            latitude=resolved.latitude,
            longitude=resolved.longitude,
        )
    )
    return LocationIdResponse(location_id=str(location.id))


@router.get("/autocomplete")
def autocomplete_location(
    admin: AdminUser,
    query: Annotated[str, Query(min_length=1)],
) -> LocationSuggestionsResponse:
    return LocationSuggestionsResponse(suggestions=locations.suggest(query))


@router.get("/geocode")
def geocode_location(
    admin: AdminUser,
    suggestion_id: Annotated[
        str | None, Query(alias="suggestionId", min_length=1)
    ] = None,
    address: Annotated[str | None, Query(min_length=1)] = None,
) -> ResolvedLocationOut:
    return locations.resolve_location(suggestion_id=suggestion_id, address=address)
