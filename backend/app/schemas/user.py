from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator, computed_field
from uuid import UUID
from datetime import datetime
from typing import Optional
import os

from ..core.password_validator import validate_password_complexity


# The public base URL of this backend — used to build absolute avatar URLs.
_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")


def _normalize_avatar_url(path: Optional[str]) -> Optional[str]:
    """Convert a relative avatar path to a full public URL."""
    if not path:
        return None
    if path.startswith("http"):
        return path
    clean = path.lstrip("/\\")
    return f"{_BACKEND_URL}/{clean}"


# ─── Password validation mixin ───────────────────────────────────────────────

def _validate_password_field(password: str, email: str = "") -> str:
    """Shared validator — raises ValueError with all violation messages."""
    errors = validate_password_complexity(password, email)
    if errors:
        raise ValueError("; ".join(errors))
    return password


class UserCreateSchema(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: str, info) -> str:
        # info.data contains already-validated fields; email is validated before password
        email = info.data.get("email", "")
        return _validate_password_field(v, email)


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

    # Avatar — raw DB column excluded; public URL exposed via computed_field
    avatar_path: Optional[str] = Field(None, exclude=True)

    @computed_field
    @property
    def avatar_url(self) -> Optional[str]:
        return _normalize_avatar_url(self.avatar_path)


class UserRoleUpdateSchema(BaseModel):
    role: str


class TokenResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordSchema(BaseModel):
    email: EmailStr


class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return _validate_password_field(v)


class ForceResetPasswordSchema(BaseModel):
    """Admin-only: payload for force-resetting a user's password."""
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return _validate_password_field(v)


class UserSecurityAuditSchema(BaseModel):
    """Admin-only: full security audit view of a user."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: str
    status: str
    created_at: datetime
    last_login_ip: Optional[str] = None
    last_login_at: Optional[datetime] = None
    last_password_change: Optional[datetime] = None
    last_email_change: Optional[datetime] = None
    failed_login_attempts: int = 0


# ─── Password change flow schemas ────────────────────────────────────────────


class ChangePasswordRequestSchema(BaseModel):
    """Payload for requesting a password change (step 1)."""
    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return _validate_password_field(v)


class ChangePasswordConfirmSchema(BaseModel):
    """Payload for confirming a password change via email token (step 2)."""
    token: str
