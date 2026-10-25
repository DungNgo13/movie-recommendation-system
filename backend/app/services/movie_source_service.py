"""
Source-video storage state for a movie (admin-only use).

No network I/O: R2 availability is derived from the database (a completed,
HeadObject-verified upload session that matches ``source_object_key``).
"""

import os
import uuid

from sqlalchemy.orm import Session

from ..core import api_errors as codes
from ..core.api_errors import CodedHTTPException
from ..models.movie import Movie
from ..models.upload_session import UPLOAD_STATUS_COMPLETED, UploadSession

SOURCE_LOCAL = "local"
SOURCE_R2 = "r2"


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
    return {
        "movie_id": movie.id,
        "source_storage": storage,
        "source_available": available,
        "processing_status": movie.processing_status,
        "hls_ready": bool(movie.hls_playlist_path) and movie.processing_status == "ready",
        "hls_processing_supported": storage == SOURCE_LOCAL,
    }


def ensure_hls_processing_supported(movie: Movie) -> None:
    """
    Guard for the local FFmpeg pipeline: it can only read local files, so an
    R2-backed movie must not be queued (it would silently encode a stale local
    file, or fail).  Removed once the FFmpeg R2 source resolver exists.
    """
    if movie.source_storage == SOURCE_R2:
        raise CodedHTTPException(
            409,
            "The active source video is stored in R2. HLS encoding from R2 "
            "sources is not supported yet.",
            codes.HLS_R2_SOURCE_UNSUPPORTED,
        )
