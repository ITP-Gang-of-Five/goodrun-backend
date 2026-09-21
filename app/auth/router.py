from fastapi import APIRouter

#import all of the schemas defined in schemas.py
from app.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenPair,
    UserSummary,
)
from app.auth.tokens import make_token, read_token
from app.errors import ApiError
from app.storage import get_users

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest) -> LoginResponse:

    #grab the user by their email (since that is what is inputted into the request body)
    user = get_users().get_by_email(body.email)

    #if user doesn't exit or the password isn't correct (NB: will use actual encryption and things later)
    if user is None or user.password != body.password:
        raise ApiError(401, "INVALID_CREDENTIALS", "Incorrect email or password")

    return LoginResponse(
        #make all of the necessary tokens for this user
        access_token=make_token(user, "access"),
        refresh_token=make_token(user, "refresh"),
        #create a UserSummary type to be returned with the user's attributes
        user=UserSummary(user_id=str(user.id), name=user.name, role=user.role),
    )


@router.post("/refresh-token")
def refresh_token(body: RefreshRequest) -> TokenPair:
    #grab the user by their refresh token
    #NB: if the token is invalid for the user, an exception will be raised here and the request
    #will get an error code returend for it
    user = get_users().get_by_id(read_token(body.refresh_token, "refresh"))
    #if no user is assigned to this refresh token
    if user is None:
        raise ApiError(401, "UNAUTHORISED", "User doesn't exist")

    #return a new token pair of a new access and refresh token for the user
    return TokenPair(
        access_token=make_token(user, "access"),
        refresh_token=make_token(user, "refresh"),
    )
