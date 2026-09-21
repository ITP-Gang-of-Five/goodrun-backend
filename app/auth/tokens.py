import os
from datetime import UTC, datetime, timedelta
from typing import Literal
import jwt
from app.errors import ApiError
from app.storage import User

#We can set JWT_SECRET in the future (and definitely should) but for now without the db just use this
SECRET = os.environ.get("JWT_SECRET", "dev-only-secret-shhhhhhhhh")

LIFETIMES = {
    #access tokens last for 1 hour
    "access": timedelta(minutes=60), 
    #refresh tokens last for 7 days
    "refresh": timedelta(days=7)
}

#Type alias for Tokens, we can just use TokenKind and it means the literal of [access token, refresh token]
TokenKind = Literal["access", "refresh"]

def make_token(user: User, kind: TokenKind) -> str:
    claims = {
        #subject for the token is the user's id
        "sub": str(user.id),
        #kind is set to either access or refresh
        "kind": kind,
        #expiry date is now + the lifetime of that kind of token
        "exp": datetime.now(UTC) + LIFETIMES[kind],
    }
    return jwt.encode(claims, SECRET, algorithm="HS256")


#Returns the ID of the user a token belogns to or 401 if the token is bad
def read_token(token: str, kind: TokenKind) -> int:
    try:
        #decode and retrieve the claims
        claims = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        #Invalid / expired token leads here
        raise ApiError(401, "UNAUTHORISED", "Invalid or expired token") from None

    #grab the subject (the user ID) for this token
    return int(claims["sub"])
