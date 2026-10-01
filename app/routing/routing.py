import os
from typing import Any

import requests
from dotenv import load_dotenv

from app.errors import ApiError
from app.routing.schemas import RouteGeometry, RouteOut, RouteStop

load_dotenv()

JsonDict = dict[str, Any]

AWS_ROUTES_URL = "https://routes.geo.ap-southeast-2.amazonaws.com/v2/routes"
_TIMEOUT = 30

_session = requests.Session()


def _get_api_key() -> str:
    key_name = "AWS_LOCATION_KEY"

    try:
        return os.environ[key_name]
    except KeyError as error:
        raise ApiError(
            500, "INTERNAL_ERROR", f"{key_name} is not configured"
        ) from error


def _leg_geometry(legs: list[JsonDict]) -> list[list[float]]:
    coordinates: list[list[float]] = []

    for leg in legs:
        for point in leg.get("Geometry", {}).get("LineString", []):
            position = [float(point[0]), float(point[1])]

            # the last point of a leg is the first point of the next one
            if not coordinates or position != coordinates[-1]:
                coordinates.append(position)

    return coordinates


def calculate_route(stops: list[RouteStop]) -> RouteOut:
    body: JsonDict = {
        "Origin": [stops[0].longitude, stops[0].latitude],
        "Destination": [stops[-1].longitude, stops[-1].latitude],
        "TravelMode": "Car",
        "OptimizeRoutingFor": "FastestRoute",
        "LegGeometryFormat": "Simple",
        "DepartNow": True,
    }

    # everything between the first and last stop is a waypoint. aws drives them in
    # the order we give, it only picks the quickest way between each pair
    middle = stops[1:-1]
    if middle:
        body["Waypoints"] = [
            {"Position": [stop.longitude, stop.latitude]} for stop in middle
        ]

    try:
        response = _session.post(
            AWS_ROUTES_URL,
            params={"key": _get_api_key()},
            json=body,
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        data: JsonDict = response.json()
    except requests.RequestException as error:
        raise ApiError(502, "ROUTING_ERROR", "AWS route request failed") from error

    try:
        route = data["Routes"][0]
        summary = route["Summary"]
        coordinates = _leg_geometry(route["Legs"])

        if not coordinates:
            raise ValueError

        return RouteOut(
            distance_meters=int(summary["Distance"]),
            duration_seconds=int(summary["Duration"]),
            geometry=RouteGeometry(coordinates=coordinates),
            provider="aws",
        )
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ApiError(
            502, "ROUTING_ERROR", "AWS returned an unexpected route response"
        ) from error
