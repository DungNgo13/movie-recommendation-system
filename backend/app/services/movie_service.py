from typing import Optional

from sqlalchemy import extract, func
from sqlalchemy.orm import Session
from uuid import UUID
from ..models import movie as movie_model
from ..schemas.movie import MovieCreateSchema, MovieUpdateSchema
from .recommendation.vectorizer import invalidate_cache

def get_movie(db: Session, movie_id: UUID):
    """
    Fetches a single movie by its UUID.
    """
    return db.query(movie_model.Movie).filter(movie_model.Movie.id == movie_id).first()

def get_movies(
    db: Session,
    page: int = 1,
    limit: int = 100,
    search: Optional[str] = None,
    genre: Optional[str] = None,
    year: Optional[int] = None,
):
    """
    Fetches a paginated list of movies with optional server-side filters.

    Filters:
      - search: case-insensitive partial match on title (ILIKE).
      - genre:  exact genre name matched inside the JSON ``genres`` column.
      - year:   exact match on the year part of ``release_date``.
    """
    query = db.query(movie_model.Movie)

    if search:
        query = query.filter(
            movie_model.Movie.title.ilike(f"%{search}%")
        )

    if year is not None:
        query = query.filter(
            extract("year", movie_model.Movie.release_date) == year
        )

    if genre:
        # genres is a JSON list stored as ["Action", "Drama", ...].
        # Cast to text and do a case-insensitive contains check so it works
        # on both PostgreSQL (native JSON) and SQLite (text column in tests).
        from sqlalchemy import String
        query = query.filter(
            func.lower(
                func.cast(movie_model.Movie.genres, String)
            ).like(f'%"{genre.lower()}"%')
        )

    skip = (page - 1) * limit
    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return {"items": items, "total": total}

def create_movie(db: Session, movie_data: MovieCreateSchema):
    """
    Creates a new movie and invalidates the recommendation cache so the
    new movie is immediately eligible for recommendations.
    """
    db_movie = movie_model.Movie(
        title=movie_data.title,
        overview=movie_data.overview,
        release_date=movie_data.release_date,
        genres=movie_data.genres,
        cast=movie_data.cast,
        keywords=movie_data.keywords,
        director=movie_data.director,
    )
    db.add(db_movie)
    db.commit()
    db.refresh(db_movie)
    invalidate_cache()   # new movie → rebuild vectors on next request
    return db_movie

def update_movie(db: Session, movie_id: UUID, movie_data: MovieUpdateSchema):
    """
    Updates an existing movie. Invalidates the TF-IDF recommendation cache
    whenever metadata (title, overview, genres, cast, keywords, director)
    changes, so vectors are rebuilt on the next recommendation request.
    """
    db_movie = get_movie(db, movie_id)
    if db_movie is None:
        return None

    update_data = movie_data.model_dump(exclude_unset=True)
    # Ignore frontend virtual URL fields — they map to poster_path/backdrop_path
    # which are managed separately via the /poster and /backdrop upload endpoints.
    update_data.pop("poster_url", None)
    update_data.pop("backdrop_url", None)

    for field, value in update_data.items():
        if hasattr(db_movie, field):
            setattr(db_movie, field, value)

    db.commit()
    db.refresh(db_movie)

    # Any metadata edit may change the movie's content vector — always invalidate.
    invalidate_cache()
    return db_movie

def delete_movie(db: Session, movie_id: UUID):
    """
    Deletes a movie by its UUID. Invalidates the recommendation cache so the
    deleted movie is no longer returned by the engine.
    Returns True if deleted, False if not found.
    """
    db_movie = get_movie(db, movie_id)
    if db_movie is None:
        return False

    db.delete(db_movie)
    db.commit()
    invalidate_cache()   # removed movie → rebuild vectors on next request
    return True
