import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

DB_FILE = Path(__file__).parent / "db.json"


# Define a model for Users
class User(BaseModel):
    id: int
    name: str
    email: str
    password: (
        str  # storing in plain text for now, will change when we do the actual databse
    )
    role: str


"""
UserRepostiry defines the interface for acting with Users in the database. Its general
so that in the future we can define one that uses the real database we have deployed and so that
for now we can create a JSON user repository (for the fake JSON database we are using for now)
"""


class UserRepository(Protocol):
    def get_by_id(self, user_id: int) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...


class JsonUserRepository:
    # reads db.json and turns them all into User type objects
    def _all(self) -> list[User]:
        data = json.loads(DB_FILE.read_text())
        users: list[User] = []
        # Create a User type for each item in the json file
        for row in data["users"]:
            users.append(User(**row))
        return users

    # get a user by their ID (or return None)
    def get_by_id(self, user_id: int) -> User | None:
        for user in self._all():
            if user.id == user_id:
                return user
        return None

    # get a user by their email (or return None)
    def get_by_email(self, email: str) -> User | None:
        for user in self._all():
            if user.email == email:
                return user
        return None


# get_users() returns a UserRepository type, which currently is JsonUserRepository
# In future we will be able to change this to the interface for our actual database
def get_users() -> UserRepository:
    return JsonUserRepository()
