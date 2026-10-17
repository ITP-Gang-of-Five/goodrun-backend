"""
Shared helpers for referencing users in responses. Any domain (orders, runs, etc.) that needs
to show a user as { userId, name } should use these instead of building UserRefs themselves.
"""

from app.common.schemas import UserRef
from app.errors import ApiError
from app.queries import Queries
from app.storage import User


# NB: for someone without a name (i.e a user who isn't signed up yet) their email is returned
def _name(user: User | None) -> str:
    if user is None:
        return "Unknown"
    return user.name or user.email


"""
Returns a UserRef for a user based on their id
"""


def user_ref(db: Queries, user_id: int) -> UserRef:
    user = db.get_user(user_id)
    return UserRef(user_id=str(user_id), name=_name(user))


"""
Returns a UserRef or none if userId is none. just a helpful wrapper
"""


def optional_user_ref(db: Queries, user_id: int | None) -> UserRef | None:
    return None if user_id is None else user_ref(db, user_id)


"""
Same as user_ref, but using users that were already fetched in bulk (see Queries.get_users),
"""


def user_ref_from(users: dict[int, User], user_id: int | None) -> UserRef | None:
    if user_id is None:
        return None
    user = users.get(user_id)
    return UserRef(user_id=str(user_id), name=_name(user))


"""
Stops a second account being made with an email that's already used, by any role. Emails are
compared ignoring case and surrounding spaces (see Queries.get_user_by_email)
"""


def require_unused_email(db: Queries, email: str) -> None:
    if db.get_user_by_email(email) is not None:
        raise ApiError(
            409, "EMAIL_ALREADY_IN_USE", "An account with that email already exists"
        )
