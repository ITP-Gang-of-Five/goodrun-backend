from fastapi import APIRouter

from app.api.deps import AdminUser
from app.locations.schemas import LocationOut, LocationsResponse
from app.queries import QueriesDep

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
