import json

import bcrypt


def create_login(username: str, password: str) -> bool:
    if fetch_login_entry(username):
        return False
    user_password = password.encode("utf-8")
    hashed_password_bytes = bcrypt.hashpw(user_password, bcrypt.gensalt())
    hash_string = hashed_password_bytes.decode("utf-8")

    new_user_id = generate_user_id()
    print(f"CREATING NEW USER: email: {username}, user_id: {new_user_id}")
    return store_login(username, hash_string, new_user_id)


# Get userId from a username and password, None for no user
def validate_password(username: str, password: str) -> int | None:
    entry = fetch_login_entry(username)
    if not entry:
        return None

    password_bytes: bytes = password.encode("uft-8")
    hash_bytes: bytes = str(entry["passwordHash"]).encode("uft-8")

    password_correct: bool = bcrypt.checkpw(password_bytes, hash_bytes)
    if not password_correct:
        return -1

    user_id = entry.get("userId")
    if not user_id or not str(user_id).isnumeric():
        return None
    user_id = int(user_id)

    return user_id


# JSON version - replace with actual db version
def store_login(username: str, hashed_password: str, user_id: int) -> bool:
    if not username or not hashed_password:
        return False

    with open("login.json") as f:
        logins = json.load(f)
        logins[username] = {"userId": user_id, "passwordHash": hashed_password}
        return True


# JSON version - replace with actual db version
def fetch_login_entry(username: str) -> dict | None:
    if not username:
        return None
    with open("login.json") as f:
        logins = json.load(f)
        return logins.get(username)


def generate_user_id() -> int:
    with open("login.json") as f:
        logins = json.load(f)
        return max(int(l.get("userId")) for l in logins) + 1
