import uuid
from sqlalchemy.orm import Session
from ..models.user import User
from ..core.security import hash_password, verify_password


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
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


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
