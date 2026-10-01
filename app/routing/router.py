from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.routing import routing
from app.routing.schemas import RouteOut, RouteRequest

router = APIRouter(prefix="/routing", tags=["routing"])


# any logged in user can ask for this, it reads nothing out of our database
@router.post("/route")
def route_stops(body: RouteRequest, user: CurrentUser) -> RouteOut:
    return routing.calculate_route(body.stops)
