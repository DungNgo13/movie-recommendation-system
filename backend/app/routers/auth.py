from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..schemas.user import (
    UserCreateSchema,
    UserLoginSchema,
    UserResponseSchema,
    TokenResponseSchema,
    ForgotPasswordSchema,
    ResetPasswordSchema,
    ChangePasswordRequestSchema,
    ChangePasswordConfirmSchema,
)
from .. import database
from ..services import auth_service
from ..services.mail_service import (
    send_welcome_email,
    send_password_reset_email,
    send_password_change_email,
)
from ..core.security import (
    create_access_token,
    decode_access_token,
    create_short_lived_token,
    hash_password,
    verify_password,
)

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

    user = auth_service.get_user_by_id(db, user_id)
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


def _extract_client_ip(request: Request) -> str:
    """
    Extract the real client IP from the request.
    Checks X-Forwarded-For (reverse proxy) first, falls back to request.client.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can be a comma-separated list; first entry is the client
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


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

    # Password complexity is enforced by the Pydantic schema validator.
    # No inline length check needed here.

    user = auth_service.create_user(db, user_data.email, user_data.password)

    # Send welcome email (non-blocking — fires in a background thread)
    send_welcome_email(user.email)

    return user


@router.post("/login", response_model=TokenResponseSchema)
def login(
    user_data: UserLoginSchema,
    request: Request,
    db: Session = Depends(database.get_db),
):
    """Login and receive a JWT access token."""
    user = auth_service.authenticate_user(db, user_data.email, user_data.password)
    if user is None:
        # Record the failed attempt before returning error
        auth_service.record_login_failure(db, user_data.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Record successful login with client IP
    client_ip = _extract_client_ip(request)
    auth_service.record_login_success(db, user, client_ip)

    token = create_access_token(data={"sub": str(user.id)})

    # Merge guest watch history into the authenticated user's account
    if user_data.guest_history:
        auth_service.merge_guest_history(db, user.id, user_data.guest_history)

    return {"access_token": token, "token_type": "bearer"}


@router.post("/forgot-password", status_code=200)
def forgot_password(
    payload: ForgotPasswordSchema,
    db: Session = Depends(database.get_db),
):
    """
    Request a password reset link.
    Always returns 200 to avoid leaking whether the email exists.
    """
    token = auth_service.create_password_reset_token(db, payload.email)
    if token:
        send_password_reset_email(payload.email, token)

    # Intentionally vague response — don't reveal whether the email exists
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
def reset_password(
    payload: ResetPasswordSchema,
    db: Session = Depends(database.get_db),
):
    """Reset a user's password using a valid, non-expired token."""
    success = auth_service.reset_password(db, payload.token, payload.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )
    return {"message": "Password has been reset successfully."}


@router.post("/refresh", response_model=TokenResponseSchema)
def refresh_token(current_user=Depends(get_current_user)):
    """
    Sliding Session — issue a fresh JWT for an already-authenticated user.

    The frontend calls this when the user is still active and the current
    token has passed 50% of its lifetime.  The old token remains valid
    until its original expiry (stateless JWTs can't be revoked), but the
    frontend immediately replaces it in localStorage so subsequent
    requests use the new, longer-lived token.
    """
    new_token = create_access_token(data={"sub": str(current_user.id)})
    return {"access_token": new_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponseSchema)
def get_me(current_user=Depends(get_current_user)):
    """Get the currently authenticated user's info."""
    return current_user


# ─── Password change (email-confirmed) ────────────────────────────────────────


@router.post("/change-password-request", status_code=200)
def change_password_request(
    payload: ChangePasswordRequestSchema,
    current_user=Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Step 1 of the secure password change flow.

    Verifies the current password, validates the new password complexity,
    then sends a confirmation email with a 15-minute JWT containing the
    pre-hashed new password.

    The password is NOT changed until the user clicks the email link.
    """
    # Verify current password
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    # Complexity already validated by Pydantic field_validator.
    # Hash the new password and embed it in a short-lived token.
    new_hash = hash_password(payload.new_password)
    token = create_short_lived_token(
        data={
            "sub": str(current_user.id),
            "purpose": "change_password",
            "new_hash": new_hash,
        },
        expire_minutes=15,
    )

    send_password_change_email(current_user.email, token)

    return {"message": "Confirmation email sent. Please check your inbox."}


@router.post("/change-password-confirm", status_code=200)
def change_password_confirm(
    payload: ChangePasswordConfirmSchema,
    db: Session = Depends(database.get_db),
):
    """
    Step 2 of the secure password change flow.

    The user arrives here by clicking the confirmation link in their email.
    Validates the JWT token and applies the new password.
    """
    token_payload = decode_access_token(payload.token)
    if token_payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired confirmation token.",
        )

    if token_payload.get("purpose") != "change_password":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token purpose.",
        )

    user_id = token_payload.get("sub")
    new_hash = token_payload.get("new_hash")
    if not user_id or not new_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed token payload.",
        )

    user = auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    auth_service.change_password(db, user, new_hash)
    return {"message": "Password changed successfully."}
