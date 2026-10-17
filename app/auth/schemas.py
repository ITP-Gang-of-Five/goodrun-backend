from pydantic import BaseModel, Field

from app.common.validation import PASSWORD_MAX_LENGTH


# Models for each of our requests
class LoginRequest(BaseModel):
    # NB: not the Email type, since the seeded admin logs in as plain "admin"
    email: str = Field(max_length=255)
    # capped so nobody can make the server hash a huge password, which is slow on purpose
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class RefreshRequest(BaseModel):
    refresh_token: str


class UserSummary(BaseModel):
    user_id: str = Field(serialization_alias="userId")
    # None until the account is fully set up
    name: str | None
    role: str
    # False: they logged in with an invite code but haven't yet setup their account
    onboarded: bool


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


# Login Response inhernets from TokenPair so that it gets the acess token and refresh token as well as the actual user
class LoginResponse(TokenPair):
    user: UserSummary
