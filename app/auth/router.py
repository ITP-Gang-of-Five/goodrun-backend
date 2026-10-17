from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.auth.invites import is_usable
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


def _wrong_credentials() -> JSONResponse:
    # NB: this is returend rather than raised since that would rollback the database change
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "INVALID_CREDENTIALS",
                "description": "Incorrect email or password",
            }
        },
    )


# NB: response_model is set because a wrong password returns a JSONResponse instead
@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest, request: Request, queries: QueriesDep
) -> LoginResponse | JSONResponse:
    # refuse straight away if whoever is asking has had too many wrong passwords recently
    ip = client_ip(request)
    login_attempts.check(ip, body.email)

    # grab the user by their email (since that is what is inputted into the request body)
    user = queries.get_user_by_email(body.email)

    # for a person whose been invited, they login with their onboarding password, everyone else
    # just uses their real password
    invite = queries.get_invite(user.id) if user and user.onboarded_at is None else None

    if user is not None and user.onboarded_at is None:
        usable = is_usable(invite)
        stored_hash = invite.code_hash if invite and usable else DUMMY_HASH
        password_ok = verify_password(body.password.strip(), stored_hash) and usable
    else:
        # check against a dummmy hash when no acconut has this email to defend against attackers
        stored_hash = user.password_hash if user and user.password_hash else DUMMY_HASH
        password_ok = verify_password(body.password, stored_hash)

    # if user doesn't exist or the password isn't correct
    if user is None or not password_ok:
        login_attempts.record_failure(ip, body.email)
        if invite is not None:
            queries.record_failed_invite_attempt(invite.user_id)
        return _wrong_credentials()

    login_attempts.clear(ip, body.email)
    # NB: we delete the invite code if it was used, as this should only work one time!!!!
    if invite is not None:
        queries.delete_invite(user.id)

    return LoginResponse(
        access_token=make_token(user, "access"),
        refresh_token=make_token(user, "refresh"),
        # create a UserSummary type to be returned with the user's attributes
        user=UserSummary(
            user_id=str(user.id),
            name=user.name,
            role=user.role,
            onboarded=user.onboarded_at is not None,
        ),
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
