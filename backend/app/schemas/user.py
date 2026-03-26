from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from datetime import datetime


class UserCreateSchema(BaseModel):
    email: EmailStr
    password: str


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str


class UserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: str
    created_at: datetime


class UserRoleUpdateSchema(BaseModel):
    role: str


class TokenResponseSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
