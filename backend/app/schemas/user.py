from pydantic import BaseModel, EmailStr, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class UserCreateSchema(BaseModel):
    email: EmailStr
    password: str


class GuestWatchEntry(BaseModel):
    """A single watch-progress record collected while the user was a guest."""
    movie_id: str
    current_time_seconds: int = Field(ge=0)
    duration_seconds: int = Field(ge=0, default=0)
    progress_percent: float = Field(ge=0.0, le=100.0, default=0.0)


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str
    guest_history: Optional[list[GuestWatchEntry]] = None


class UserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: str
    status: str
    created_at: datetime
    last_login_at: Optional[datetime] = None


class UserRoleUpdateSchema(BaseModel):
    role: str


class TokenResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordSchema(BaseModel):
    email: EmailStr


class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str = Field(min_length=6)
