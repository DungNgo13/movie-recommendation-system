"""
Admin-only endpoints for direct-to-R2 source-video uploads.

POST /api/v1/admin/movies/{movie_id}/uploads
     → create a pending session, return a short-lived presigned PUT URL
POST /api/v1/admin/movies/{movie_id}/uploads/{session_id}/complete
     → verify the object via HeadObject and mark the session completed
       (idempotent: repeated calls return the same completed session)

The existing multipart endpoint POST /api/v1/movies/{movie_id}/video and the
FFmpeg/HLS endpoints are unchanged.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import database
from ..schemas.upload_session import (
    UploadSessionCreateResponseSchema,
    UploadSessionCreateSchema,
    UploadSessionSchema,
)
from ..services import upload_session_service
from ..services.admin_service import create_audit_log
from ..services.r2_storage_service import (
    R2StorageService,
    get_optional_r2_storage,
    get_r2_storage,
)
from .auth import get_current_admin_user

router = APIRouter(
    prefix="/api/v1/admin/movies/{movie_id}/uploads",
    tags=["admin-uploads"],
)


@router.post("", response_model=UploadSessionCreateResponseSchema, status_code=201)
def create_upload(
    movie_id: UUID,
    data: UploadSessionCreateSchema,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
    storage: R2StorageService = Depends(get_r2_storage),
):
    """Initiate a direct R2 upload for a movie's source video (admin only)."""
    session, upload_url = upload_session_service.create_upload_session(
        db, storage, movie_id, admin_user, data,
    )
    create_audit_log(
        db=db,
        admin_email=admin_user.email,
        action_type="movie_update",
        target_type="movie",
        target_id=str(movie_id),
        description=f"Initiated R2 source upload session {session.id}",
    )
    return {
        "session": session,
        "upload_url": upload_url,
        "upload_method": "PUT",
        "upload_headers": {"Content-Type": session.content_type},
        "expires_in_seconds": storage.settings.presign_expires_seconds,
    }


@router.post("/{session_id}/complete", response_model=UploadSessionSchema)
def complete_upload(
    movie_id: UUID,
    session_id: UUID,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
    storage: Optional[R2StorageService] = Depends(get_optional_r2_storage),
):
    """
    Verify the uploaded object and mark the session completed (admin, owner
    only).  Replays of a completed session are answered from the database
    without contacting R2.
    """
    result = upload_session_service.complete_upload_session(
        db, storage, movie_id, session_id, admin_user,
    )
    if result.newly_completed:
        create_audit_log(
            db=db,
            admin_email=admin_user.email,
            action_type="movie_update",
            target_type="movie",
            target_id=str(movie_id),
            description=f"Completed R2 source upload session {result.session.id}",
        )
    return result.session
