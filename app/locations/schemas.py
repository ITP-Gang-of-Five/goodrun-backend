from app.common.schemas import CamelModel


# location object as a reponse to a request (out)
class LocationOut(CamelModel):
    location_id: str
    name: str
    latitude: float
    longitude: float


# every saved location rapped in an object
class LocationsResponse(CamelModel):
    locations: list[LocationOut]
