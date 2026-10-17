"""
Create an admin account in whatever DATABASE_URL points at.

    uv run python scripts/create_admin.py

This is how the first admin gets into a fresh production database, since production
doesn't load seed.sql and there is no sign up. That admin then makes the volunteer and
organisation accounts in the platform. It asks for the details rather than taking them as
arguments, so the password never ends up in your shell history.
"""

import getpass
import sys
from datetime import UTC, datetime

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from pydantic import BaseModel, ValidationError

from app.auth.passwords import hash_password
from app.common.users import require_unused_email
from app.common.validation import Email, Name, Password
from app.errors import ApiError
from app.queries import DATABASE_URL, Queries
from app.storage import Role, User


# the same rules the api applies to any other new account
class NewAdmin(BaseModel):
    name: Name
    email: Email
    password: Password


def create_admin(db: Queries, name: str, email: str, password: str) -> User:
    """Raises ValidationError for bad details, or ApiError if the email is taken."""
    details = NewAdmin(name=name, email=email, password=password)
    require_unused_email(db, details.email)
    return db.add_user(
        User(
            id=0,
            name=details.name,
            email=details.email,
            password_hash=hash_password(details.password),
            role=Role.ADMIN,
            created_at=datetime.now(UTC),
        )
    )


def main() -> int:
    # say which database this is about to change, so nobody adds an admin to the wrong one
    host = conninfo_to_dict(DATABASE_URL).get("host", "unknown host")
    print(f"Creating an admin account in the database at {host}")

    name = input("Name: ")
    email = input("Email: ")
    password = getpass.getpass("Password: ")
    if getpass.getpass("Password again: ") != password:
        print("The passwords don't match, nothing was created", file=sys.stderr)
        return 1

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        try:
            admin = create_admin(Queries(connection), name, email, password)
        except ValidationError as error:
            problem = error.errors()[0]
            print(f"{problem['loc'][0]}: {problem['msg']}", file=sys.stderr)
            return 1
        except ApiError as error:
            print(error.description, file=sys.stderr)
            return 1
        connection.commit()

    print(f"Created admin {admin.email}, they can log in now")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
