"""
Shared input rules for request bodies and query params. Every schema should build its fields out of
these instead of plain str/datetime, so a rule (e.g. how long a name can be) is defined once and is the
same everywhere.

A value that breaks one of these rules never reaches the endpoint: FastAPI rejects the request with
422 VALIDATION_ERROR, naming the field (see app/errors.py). Rules that depend on the database or on
the state of things (e.g. "this run is still in progress") belong in the routers instead.
"""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, EmailStr, StringConstraints

# limits, shared so the frontend and any docs can quote the same numbers
NAME_MAX_LENGTH = 100
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
DESCRIPTION_MAX_LENGTH = 500
NOTES_MAX_LENGTH = 300
ADDRESS_MIN_LENGTH = 3
ADDRESS_MAX_LENGTH = 300
# NB: every autocomplete request costs us money with the external location api, so a query has to be
# long enough to be worth looking up
AUTOCOMPLETE_MIN_LENGTH = 3
AUTOCOMPLETE_MAX_LENGTH = 200
RUN_MAX_ORDERS = 20


def _lowercase(email: str) -> str:
    # emails are stored lower case so the same address can't become two accounts
    return email.lower()


def _blank_to_none(text: str | None) -> str | None:
    # an optional text field sent as "" or "   " means nothing was entered
    return text or None


def _in_the_future(moment: datetime) -> datetime:
    # a time with no timezone is taken to be UTC, which is what the api agreement uses
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    if moment <= datetime.now(UTC):
        raise ValueError("must be in the future")
    return moment


# a person's, organisation's or location's name. surrounding spaces are trimmed, and it can't be blank
Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX_LENGTH),
]

# a valid email address, trimmed and lower cased. used when creating accounts
# NB: not used for login, since the seeded admin logs in as plain "admin"
Email = Annotated[EmailStr, AfterValidator(_lowercase)]

# not trimmed, spaces are allowed in passwords
Password = Annotated[
    str,
    StringConstraints(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH),
]

# what an order is carrying. required, since it's what the volunteer is told they are picking up
Description = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=DESCRIPTION_MAX_LENGTH
    ),
]

# optional instructions for the volunteer. blank becomes None
OptionalNotes = Annotated[
    Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=NOTES_MAX_LENGTH)
    ]
    | None,
    AfterValidator(_blank_to_none),
]

# an address typed in by an admin, looked up with the external location api
Address = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=ADDRESS_MIN_LENGTH,
        max_length=ADDRESS_MAX_LENGTH,
    ),
]

# a suggestion id handed out by the location api, which we only ever pass back to it
SuggestionId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]

# a time that hasn't happened yet, e.g. when an order is due
FutureDatetime = Annotated[datetime, AfterValidator(_in_the_future)]
