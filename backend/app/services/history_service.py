from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone
from ..models.watch_history import WatchHistory
from ..models.movie import Movie


def record_watch(db: Session, user_id: UUID, movie_id: UUID) -> WatchHistory:
    """
    Records a movie view. If already watched, updates watched_at (upsert pattern).
    """
    existing = (
        db.query(WatchHistory)
        .filter(WatchHistory.user_id == user_id, WatchHistory.movie_id == movie_id)
        .first()
    )
    if existing:
        existing.watched_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    entry = WatchHistory(user_id=user_id, movie_id=movie_id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_user_history(db: Session, user_id: UUID, limit: int = 10) -> list[dict]:
    """
    Gets the user's watch history with movie details, ordered by most recent first.
    """
    rows = (
        db.query(Movie, WatchHistory.watched_at)
        .join(WatchHistory, WatchHistory.movie_id == Movie.id)
        .filter(WatchHistory.user_id == user_id)
        .order_by(WatchHistory.watched_at.desc())
        .limit(limit)
        .all()
    )
    from ..schemas.movie import normalize_url
    results_list = []
    for movie, watched_at in rows:
        release_year = None
        if movie.release_date:
            release_year = movie.release_date.year
        results_list.append({
            "id": movie.id,
            "title": movie.title,
            "poster_url": normalize_url(movie.poster_path),
            "release_year": release_year,
            "watched_at": watched_at,
        })
    return results_list
