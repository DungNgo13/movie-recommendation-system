"""
Admin-only movie source-status endpoint.

GET /api/v1/admin/movies/{movie_id}/source
    → storage backend ("local" | "r2"), availability and processing flags.
      Never returns object keys, bucket names, file paths or URLs.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import database
from ..schemas.movie_source import MovieSourceStatusSchema
from ..services import movie_source_service
from .auth import get_current_admin_user

router = APIRouter(prefix="/api/v1/admin/movies", tags=["admin-movie-source"])


@router.get("/{movie_id}/source", response_model=MovieSourceStatusSchema)
def get_movie_source_status(
    movie_id: UUID,
    db: Session = Depends(database.get_db),
    admin_user=Depends(get_current_admin_user),
):
    """Return the source-video storage state of a movie (admin only)."""
    return movie_source_service.get_source_status(db, movie_id)
