from sqlalchemy.orm import Session
from uuid import UUID
from ..models.user_favorite import UserFavorite
from ..models.movie import Movie


def get_user_favorites(db: Session, user_id: UUID) -> list[dict]:
    """Get all favorite movies for a user with movie details."""
    favorites = (
        db.query(Movie)
        .join(UserFavorite, UserFavorite.movie_id == Movie.id)
        .filter(UserFavorite.user_id == user_id)
        .all()
    )
    from ..schemas.movie import normalize_url
    results_list = []
    for movie in favorites:
        release_year = None
        if movie.release_date:
            release_year = movie.release_date.year
        results_list.append({
            "id": movie.id,
            "title": movie.title,
            "poster_url": normalize_url(movie.poster_path),
            "release_year": release_year,
        })
    return results_list


def get_user_favorite_ids(db: Session, user_id: UUID) -> list[str]:
    """Get just the movie IDs that a user has favorited."""
    rows = (
        db.query(UserFavorite.movie_id)
        .filter(UserFavorite.user_id == user_id)
        .all()
    )
    return [str(row.movie_id) for row in rows]


def add_favorite(db: Session, user_id: UUID, movie_id: UUID) -> bool:
    """Add a movie to favorites. Returns True if added, False if already exists."""
    existing = (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == user_id, UserFavorite.movie_id == movie_id)
        .first()
    )
    if existing:
        return False

    fav = UserFavorite(user_id=user_id, movie_id=movie_id)
    db.add(fav)
    db.commit()
    return True


def remove_favorite(db: Session, user_id: UUID, movie_id: UUID) -> bool:
    """Remove a movie from favorites. Returns True if removed, False if not found."""
    fav = (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == user_id, UserFavorite.movie_id == movie_id)
        .first()
    )
    if not fav:
        return False

    db.delete(fav)
    db.commit()
    return True
