from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone
from ..models.rating import Rating


def get_user_rating_for_movie(db: Session, user_id: UUID, movie_id: UUID) -> Rating | None:
    """Get a user's rating for a specific movie."""
    return (
        db.query(Rating)
        .filter(Rating.user_id == user_id, Rating.movie_id == movie_id)
        .first()
    )


def get_user_ratings(db: Session, user_id: UUID) -> list[Rating]:
    """Get all ratings by a user."""
    return (
        db.query(Rating)
        .filter(Rating.user_id == user_id)
        .order_by(Rating.updated_at.desc())
        .all()
    )


def upsert_rating(db: Session, user_id: UUID, movie_id: UUID, rating_value: int) -> Rating:
    """
    Create or update a rating. If user already rated this movie, update it.
    """
    existing = get_user_rating_for_movie(db, user_id, movie_id)
    if existing:
        existing.rating = rating_value
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    new_rating = Rating(
        user_id=user_id,
        movie_id=movie_id,
        rating=rating_value,
    )
    db.add(new_rating)
    db.commit()
    db.refresh(new_rating)
    return new_rating
