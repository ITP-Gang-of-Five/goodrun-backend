"""
Shared helpers for referencing users in responses. Any domain (orders, runs, etc.) that needs
to show a user as { userId, name } should use these instead of building UserRefs themselves.
"""

from app.common.schemas import UserRef
from app.queries import Queries

"""
Returns a UserRef for a user based on their id
"""


def user_ref(db: Queries, user_id: int) -> UserRef:
    user = db.get_user(user_id)
    return UserRef(user_id=str(user_id), name=user.name if user else "Unknown")


"""
Returns a UserRef or none if userId is none. just a helpful wrapper
"""


def optional_user_ref(db: Queries, user_id: int | None) -> UserRef | None:
    return None if user_id is None else user_ref(db, user_id)
