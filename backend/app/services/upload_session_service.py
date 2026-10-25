"""
Business logic for direct-to-R2 source-video upload sessions.

Flow:
  1. ``create_upload_session``   — validate movie + declared file, persist a
     ``pending`` session with an unpredictable server-side object key, return
     a short-lived presigned PUT URL (returned once, never stored).
  2. Browser PUTs the file directly to R2 (outside this API).
  3. ``complete_upload_session`` — verify the real object via HeadObject
     (size + content type), then atomically mark the session ``completed``
     and point the movie at the R2 object.  Repeated calls are idempotent.

This module deliberately does NOT touch ``video_source_path``,
``processing_status`` or any HLS field, so the existing local upload and
FFmpeg/HLS pipeline keep working unchanged.
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models.movie import Movie
from ..models.upload_session import (
    UPLOAD_STATUS_COMPLETED,
    UPLOAD_STATUS_EXPIRED,
    UPLOAD_STATUS_FAILED,
    UPLOAD_STATUS_PENDING,
    UploadSession,
)
from ..schemas.upload_session import ALLOWED_VIDEO_CONTENT_TYPES, UploadSessionCreateSchema
from .r2_storage_service import R2StorageError, R2StorageService

logger = logging.getLogger(__name__)

OBJECT_KEY_PREFIX = "sources"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_object_key(movie_id: uuid.UUID, session_id: uuid.UUID, content_type: str) -> str:
    """
    Server-generated key: ``sources/movie_<id>/<session_id>/<random>.<ext>``.
    The user-supplied filename is never part of the key, and the 144-bit
    random component makes keys unguessable even if a session id leaks.
    """
    ext = ALLOWED_VIDEO_CONTENT_TYPES[content_type]
    token = secrets.token_urlsafe(18)
    return f"{OBJECT_KEY_PREFIX}/movie_{movie_id}/{session_id}/{token}.{ext}"


# ─── Initiation ──────────────────────────────────────────────────────────────

def create_upload_session(
    db: Session,
    storage: R2StorageService,
    movie_id: uuid.UUID,
    user,
    data: UploadSessionCreateSchema,
) -> Tuple[UploadSession, str]:
    """Create a pending session and return ``(session, presigned_put_url)``."""
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    max_bytes = storage.settings.max_upload_bytes
    if data.size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Video file too large. Maximum size is {max_bytes} bytes.",
        )

    session_id = uuid.uuid4()
    object_key = build_object_key(movie_id, session_id, data.content_type)
    expires_in = storage.settings.presign_expires_seconds

    try:
        upload_url = storage.presign_put(object_key, data.content_type, expires_in)
    except Exception:  # signing is local; any failure is a server/config problem
        logger.error("Failed to presign R2 upload for movie %s", movie_id)
        raise HTTPException(status_code=502, detail="Could not create upload URL.")

    now = _utcnow()
    session = UploadSession(
        id=session_id,
        movie_id=movie_id,
        created_by_user_id=user.id,
        storage_backend="r2",
        object_key=object_key,
        original_filename=data.filename,
        content_type=data.content_type,
        expected_size=data.size,
        status=UPLOAD_STATUS_PENDING,
        created_at=now,
        expires_at=now + timedelta(seconds=expires_in),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Log identifiers only — never the presigned URL.
    logger.info("Created R2 upload session %s for movie %s", session.id, movie_id)
    return session, upload_url


# ─── Completion ──────────────────────────────────────────────────────────────

def get_owned_session(
    db: Session, movie_id: uuid.UUID, session_id: uuid.UUID, user,
) -> UploadSession:
    """Load a session that belongs to ``movie_id`` and was created by ``user``."""
    session = (
        db.query(UploadSession)
        .filter(UploadSession.id == session_id, UploadSession.movie_id == movie_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Upload session not found")
    if session.created_by_user_id is None or session.created_by_user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Upload session belongs to another user"
        )
    return session


def _transition_from_pending(db: Session, session: UploadSession, **values) -> bool:
    """
    Atomically move a session out of ``pending``.  Uses a conditional UPDATE
    so two concurrent completions cannot both succeed.  Does not commit.
    """
    updated = (
        db.query(UploadSession)
        .filter(UploadSession.id == session.id, UploadSession.status == UPLOAD_STATUS_PENDING)
        .update(values, synchronize_session=False)
    )
    return updated == 1


def _fail_session(db: Session, session: UploadSession, status: str, reason: str) -> None:
    if _transition_from_pending(db, session, status=status, error=reason):
        db.commit()
    else:
        db.rollback()
    db.refresh(session)


def complete_upload_session(
    db: Session,
    storage: R2StorageService,
    movie_id: uuid.UUID,
    session_id: uuid.UUID,
    user,
) -> UploadSession:
    """Verify the uploaded object and mark the session completed (idempotent)."""
    session = get_owned_session(db, movie_id, session_id, user)

    if session.status == UPLOAD_STATUS_COMPLETED:
        return session  # idempotent: no second HeadObject, no DB change
    if session.status != UPLOAD_STATUS_PENDING:
        raise HTTPException(status_code=409, detail=f"Upload session is {session.status}")

    try:
        info = storage.head_object(session.object_key)
    except R2StorageError:
        raise HTTPException(status_code=502, detail="Could not verify upload with storage.")

    if info is None:
        if _utcnow() > session.expires_at:
            _fail_session(db, session, UPLOAD_STATUS_EXPIRED,
                          "Object was not uploaded before the upload URL expired.")
            raise HTTPException(status_code=409, detail="Upload session expired")
        raise HTTPException(
            status_code=409,
            detail="Uploaded object not found. Finish the upload, then retry completion.",
        )

    mismatch = _verification_error(session, info.size, info.content_type)
    if mismatch:
        _fail_session(db, session, UPLOAD_STATUS_FAILED, mismatch)
        raise HTTPException(status_code=422, detail=mismatch)

    return _finalize(db, session, info.size, info.etag)


def _verification_error(
    session: UploadSession, actual_size: int, actual_type: Optional[str],
) -> Optional[str]:
    if actual_size != session.expected_size:
        return (f"Uploaded size {actual_size} bytes does not match declared size "
                f"{session.expected_size} bytes.")
    if (actual_type or "").split(";")[0].strip().lower() != session.content_type:
        return "Uploaded content type does not match the declared content type."
    return None


def _finalize(db: Session, session: UploadSession, size: int, etag: Optional[str]) -> UploadSession:
    now = _utcnow()
    won = _transition_from_pending(
        db, session,
        status=UPLOAD_STATUS_COMPLETED, actual_size=size, etag=etag,
        completed_at=now, error=None,
    )
    if not won:
        # A concurrent request already moved the session; report its outcome.
        db.rollback()
        db.refresh(session)
        if session.status == UPLOAD_STATUS_COMPLETED:
            return session
        raise HTTPException(status_code=409, detail=f"Upload session is {session.status}")

    movie = db.query(Movie).filter(Movie.id == session.movie_id).first()
    if movie is None:  # deleted between steps; FK cascade will remove session
        db.rollback()
        raise HTTPException(status_code=404, detail="Movie not found")

    movie.source_storage = "r2"
    movie.source_object_key = session.object_key
    db.commit()
    db.refresh(session)
    logger.info("Completed R2 upload session %s for movie %s", session.id, session.movie_id)
    return session
