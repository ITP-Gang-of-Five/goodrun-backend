from datetime import UTC, datetime, timedelta

import jwt

SECRET_KEY = "100"
ALGORITHM = "HS256"


def create_access_token(
    data: dict, expires_delta: timedelta = timedelta(minutes=15)
) -> str:
    """Generates a secure server-side JWT."""
    payload = data.copy()
    # Always set an expiration time (exp) and issued-at time (iat)
    expire = datetime.now(UTC) + expires_delta
    payload.update({"exp": expire, "iat": datetime.now(UTC)})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> dict | None:
    """Decodes and validates the signature and claims of the token."""
    try:
        # PyJWT automatically verifies 'exp' and 'iat' claims during decode
        decoded_payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded_payload
    except jwt.ExpiredSignatureError:
        print("Token has expired.")
        return None
    except jwt.InvalidTokenError:
        print("Invalid token signature or payload.")
        return None
