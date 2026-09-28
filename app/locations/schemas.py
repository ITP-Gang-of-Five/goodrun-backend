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


class LocationSuggestionOut(CamelModel):
    suggestion_id: str
    label: str


class LocationSuggestionsResponse(CamelModel):
    suggestions: list[LocationSuggestionOut]


class ResolvedLocationOut(CamelModel):
    address: str
    latitude: float
    longitude: float


class CreateLocationRequest(CamelModel):
    name: str
    suggestion_id: str | None = None
    address: str | None = None


class LocationIdResponse(CamelModel):
    location_id: str
