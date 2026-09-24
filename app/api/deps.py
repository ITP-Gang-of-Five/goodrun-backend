"""
Shared dependenices for pulling the caller off the Auth header and gating endpoints
to certain roles.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.tokens import read_token
from app.errors import ApiError
from app.queries import QueriesDep
from app.storage import Role, User

"""
Declares that this API is authenticated with a bearer token, which does two things
beyond reading the header for us:
"""
bearer_scheme = HTTPBearer(auto_error=False)

BearerToken = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]

"""
Retrieve the current User (storage model) based on their auth header
"""


def get_current_user(queries: QueriesDep, credentials: BearerToken = None) -> User:
    # requests must have the Authorization header with a bearer token
    if credentials is None:
        raise ApiError(401, "UNAUTHORISED", "Missing or invalid Authorization header")

    # the bearer token must be a valid access (not refresh) token for the user
    user_id = read_token(credentials.credentials, "access")
    user = queries.get_user(user_id)
    if user is None:
        raise ApiError(401, "UNAUTHORISED", "User doesn't exist")
    return user


# this allows us to grab the current logged in user without repeating auth logic at every endpoin
CurrentUser = Annotated[User, Depends(get_current_user)]


"""
Determine if the current user corresponds to the parsed role(s)
"""


def require_role(*roles: Role) -> Callable[[CurrentUser], User]:
    def check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ApiError(
                403, "FORBIDDEN", "You are not allowed to perform this action"
            )
        return user

    return check


"""
More dependencey shortcuts
"""
AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]
VolunteerUser = Annotated[User, Depends(require_role(Role.VOLUNTEER))]
AdminOrOrganisationUser = Annotated[
    User, Depends(require_role(Role.ADMIN, Role.ORGANISATION))
]
