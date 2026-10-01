from typing import Literal

from pydantic import Field

from app.common.schemas import CamelModel


class RouteStop(CamelModel):
    location_id: str
    latitude: float
    longitude: float


# visited in the order they come in, we dont reorder them. aws takes 23 waypoints
# between the origin and destination, so 25 stops is our cap
class RouteRequest(CamelModel):
    stops: list[RouteStop] = Field(min_length=2, max_length=25)


# geojson, so coordinates are [longitude, latitude]
class RouteGeometry(CamelModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]]


class RouteOut(CamelModel):
    distance_meters: int
    duration_seconds: int
    geometry: RouteGeometry
    provider: str
