import uuid
import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from ..models.user import User
from ..core.security import hash_password, verify_password

# An account is flagged as "suspect" after this many consecutive failed logins.
MAX_FAILED_ATTEMPTS = 5


def get_user_by_id(db: Session, user_id: str) -> User | None:
    # Safely handle invalid UUID formats if an old email token comes through during transition
    try:
        uid = uuid.UUID(user_id)
        return db.query(User).filter(User.id == uid).first()
    except Exception:
        return None


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, email: str, password: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        last_password_change=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """
    Validate credentials. Does NOT update login tracking — the caller
    must call record_login_success / record_login_failure explicitly
    so that the IP address (available only at the router layer) can be passed in.
    """
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# ─── Login tracking ──────────────────────────────────────────────────────────


def record_login_success(db: Session, user: User, ip: str) -> None:
    """Update user record after a successful login."""
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = ip
    user.failed_login_attempts = 0
    # If the account was flagged suspect by failed attempts, restore it.
    if user.status == "suspect":
        user.status = "active"
    db.commit()


def record_login_failure(db: Session, email: str) -> None:
    """
    Increment the failed-attempt counter for the given email.
    If the threshold is reached, set the account status to 'suspect'.
    """
    user = get_user_by_email(db, email)
    if user is None:
        return  # Don't leak whether the email exists

    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.status = "suspect"
    db.commit()


# ─── Password reset ─────────────────────────────────────────────────────────


def create_password_reset_token(db: Session, email: str) -> str | None:
    """
    Generate a secure reset token for the given email.
    Returns the token string, or None if the email doesn't exist.
    The token expires after 1 hour.
    """
    user = get_user_by_email(db, email)
    if user is None:
        return None

    token = secrets.token_hex(32)  # 64-char hex string
    user.password_reset_token = token
    user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()
    return token


def reset_password(db: Session, token: str, new_password: str) -> bool:
    """
    Validate the reset token and change the user's password.
    Returns True on success, False on invalid/expired token.
    Clears the token after use regardless of outcome.
    """
    user = db.query(User).filter(User.password_reset_token == token).first()
    if user is None:
        return False

    now = datetime.now(timezone.utc)
    expired = user.password_reset_expires is None or user.password_reset_expires < now

    # Always clear the token (single-use, even if expired)
    user.password_reset_token = None
    user.password_reset_expires = None

    if expired:
        db.commit()
        return False

    user.password_hash = hash_password(new_password)
    user.last_password_change = now
    # Reset suspect status if present — user proved identity via email
    if user.status == "suspect":
        user.status = "active"
    user.failed_login_attempts = 0
    db.commit()
    return True


def change_password(db: Session, user: User, new_password_hash: str) -> None:
    """
    Apply a pre-hashed password to the user record.

    Used by the change-password-confirm flow where the hash was already
    computed and stored inside a short-lived JWT.
    """
    user.password_hash = new_password_hash
    user.last_password_change = datetime.now(timezone.utc)
    if user.status == "suspect":
        user.status = "active"
    user.failed_login_attempts = 0
    db.commit()


# ─── Guest history merge (Cold Start) ────────────────────────────────────────


def merge_guest_history(
    db: Session,
    user_id: uuid.UUID,
    guest_history: list,
) -> int:
    """
    Upsert guest watch-progress records into the DB for the given user.
    Returns the number of successfully merged entries.
    Non-fatal: individual entry failures are skipped so login always succeeds.
    """
    from ..services.history_service import save_watch_progress

    merged = 0
    for entry in guest_history:
        try:
            movie_id = uuid.UUID(entry.movie_id)
            save_watch_progress(
                db=db,
                user_id=user_id,
                movie_id=movie_id,
                current_time_seconds=entry.current_time_seconds,
                duration_seconds=entry.duration_seconds,
                progress_percent=entry.progress_percent,
            )
            merged += 1
        except Exception:
            # Skip invalid entries — don't block login
            continue
    return merged
