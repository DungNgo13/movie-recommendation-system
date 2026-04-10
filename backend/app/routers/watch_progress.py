from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from ..schemas.watch_progress import WatchProgressPayload, WatchProgressResponse
from .. import database
from ..services import history_service
from ..routers.auth import get_current_user
from ..models.user import User

router = APIRouter(
    prefix="/api/v1/watch-progress",
    tags=["watch-progress"],
)


@router.post("", response_model=WatchProgressResponse, status_code=200)
def save_progress(
    payload: WatchProgressPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Save or update the user's playback position for a movie."""
    try:
        movie_id = UUID(payload.movie_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid movie_id format.")

    entry = history_service.save_watch_progress(
        db=db,
        user_id=current_user.id,
        movie_id=movie_id,
        current_time_seconds=payload.current_time_seconds,
        duration_seconds=payload.duration_seconds,
        progress_percent=payload.progress_percent,
    )

    return WatchProgressResponse(
        movie_id=payload.movie_id,
        current_time_seconds=entry.playback_position_seconds or 0,
        duration_seconds=entry.duration_seconds or 0,
        progress_percent=float(entry.progress_percent or 0),
        is_completed=entry.is_completed,
        watched_at=entry.watched_at,
    )


@router.get("/{movie_id}", response_model=WatchProgressResponse)
def get_progress(
    movie_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get saved playback position for a specific movie. Returns 0 if not watched."""
    result = history_service.get_watch_progress(db, current_user.id, movie_id)
    if not result:
        return WatchProgressResponse(
            movie_id=str(movie_id),
            current_time_seconds=0,
            duration_seconds=0,
            progress_percent=0.0,
            is_completed=False,
        )
    return WatchProgressResponse(**result)
