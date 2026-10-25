"""
Personalized Recommendation Engine

Uses cosine similarity between the user's preference vector and all movie
vectors to produce a ranked list of recommendations.

Handles cold-start by falling back to recently added movies.
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session
from uuid import UUID

from .user_profile import build_user_profile, get_interaction_summary, _get_watch_records
from .vectorizer import get_movie_vectors, _candidate_query
from ..favorite_service import get_user_favorite_ids
from ..rating_service import get_user_ratings
from .explainer import generate_reason
from ...models.movie import Movie

# ─── Configuration ────────────────────────────────────────────────────────────
# Minimum watch progress percent to consider a movie "consumed" for exclusion.
# Users who watched < 80% (previewed/abandoned) can still see the movie recommended.
WATCH_EXCLUSION_PROGRESS_THRESHOLD = 80


def get_user_excluded_movie_ids(
    db: Session,
    user_id: UUID,
    exclude_favorited: bool = True,
    exclude_rated: bool = True,
    exclude_watched: bool = True,
    watched_progress_threshold: int = WATCH_EXCLUSION_PROGRESS_THRESHOLD,
) -> set[str]:
    """
    Collect IDs of movies that should be excluded from recommendations (TF-IDF v1.1 - R1 Fix).

    Excludes:
      - Favorited movies (explicit user interest).
      - Explicitly rated movies (user has already watched and evaluated).
      - Substantially watched movies (progress >= watched_progress_threshold or is_completed=True).
        Movies merely clicked or previewed (< threshold) are NOT excluded.
    """
    exclude_ids: set[str] = set()

    if exclude_favorited:
        fav_ids = get_user_favorite_ids(db, user_id)
        exclude_ids.update(str(mid) for mid in fav_ids)

    if exclude_rated:
        ratings = get_user_ratings(db, user_id)
        exclude_ids.update(str(r.movie_id) for r in ratings)

    if exclude_watched:
        watch_records = _get_watch_records(db, user_id)
        for rec in watch_records:
            pct = rec.progress_percent or 0
            if getattr(rec, "is_completed", False) or pct >= watched_progress_threshold:
                exclude_ids.add(str(rec.movie_id))

    return exclude_ids


def get_recommendations(
    db: Session,
    user_id: UUID,
    top_n: int = 10,
    exclude_interacted: bool = True,
    exclude_rated: bool = True,
    exclude_watched: bool = True,
    watched_progress_threshold: int = WATCH_EXCLUSION_PROGRESS_THRESHOLD,
    suppress_negative: bool = True,
) -> list[dict]:
    """
    Generate personalized movie recommendations for a user.

    The candidate pool is determined by the RECOMMEND_ONLY_UPLOADED_MOVIES
    environment flag (see vectorizer.py).  When enabled, only movies with
    uploaded media are considered.

    Args:
        db: Database session
        user_id: Current user UUID
        top_n: Number of recommendations to return
        exclude_interacted: Master toggle to exclude seen movies
        exclude_rated: Exclude movies the user has rated (R1 fix)
        exclude_watched: Exclude movies the user watched >= threshold (R1 fix)
        watched_progress_threshold: Progress % for watch exclusion (default 80%)
        suppress_negative: Suppress positive signals from 1-2 star movies (R2 fix)

    Returns:
        List of dicts: { id, title, poster_url, release_year, score, reason }
    """
    # Build user profile vector
    user_vector = build_user_profile(db, user_id, suppress_negative=suppress_negative)

    if user_vector is None:
        # Cold start → return deterministic recent movies as fallback (R3 fix)
        return _cold_start_fallback(db, top_n)

    # Get all movie vectors
    matrix, movie_ids = get_movie_vectors(db)
    if matrix is None:
        return []

    # Compute cosine similarity: user_vector vs all movie vectors
    scores = cosine_similarity(user_vector.reshape(1, -1), matrix).flatten()

    # Build exclusion set (R1 Fix)
    exclude_ids: set[str] = set()
    if exclude_interacted:
        exclude_ids = get_user_excluded_movie_ids(
            db=db,
            user_id=user_id,
            exclude_favorited=True,
            exclude_rated=exclude_rated,
            exclude_watched=exclude_watched,
            watched_progress_threshold=watched_progress_threshold,
        )

    # Get interaction summary for explanation
    summary = get_interaction_summary(db, user_id)

    # Rank movies by score (descending), excluding seen items
    scored_movies: list[tuple[str, float]] = []
    for i, mid in enumerate(movie_ids):
        if mid not in exclude_ids:
            scored_movies.append((mid, float(scores[i])))

    scored_movies.sort(key=lambda x: x[1], reverse=True)
    top_movies = scored_movies[:top_n]

    # Pre-load all movies into a dict for fast lookup (avoids UUID/SQLite issues)
    all_movies = db.query(Movie).all()
    movie_map: dict[str, Movie] = {str(m.id): m for m in all_movies}

    # Fetch movie details and build response
    from ...schemas.movie import normalize_url
    results = []
    for mid, score in top_movies:
        movie = movie_map.get(mid)
        if movie is None:
            continue

        release_year = None
        if movie.release_date:
            release_year = movie.release_date.year

        results.append({
            "id": str(movie.id),
            "title": movie.title,
            "title_vi": getattr(movie, "title_vi", None),
            "poster_url": normalize_url(movie.poster_path),
            "release_year": release_year,
            "score": round(score, 4),
            "reason": generate_reason(summary, score),
        })

    return results


def _cold_start_fallback(db: Session, top_n: int) -> list[dict]:
    """
    Fallback for cold-start users: return the most recent movies
    from the candidate pool (respects RECOMMEND_ONLY_UPLOADED_MOVIES).

    TF-IDF v1.1 (R3 Fix):
      - Handles NULL release dates consistently across SQLite and PostgreSQL (NULLS LAST).
      - Deterministic tie-breaking on Movie.id ASC.
      - Accurate reason label ('Recently released movie').
    """
    movies = (
        _candidate_query(db)
        .order_by(Movie.release_date.desc().nulls_last(), Movie.id.asc())
        .limit(top_n)
        .all()
    )
    from ...schemas.movie import normalize_url
    results = []
    for movie in movies:
        release_year = None
        if movie.release_date:
            release_year = movie.release_date.year
        results.append({
            "id": str(movie.id),
            "title": movie.title,
            "title_vi": getattr(movie, "title_vi", None),
            "poster_url": normalize_url(movie.poster_path),
            "release_year": release_year,
            "score": 0.0,
            "reason": "Recently released movie — rate or favorite some movies for personalized picks!",
        })
    return results

