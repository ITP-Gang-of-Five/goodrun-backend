"""
Turning passwords into hashes and checking them, so the database never holds anyone's
actual password.

Uses Argon2, the currently recommended algorithm for storing passwords. It is slow on
purpose (about 75ms a check), which is what makes guessing passwords from a leaked
database impractical. The settings it was made with are stored inside each hash, so
they can be changed later without breaking existing accounts.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# a hash that no real password matches. checked against when nobody has the email that
# was entered, so an unknown email takes as long to reject as a wrong password does.
# otherwise how quickly a login failed would give away which emails have accounts
DUMMY_HASH = _hasher.hash("not anyone's password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError, InvalidHashError:
        # a wrong password, or a stored value that isn't a hash at all (e.g. an account
        # left over from before passwords were hashed)
        return False
