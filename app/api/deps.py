"""
Shared dependenices for pulling the caller off the Auth header and gating endpoints
to certain roles.
NB: Eveyr domain router should use these instead of implementing their own auth
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header

from app.auth.tokens import read_token
from app.errors import ApiError
from app.storage import Role, User, get_database

"""
Retrieve the current User (storage model) based on their auth header
"""


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> User:
    # requests must have the Authorization header with a bearer token
    if authorization is None or not authorization.startswith("Bearer "):
        raise ApiError(401, "UNAUTHORISED", "Missing or invalid Authorization header")

    # the bearer token must be a valid access (not refresh) token for the user
    user_id = read_token(authorization.removeprefix("Bearer "), "access")
    user = get_database().get_user(user_id)
    if user is None:
        raise ApiError(401, "UNAUTHORISED", "User doesn't exist")
    return user


# Dependencny shortcut: this allows us to grab the current logged in user without repeating auth logic at every endpoin
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
More dependencey shortcuts, taking in a user and handing it back as an admin, volunteer
admin or org. we can add more later since some endpoints are accessible by: any user type,
only one user type, two user types
"""
AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]
VolunteerUser = Annotated[User, Depends(require_role(Role.VOLUNTEER))]
AdminOrOrganisationUser = Annotated[
    User, Depends(require_role(Role.ADMIN, Role.ORGANISATION))
]
