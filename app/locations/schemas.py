from app.common.schemas import CamelModel


# location object as a reponse to a request (out)
class LocationOut(CamelModel):
    location_id: str
    name: str
    latitude: float
    longitude: float
