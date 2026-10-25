"""
UploadSession model — tracks a single direct-to-R2 source-video upload.

Lifecycle (state machine):

    pending ──(HeadObject OK)──────────────▶ completed   (terminal, idempotent)
       │
       ├──(size / type mismatch)───────────▶ failed      (terminal)
       ├──(object missing after expiry)────▶ expired     (terminal)
       └──(cleanup job, past expiry+grace)─▶ expired     (terminal)

Only ``failed`` / ``expired`` sessions are eligible for the opt-in cleanup
job, which deletes that session's own object and records
``object_deleted_at``.  ``completed`` sessions are never cleaned up.

The presigned PUT URL itself is NEVER stored — it is returned exactly once in
the initiation response.  Only the server-generated, unpredictable
``object_key`` is persisted.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from ..database import Base


UPLOAD_STATUS_PENDING = "pending"
UPLOAD_STATUS_COMPLETED = "completed"
UPLOAD_STATUS_FAILED = "failed"
UPLOAD_STATUS_EXPIRED = "expired"

ALLOWED_UPLOAD_STATUSES = {
    UPLOAD_STATUS_PENDING,
    UPLOAD_STATUS_COMPLETED,
    UPLOAD_STATUS_FAILED,
    UPLOAD_STATUS_EXPIRED,
}


def _utcnow_naive() -> datetime:
    """Naive UTC timestamp — matches the convention used by other models."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movie_id = Column(
        UUID(as_uuid=True),
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Owner of the session.  SET NULL keeps the audit trail if an admin
    # account is later deleted; a NULL owner can never complete a session.
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    storage_backend = Column(String(10), nullable=False, default="r2", server_default="r2")
    object_key = Column(String(512), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=True)
    content_type = Column(String(100), nullable=False)
    expected_size = Column(BigInteger, nullable=False)

    status = Column(
        String(20), nullable=False,
        default=UPLOAD_STATUS_PENDING, server_default=UPLOAD_STATUS_PENDING,
    )
    actual_size = Column(BigInteger, nullable=True)
    etag = Column(String(128), nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utcnow_naive)
    expires_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    # Set by the opt-in cleanup job after the session's own object was deleted
    # (or confirmed absent).  NULL means "not cleaned up".
    object_deleted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_upload_sessions_movie_status", "movie_id", "status"),
        Index("ix_upload_sessions_status_expires", "status", "expires_at"),
    )
