from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Role = Literal["admin", "mod"]


class UserPublic(BaseModel):
    user_id: UUID
    email: str
    display_name: str
    role: Role
    is_root_admin: bool
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=256)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=20, max_length=10000)
    password: str | None = Field(default=None, max_length=256)


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserPublic


class UserCreateRequest(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=120)
    role: Role = "mod"
    password: str = Field(min_length=8, max_length=256)


class UserRoleUpdateRequest(BaseModel):
    role: Role


class UserStatusUpdateRequest(BaseModel):
    is_active: bool
