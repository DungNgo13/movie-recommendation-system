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

def _normalize_ws(s: str) -> str:
    """Trim and collapse internal whitespace for safe comparison."""
    import re
    return re.sub(r"\s+", " ", s.strip())


def get_movies(
    db: Session,
    page: int = 1,
    limit: int = 100,
    search: Optional[str] = None,
    genre: Optional[str] = None,
    year: Optional[int] = None,
    director: Optional[str] = None,
    cast_member: Optional[str] = None,
    keyword: Optional[str] = None,
    exclude_id: Optional[UUID] = None,
):
    """
    Fetches a paginated list of movies with optional server-side filters.

    Filters:
      - search:      case-insensitive partial match on title (ILIKE).
      - genre:       exact genre name matched inside the JSON ``genres`` column.
      - year:        exact match on the year part of ``release_date``.
      - director:    exact, case-insensitive, whitespace-normalized director match.
      - cast_member: exact array-item match inside the JSON ``cast`` column.
      - keyword:     exact array-item match inside the JSON ``keywords`` column.
                     A leading ``#`` is stripped automatically.
      - exclude_id:  UUID of a movie to omit from results (e.g. the current movie).
    """
    from sqlalchemy import String

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
        query = query.filter(
            func.lower(
                func.cast(movie_model.Movie.genres, String)
            ).like(f'%"{genre.lower()}"%')
        )

    if director:
        # Exact, case-insensitive, whitespace-normalized director match.
        # director is a plain String column, so lower() works on all backends.
        norm_dir = _normalize_ws(director).lower()
        query = query.filter(
            func.lower(func.trim(movie_model.Movie.director)) == norm_dir
        )

    if cast_member:
        # Pre-filter at DB level using JSON-as-text LIKE (same as genre).
        # Post-filter below ensures exact array-item match.
        norm_cast = _normalize_ws(cast_member).lower()
        query = query.filter(
            func.lower(
                func.cast(movie_model.Movie.cast, String)
            ).like(f'%"{norm_cast}"%')
        )

    if keyword:
        # Strip optional leading '#' and normalize.
        norm_kw = _normalize_ws(keyword.lstrip("#")).lower()
        if norm_kw:
            query = query.filter(
                func.lower(
                    func.cast(movie_model.Movie.keywords, String)
                ).like(f'%"{norm_kw}"%')
            )

    if exclude_id is not None:
        query = query.filter(movie_model.Movie.id != exclude_id)

    skip = (page - 1) * limit
    total_before_post = query.count()
    items = query.offset(skip).limit(limit).all()

    # ── Post-query exact-item filtering for JSON arrays ──────────────
    # The DB LIKE filter may produce false positives (e.g. "Camera" matching
    # "Drone Camera" via substring). Post-filter ensures each match is an
    # exact array item after normalization.
    if cast_member:
        norm_cast = _normalize_ws(cast_member).lower()
        filtered = []
        for m in items:
            arr = m.cast if isinstance(m.cast, list) else []
            if any(_normalize_ws(c).lower() == norm_cast for c in arr):
                filtered.append(m)
        items = filtered
        total_before_post = len(items)  # recalculate for post-filtered set

    if keyword:
        norm_kw = _normalize_ws(keyword.lstrip("#")).lower()
        if norm_kw:
            filtered = []
            for m in items:
                arr = m.keywords if isinstance(m.keywords, list) else []
                if any(_normalize_ws(k).lower() == norm_kw for k in arr):
                    filtered.append(m)
            items = filtered
            total_before_post = len(items)

    return {"items": items, "total": total_before_post}

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

    # Source & license fields — only set if provided (model defaults apply otherwise)
    if movie_data.source_name is not None:
        db_movie.source_name = movie_data.source_name
    if movie_data.source_url is not None:
        db_movie.source_url = movie_data.source_url
    if movie_data.license_type is not None:
        db_movie.license_type = movie_data.license_type
    if movie_data.license_url is not None:
        db_movie.license_url = movie_data.license_url
    if movie_data.attribution is not None:
        db_movie.attribution = movie_data.attribution
    if movie_data.is_public_domain is not None:
        db_movie.is_public_domain = movie_data.is_public_domain
    if movie_data.media_rights_status is not None:
        db_movie.media_rights_status = movie_data.media_rights_status

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
