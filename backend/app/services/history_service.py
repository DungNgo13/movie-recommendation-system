from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone
from ..models.watch_history import WatchHistory
from ..models.movie import Movie

# A movie is considered "completed" when ≥ 95% watched.
COMPLETION_THRESHOLD = 95.0


def save_watch_progress(
    db: Session,
    user_id: UUID,
    movie_id: UUID,
    current_time_seconds: int,
    duration_seconds: int,
    progress_percent: float,
) -> WatchHistory:
    """
    Upsert watch progress for a user+movie pair.
    Marks as completed when progress_percent >= COMPLETION_THRESHOLD.
    """
    is_completed = progress_percent >= COMPLETION_THRESHOLD

    existing = (
        db.query(WatchHistory)
        .filter(WatchHistory.user_id == user_id, WatchHistory.movie_id == movie_id)
        .first()
    )

    if existing:
        existing.watched_at = datetime.now(timezone.utc)
        existing.playback_position_seconds = current_time_seconds
        existing.duration_seconds = duration_seconds if duration_seconds > 0 else existing.duration_seconds
        existing.progress_percent = int(progress_percent)
        existing.is_completed = is_completed
        db.commit()
        db.refresh(existing)
        return existing

    entry = WatchHistory(
        user_id=user_id,
        movie_id=movie_id,
        playback_position_seconds=current_time_seconds,
        duration_seconds=duration_seconds,
        progress_percent=int(progress_percent),
        is_completed=is_completed,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_watch_progress(
    db: Session,
    user_id: UUID,
    movie_id: UUID,
) -> dict | None:
    """
    Fetch resume data for a specific movie.
    Returns None if no record exists.
    Completed movies return position = 0 so replay starts from beginning.
    """
    history = (
        db.query(WatchHistory)
        .filter(WatchHistory.user_id == user_id, WatchHistory.movie_id == movie_id)
        .first()
    )
    if not history:
        return None

    # If the movie was fully watched, do not resume from the end
    resume_position = 0 if history.is_completed else (history.playback_position_seconds or 0)

    return {
        "movie_id": str(movie_id),
        "current_time_seconds": resume_position,
        "duration_seconds": history.duration_seconds or 0,
        "progress_percent": history.progress_percent or 0,
        "is_completed": history.is_completed,
        "watched_at": history.watched_at,
    }


def record_watch(db: Session, user_id: UUID, movie_id: UUID, playback_position_seconds: int = 0) -> WatchHistory:
    """
    Lightweight upsert used when only position is known (no duration).
    Preserved for backward-compatibility with existing call sites.
    """
    existing = (
        db.query(WatchHistory)
        .filter(WatchHistory.user_id == user_id, WatchHistory.movie_id == movie_id)
        .first()
    )
    if existing:
        existing.watched_at = datetime.now(timezone.utc)
        existing.playback_position_seconds = playback_position_seconds
        db.commit()
        db.refresh(existing)
        return existing

    entry = WatchHistory(user_id=user_id, movie_id=movie_id, playback_position_seconds=playback_position_seconds)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_movie_watch_status(db: Session, user_id: UUID, movie_id: UUID) -> dict | None:
    """Backward-compatible: return playback position for a specific movie."""
    history = (
        db.query(WatchHistory)
        .filter(WatchHistory.user_id == user_id, WatchHistory.movie_id == movie_id)
        .first()
    )
    if not history:
        return None
    return {
        "playback_position_seconds": history.playback_position_seconds or 0,
        "watched_at": history.watched_at,
    }


def get_user_history(db: Session, user_id: UUID, limit: int = 10) -> list[dict]:
    """
    Watch history list, most recent first.
    Unfinished movies appear naturally via watched_at ordering.
    """
    rows = (
        db.query(Movie, WatchHistory)
        .join(WatchHistory, WatchHistory.movie_id == Movie.id)
        .filter(WatchHistory.user_id == user_id)
        .order_by(WatchHistory.watched_at.desc())
        .limit(limit)
        .all()
    )
    from ..schemas.movie import normalize_url
    results = []
    for movie, history in rows:
        release_year = movie.release_date.year if movie.release_date else None
        results.append({
            "id": movie.id,
            "title": movie.title,
            "poster_url": normalize_url(movie.poster_path),
            "release_year": release_year,
            "watched_at": history.watched_at,
            "playback_position_seconds": history.playback_position_seconds or 0,
            "progress_percent": history.progress_percent or 0,
            "is_completed": history.is_completed or False,
        })
    return results
