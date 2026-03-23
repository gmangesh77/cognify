from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["admin", "editor", "viewer"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    role: Role
    exp: int
    iat: int
    jti: str


class RefreshTokenData(BaseModel):
    user_id: str
    token: str
    expires_at: datetime
    revoked: bool = False


class UserData(BaseModel):
    id: str
    email: str
    password_hash: str
    role: Role
