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
