from fastapi import APIRouter, Request

from app.auth.limits import client_ip, login_attempts
from app.auth.passwords import DUMMY_HASH, verify_password

# import all of the schemas defined in schemas.py
from app.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenPair,
    UserSummary,
)
from app.auth.tokens import make_token, read_token
from app.errors import ApiError
from app.queries import QueriesDep

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, request: Request, queries: QueriesDep) -> LoginResponse:
    # refuse straight away if whoever is asking has had too many wrong passwords recently
    ip = client_ip(request)
    login_attempts.check(ip, body.email)

    # grab the user by their email (since that is what is inputted into the request body)
    user = queries.get_user_by_email(body.email)

    # NB: the password is checked even when no account has this email (against a dummy
    # hash), so an unknown email is as slow to reject as a wrong password and the timing
    # doesn't give away which emails have accounts
    password_ok = verify_password(
        body.password, user.password_hash if user else DUMMY_HASH
    )

    # if user doesn't exist or the password isn't correct
    if user is None or not password_ok:
        login_attempts.record_failure(ip, body.email)
        raise ApiError(401, "INVALID_CREDENTIALS", "Incorrect email or password")

    login_attempts.clear(ip, body.email)

    return LoginResponse(
        # make all of the necessary tokens for this user
        access_token=make_token(user, "access"),
        refresh_token=make_token(user, "refresh"),
        # create a UserSummary type to be returned with the user's attributes
        user=UserSummary(user_id=str(user.id), name=user.name, role=user.role),
    )


@router.post("/refresh-token")
def refresh_token(body: RefreshRequest, queries: QueriesDep) -> TokenPair:
    # grab the user by their refresh token
    # NB: if the token is invalid for the user, an exception will be raised here and the request
    # will get an error code returend for it
    user = queries.get_user(read_token(body.refresh_token, "refresh"))
    # if no user is assigned to this refresh token
    if user is None:
        raise ApiError(401, "UNAUTHORISED", "User doesn't exist")

    # return a new token pair of a new access and refresh token for the user
    return TokenPair(
        access_token=make_token(user, "access"),
        refresh_token=make_token(user, "refresh"),
    )
