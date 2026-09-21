from pydantic import BaseModel, Field

#Models for each of our requests
class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserSummary(BaseModel):
    user_id: str = Field(serialization_alias="userId")
    name: str
    role: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str

#Login Response inhernets from TokenPair so that it gets the acess token and refresh token as well as the actual user
class LoginResponse(TokenPair):
    user: UserSummary



