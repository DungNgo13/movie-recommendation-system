"""
Source-video storage state for a movie (admin-only use).

No network I/O: R2 availability is derived from the database (a completed,
HeadObject-verified upload session that matches ``source_object_key``).
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from ..core import api_errors as codes
from ..core.api_errors import CodedHTTPException
from ..models.movie import Movie
from ..models.upload_session import UPLOAD_STATUS_COMPLETED, UploadSession
from .r2_storage_service import REQUIRED_ENV_VARS

SOURCE_LOCAL = "local"
SOURCE_R2 = "r2"


def is_r2_configured() -> bool:
    """Return True if all required R2 configuration environment variables are set."""
    return all(bool((os.getenv(name) or "").strip()) for name in REQUIRED_ENV_VARS)


def _local_source_available(movie: Movie) -> bool:
    path = movie.video_source_path
    if not path or path.startswith("http"):
        return False
    return os.path.isfile(path)


def _r2_source_available(db: Session, movie: Movie) -> bool:
    if not movie.source_object_key:
        return False
    return db.query(UploadSession.id).filter(
        UploadSession.movie_id == movie.id,
        UploadSession.object_key == movie.source_object_key,
        UploadSession.status == UPLOAD_STATUS_COMPLETED,
    ).first() is not None


def get_source_status(db: Session, movie_id: uuid.UUID) -> dict:
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if movie is None:
        raise CodedHTTPException(404, "Movie not found", codes.MOVIE_NOT_FOUND)

    storage = SOURCE_R2 if movie.source_storage == SOURCE_R2 else SOURCE_LOCAL
    available = (_r2_source_available(db, movie) if storage == SOURCE_R2
                 else _local_source_available(movie))
    
    # HLS processing is supported for local sources, and for R2 sources when
    # verified available and R2 configuration is present.
    if storage == SOURCE_R2:
        hls_supported = bool(available and is_r2_configured())
    else:
        hls_supported = True

    return {
        "movie_id": movie.id,
        "source_storage": storage,
        "source_available": available,
        "processing_status": movie.processing_status,
        "hls_ready": bool(movie.hls_playlist_path) and movie.processing_status == "ready",
        "hls_processing_supported": hls_supported,
    }


def ensure_hls_processing_supported(movie: Movie, db: Optional[Session] = None) -> None:
    """
    Validate that the movie's active source is ready and supported for HLS conversion.

    Supports both 'local' and 'r2' sources.
    Raises structured CodedHTTPException if requirements are not met.
    """
    storage = movie.source_storage or SOURCE_LOCAL

    if storage == SOURCE_R2:
        if not is_r2_configured():
            raise CodedHTTPException(
                503,
                "R2 storage is not configured.",
                codes.STORAGE_NOT_CONFIGURED,
            )
        if not movie.source_object_key:
            raise CodedHTTPException(
                422,
                "No source video found. Upload a video file first.",
                codes.MOVIE_NOT_FOUND,
            )
        if db is not None and not _r2_source_available(db, movie):
            raise CodedHTTPException(
                409,
                "R2 source object is not verified or session incomplete.",
                codes.UPLOAD_OBJECT_MISSING,
            )
        return

    if storage == SOURCE_LOCAL:
        if not movie.video_source_path:
            raise CodedHTTPException(
                422,
                "No source video found. Upload a video file first.",
                codes.MOVIE_NOT_FOUND,
            )
        return

    raise CodedHTTPException(
        400,
        f"Unsupported source storage type '{storage}'.",
        codes.MOVIE_NOT_FOUND,
    )
