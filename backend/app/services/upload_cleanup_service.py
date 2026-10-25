"""
Opt-in cleanup of abandoned / invalid direct-to-R2 uploads.

Nothing here runs automatically.  It is invoked explicitly via
``scripts/cleanup_r2_uploads.py`` and defaults to DRY-RUN.

Candidates (all must have ``object_deleted_at IS NULL``):
  * ``failed``  sessions  (size / content-type verification failed)
  * ``expired`` sessions
  * ``pending`` sessions whose upload URL expired more than ``grace`` ago
    (they are first moved to ``expired`` so they can no longer complete)

Safety rules — an object is deleted only if ALL hold:
  1. The session is not ``completed`` (completed sessions are never touched).
  2. The object key is inside that session's own key namespace
     ``sources/movie_<movie_id>/<session_id>/`` — never another session's.
  3. No movie currently references the key via ``movies.source_object_key``.
  4. ``dry_run`` is False and a storage client was supplied.

R2 DeleteObject is idempotent, so a missing object is treated as deleted.
Transient R2 errors are retried (bounded) by ``R2StorageService``; a
persistent error leaves ``object_deleted_at`` NULL so the next run retries.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models.movie import Movie
from ..models.upload_session import (
    UPLOAD_STATUS_EXPIRED,
    UPLOAD_STATUS_FAILED,
    UPLOAD_STATUS_PENDING,
    UploadSession,
)
from .r2_storage_service import R2StorageError, R2StorageService
from .upload_session_service import OBJECT_KEY_PREFIX

logger = logging.getLogger(__name__)

DEFAULT_GRACE = timedelta(hours=24)
DEFAULT_LIMIT = 100

ACTION_WOULD_DELETE = "would_delete"
ACTION_DELETED = "deleted"
ACTION_SKIPPED_REFERENCED = "skipped_referenced"
ACTION_SKIPPED_KEY_MISMATCH = "skipped_key_mismatch"
ACTION_SKIPPED_STATE_CHANGED = "skipped_state_changed"
ACTION_ERROR = "error"

ABANDONED_REASON = "Abandoned: not completed before the upload URL expired (cleanup)."

_ELIGIBLE_STATUSES = {UPLOAD_STATUS_FAILED, UPLOAD_STATUS_EXPIRED, UPLOAD_STATUS_PENDING}


@dataclass
class CleanupItem:
    session_id: str
    movie_id: str
    status_before: str
    status_after: str
    action: str
    detail: str = ""


@dataclass
class CleanupReport:
    dry_run: bool
    items: List[CleanupItem] = field(default_factory=list)

    def count(self, action: str) -> int:
        return sum(1 for item in self.items if item.action == action)

    @property
    def has_errors(self) -> bool:
        return self.count(ACTION_ERROR) > 0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def expected_key_prefix(session: UploadSession) -> str:
    return f"{OBJECT_KEY_PREFIX}/movie_{session.movie_id}/{session.id}/"


def find_cleanup_candidates(
    db: Session, now: datetime, grace: timedelta = DEFAULT_GRACE, limit: int = DEFAULT_LIMIT,
) -> List[UploadSession]:
    cutoff = now - grace
    return (
        db.query(UploadSession)
        .filter(
            UploadSession.object_deleted_at.is_(None),
            UploadSession.storage_backend == "r2",
            or_(
                UploadSession.status.in_([UPLOAD_STATUS_FAILED, UPLOAD_STATUS_EXPIRED]),
                and_(UploadSession.status == UPLOAD_STATUS_PENDING,
                     UploadSession.expires_at < cutoff),
            ),
        )
        .order_by(UploadSession.created_at)
        .limit(max(1, limit))
        .all()
    )


def _is_referenced(db: Session, object_key: str) -> bool:
    return db.query(Movie.id).filter(Movie.source_object_key == object_key).first() is not None


def _expire_abandoned(db: Session, session: UploadSession) -> bool:
    """Conditionally move pending → expired.  False if the state changed meanwhile."""
    updated = (
        db.query(UploadSession)
        .filter(UploadSession.id == session.id, UploadSession.status == UPLOAD_STATUS_PENDING)
        .update({"status": UPLOAD_STATUS_EXPIRED, "error": ABANDONED_REASON},
                synchronize_session=False)
    )
    if updated == 1:
        db.commit()
        db.refresh(session)
        return True
    db.rollback()
    db.refresh(session)
    return False


def _process(
    db: Session, storage: Optional[R2StorageService], session: UploadSession,
    now: datetime, dry_run: bool,
) -> CleanupItem:
    status_before = session.status
    item = CleanupItem(str(session.id), str(session.movie_id), status_before, status_before, "")

    # Rows may have been reloaded after earlier commits; re-check the state so
    # a session completed after selection is never touched.
    if status_before not in _ELIGIBLE_STATUSES:
        item.action = ACTION_SKIPPED_STATE_CHANGED
        item.detail = f"status is now {status_before}"
        return item

    if not session.object_key.startswith(expected_key_prefix(session)):
        item.action = ACTION_SKIPPED_KEY_MISMATCH
        item.detail = "object key outside this session's namespace"
        return item
    if _is_referenced(db, session.object_key):
        item.action = ACTION_SKIPPED_REFERENCED
        item.detail = "object is the active source of a movie"
        return item

    if dry_run:
        if status_before == UPLOAD_STATUS_PENDING:
            item.status_after = UPLOAD_STATUS_EXPIRED
        item.action = ACTION_WOULD_DELETE
        return item

    if status_before == UPLOAD_STATUS_PENDING and not _expire_abandoned(db, session):
        item.status_after = session.status
        item.action = ACTION_SKIPPED_STATE_CHANGED
        return item
    item.status_after = session.status

    try:
        storage.delete_object(session.object_key)
    except R2StorageError as exc:
        item.action = ACTION_ERROR
        item.detail = str(exc)
        return item

    session.object_deleted_at = now
    db.commit()
    item.action = ACTION_DELETED
    return item


def cleanup_abandoned_uploads(
    db: Session,
    storage: Optional[R2StorageService],
    *,
    dry_run: bool = True,
    now: Optional[datetime] = None,
    grace: timedelta = DEFAULT_GRACE,
    limit: int = DEFAULT_LIMIT,
) -> CleanupReport:
    """Scan candidates and (only when ``dry_run=False``) delete their objects."""
    if not dry_run and storage is None:
        raise ValueError("A storage client is required when dry_run=False")

    now = now or _utcnow()
    report = CleanupReport(dry_run=dry_run)
    for session in find_cleanup_candidates(db, now, grace, limit):
        item = _process(db, storage, session, now, dry_run)
        report.items.append(item)
        logger.info("R2 cleanup %s session=%s action=%s",
                    "dry-run" if dry_run else "execute", item.session_id, item.action)
    return report
