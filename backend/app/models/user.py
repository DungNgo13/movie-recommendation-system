import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="user", nullable=False)
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Login tracking
    last_login_ip = Column(String(45), nullable=True)
    last_login_at = Column(DateTime, nullable=True)

    # Change tracking
    last_password_change = Column(DateTime, nullable=True)
    last_email_change = Column(DateTime, nullable=True)

    # Brute-force / abnormal activity detection
    failed_login_attempts = Column(Integer, default=0, nullable=False)

    # Password reset flow
    password_reset_token = Column(String(64), nullable=True, index=True)
    password_reset_expires = Column(DateTime, nullable=True)
