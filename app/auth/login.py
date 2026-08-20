import json
from pathlib import Path

import bcrypt

from app.auth.exceptions import (
    IncorrectPasswordError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.models.entities import LoginRecord

BASE_DIR = Path(__file__).resolve().parent
JSON_FILE_PATH = BASE_DIR / "login.json"


def mock_db():
    global JSON_FILE_PATH
    JSON_FILE_PATH = BASE_DIR / "test_login.json"
    with open(JSON_FILE_PATH, "w") as f:
        json.dump({}, f)


def create_login(username: str, password: str) -> int:
    if fetch_login_entry(username):
        raise UserAlreadyExistsError("This username is already in use")

    user_password = password.encode("utf-8")
    hashed_password_bytes = bcrypt.hashpw(user_password, bcrypt.gensalt())
    hash_string = hashed_password_bytes.decode("utf-8")

    new_user_id = generate_user_id()
    store_login(username, hash_string, new_user_id)
    return new_user_id


# returns if the username and password match and if so returns the users id else None
def validate_password(username: str, password: str) -> int:
    entry = fetch_login_entry(username)
    if not entry:
        raise UserNotFoundError("The login record could not be found")

    password_bytes: bytes = password.encode("utf-8")
    hash_bytes: bytes = str(entry.password_hash).encode("utf-8")

    password_correct: bool = bcrypt.checkpw(password_bytes, hash_bytes)
    if not password_correct:
        raise IncorrectPasswordError("The password in incorrect")

    return entry.user_id


"""
---------------------------------
BELOW ARE THESE ARE TEMP JSON DB FUNCTIONS!
PLEASE FIX WHEN DB IS IMPLEMENTED
---------------------------------
"""


# JSON version - replace with actual db version
def store_login(username: str, hashed_password: str, user_id: int) -> bool:
    if not username or not hashed_password:
        return False

    with open(JSON_FILE_PATH) as f:
        logins = json.load(f)

    logins[username] = {"userId": user_id, "passwordHash": hashed_password}

    with open(JSON_FILE_PATH, "w") as f:
        json.dump(logins, f)
        return True


# JSON version - replace with actual db version
def fetch_login_entry(username: str) -> LoginRecord | None:
    if not username:
        return None
    with open(JSON_FILE_PATH) as f:
        logins = json.load(f)
        entry = logins.get(username)
        if not entry:
            return None
        return LoginRecord(int(entry["userId"]), entry["passwordHash"])


def generate_user_id() -> int:
    with open(JSON_FILE_PATH) as f:
        login_records = json.load(f)

        user_ids = [
            int(login_records[username].get("userId")) for username in login_records
        ]
        if user_ids:
            return max(user_ids) + 1
        else:
            return 0
