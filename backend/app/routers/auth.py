from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..schemas.user import (
    UserCreateSchema,
    UserLoginSchema,
    UserResponseSchema,
    TokenResponseSchema,
)
from .. import database
from ..services import auth_service
from ..core.security import create_access_token, decode_access_token

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db),
):
    """
    Dependency that extracts and validates the current user from a JWT token.
    Returns None if no token or invalid token.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = auth_service.get_user_by_email(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_current_admin_user(current_user=Depends(get_current_user)):
    """
    Dependency that ensures the current user is an admin.
    Returns 403 Forbidden if the user is not an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


@router.post("/register", response_model=UserResponseSchema, status_code=201)
def register(
    user_data: UserCreateSchema,
    db: Session = Depends(database.get_db),
):
    """Register a new user."""
    existing = auth_service.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    if not user_data.password or len(user_data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters",
        )

    user = auth_service.create_user(db, user_data.email, user_data.password)
    return user


@router.post("/login", response_model=TokenResponseSchema)
def login(
    user_data: UserLoginSchema,
    db: Session = Depends(database.get_db),
):
    """Login and receive a JWT access token."""
    user = auth_service.authenticate_user(db, user_data.email, user_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponseSchema)
def get_me(current_user=Depends(get_current_user)):
    """Get the currently authenticated user's info."""
    return current_user
