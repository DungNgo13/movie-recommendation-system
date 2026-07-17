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

from .user_profile import build_user_profile, get_interaction_summary
from .vectorizer import get_movie_vectors, _candidate_query
from ..favorite_service import get_user_favorite_ids
from .explainer import generate_reason
from ...models.movie import Movie


def get_recommendations(
    db: Session,
    user_id: UUID,
    top_n: int = 10,
    exclude_interacted: bool = True,
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
        exclude_interacted: Whether to exclude already-favorited movies

    Returns:
        List of dicts: { id, title, poster_url, release_year, score, reason }
    """
    # Build user profile vector
    user_vector = build_user_profile(db, user_id)

    if user_vector is None:
        # Cold start → return popular/recent movies as fallback
        return _cold_start_fallback(db, top_n)

    # Get all movie vectors
    matrix, movie_ids = get_movie_vectors(db)
    if matrix is None:
        return []

    # Compute cosine similarity: user_vector vs all movie vectors
    scores = cosine_similarity(user_vector.reshape(1, -1), matrix).flatten()

    # Build exclusion set if needed
    exclude_ids: set[str] = set()
    if exclude_interacted:
        exclude_ids = set(get_user_favorite_ids(db, user_id))

    # Get interaction summary for explanation
    summary = get_interaction_summary(db, user_id)

    # Rank movies by score (descending), excluding interacted
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
    """
    movies = (
        _candidate_query(db)
        .order_by(Movie.release_date.desc())
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
            "reason": "Popular movie — rate or favorite some movies for personalized picks!",
        })
    return results

