import os
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from app.errors import ApiError
from app.locations.schemas import LocationSuggestionOut, ResolvedLocationOut

load_dotenv()

JsonDict = dict[str, Any]

AWS_PLACES_URL = "https://places.geo.ap-southeast-2.amazonaws.com/v2"
_TIMEOUT = 20

MELBOURNE = [144.9631, -37.8136]

_session = requests.Session()


def _get_api_key() -> str:
    key_name = "AWS_LOCATION_KEY"

    try:
        return os.environ[key_name]
    except KeyError as error:
        raise ApiError(
            500, "INTERNAL_ERROR", f"{key_name} is not configured"
        ) from error


def _request(
    path: str,
    params: JsonDict | None = None,
    body: JsonDict | None = None,
) -> JsonDict:
    query: JsonDict = {"key": _get_api_key()}
    if params:
        query.update(params)

    url = f"{AWS_PLACES_URL}/{path}"

    try:
        if body is None:
            response = _session.get(url, params=query, timeout=_TIMEOUT)
        else:
            response = _session.post(url, params=query, json=body, timeout=_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        endpoint = path.split("/")[0]
        raise ApiError(
            502, "LOCATION_LOOKUP_FAILED", f"AWS {endpoint} request failed"
        ) from error


def suggest(query: str) -> list[LocationSuggestionOut]:
    data = _request(
        "suggest",
        body={
            "QueryText": query,
            "MaxResults": 5,
            "BiasPosition": MELBOURNE,
            "Filter": {"IncludeCountries": ["AUS"]},
            "IntendedUse": "SingleUse",
        },
    )

    try:
        suggestions = []

        for item in data.get("ResultItems", []):
            place = item.get("Place")

            if place is None:
                continue

            label = place.get("Address", {}).get("Label") or item["Title"]
            suggestions.append(
                LocationSuggestionOut(
                    suggestion_id=str(place["PlaceId"]),
                    label=str(label),
                )
            )

        return suggestions
    except (KeyError, TypeError, ValueError) as error:
        raise ApiError(
            502,
            "LOCATION_LOOKUP_FAILED",
            "AWS returned an unexpected suggest response",
        ) from error


def autocomplete(query: str) -> list[LocationSuggestionOut]:
    data = _request(
        "autocomplete",
        body={
            "QueryText": query,
            "MaxResults": 5,
            "Filter": {"IncludeCountries": ["AUS"]},
            "IntendedUse": "SingleUse",
        },
    )

    try:
        return [
            LocationSuggestionOut(
                suggestion_id=str(item["PlaceId"]),
                label=str(item.get("Address", {}).get("Label") or item["Title"]),
            )
            for item in data.get("ResultItems", [])
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise ApiError(
            502,
            "LOCATION_LOOKUP_FAILED",
            "AWS returned an unexpected autocomplete response",
        ) from error


def get_place(suggestion_id: str) -> ResolvedLocationOut:
    data = _request(
        f"place/{quote(suggestion_id, safe='')}",
        params={"intended-use": "SingleUse"},
    )

    return _parse_aws_location(data)


def geocode(address: str) -> ResolvedLocationOut:
    data = _request(
        "geocode",
        body={
            "QueryText": address,
            "MaxResults": 1,
            "Filter": {"IncludeCountries": ["AUS"]},
            "IntendedUse": "SingleUse",
        },
    )

    results = data.get("ResultItems") or []
    if not results:
        raise ApiError(404, "LOCATION_NOT_FOUND", "No location found for that address")

    return _parse_aws_location(results[0])


def resolve_location(
    suggestion_id: str | None = None,
    address: str | None = None,
) -> ResolvedLocationOut:
    if suggestion_id and address:
        raise ApiError(
            422, "VALIDATION_ERROR", "Provide either suggestionId or address, not both"
        )

    if suggestion_id:
        return get_place(suggestion_id)

    if address:
        return geocode(address)

    raise ApiError(422, "VALIDATION_ERROR", "Provide either suggestionId or address")


def _parse_aws_location(data: JsonDict) -> ResolvedLocationOut:
    try:
        position = data["Position"]
        address = data.get("Address", {}).get("Label") or data["Title"]

        return ResolvedLocationOut(
            address=str(address),
            latitude=float(position[1]),
            longitude=float(position[0]),
        )
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ApiError(
            502,
            "LOCATION_LOOKUP_FAILED",
            "AWS returned an unexpected location response",
        ) from error
