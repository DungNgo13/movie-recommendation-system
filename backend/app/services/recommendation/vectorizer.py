"""
TF-IDF vectorizer for movie content.

Manages fitting the vectorizer on a movie corpus and transforming movies
into feature vectors. Includes a simple in-memory cache so we don't refit
on every request.

Candidate Pool
──────────────
When RECOMMEND_ONLY_UPLOADED_MOVIES=true (default for production), only
movies with uploaded media are included in the recommendation candidate
pool.  This ensures the AI recommends movies that actually exist in the
website catalog — not empty placeholder entries.

A movie is considered "uploaded" if ANY of these conditions hold:
  - video_source_path IS NOT NULL
  - hls_playlist_path IS NOT NULL
  - processing_status = "ready"
"""

import os
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import spmatrix
from sqlalchemy.orm import Session
from sqlalchemy import or_
import numpy as np

from ...models.movie import Movie
from .movie_profile import build_movie_corpus


# ─── Configuration ────────────────────────────────────────────────────────────

def _should_filter_uploaded_only() -> bool:
    """Read the RECOMMEND_ONLY_UPLOADED_MOVIES env flag (default: true)."""
    raw = os.getenv("RECOMMEND_ONLY_UPLOADED_MOVIES", "true").strip().lower()
    return raw in ("true", "1", "yes")


def _candidate_query(db: Session):
    """
    Return a SQLAlchemy query for the candidate movie pool.

    When the filter is active, only movies with uploaded video
    (or fully processed HLS) are included.  When the filter is off,
    all movies in the catalog are candidates.
    """
    query = db.query(Movie)
    if _should_filter_uploaded_only():
        query = query.filter(
            or_(
                Movie.video_source_path.isnot(None),
                Movie.hls_playlist_path.isnot(None),
                Movie.processing_status == "ready",
            )
        )
    return query


# ─── In-memory cache ─────────────────────────────────────────────
# Cache Lifecycle & Synchronization:
# 1. What is cached:
#    - Fitted TfidfVectorizer, sparse TF-IDF document-term matrix, parallel
#      movie_ids list, movie_count, and filter_flag.
# 2. When it is invalidated (`invalidate_cache()`):
#    - After movie creation, update, or deletion in `movie_service.py`
#    - After approved metadata enrichment application in `metadata_application_service.py`
#    - After HLS conversion transitions a movie to `processing_status = "ready"`
# 3. When it is rebuilt (`fit_vectorizer(db)` / `refresh_cache(db)`):
#    - Lazily on the next call to `get_movie_vectors(db)` or `get_movie_vector_by_id(db, id)`
#      when `_is_cache_valid(db)` returns False, or eagerly via `refresh_cache(db)`.
_cache: dict = {
    "vectorizer": None,       # fitted TfidfVectorizer
    "matrix": None,           # sparse TF-IDF matrix (n_movies × n_features)
    "movie_ids": [],          # list[str] parallel to matrix rows
    "movie_count": 0,         # number of movies at fit time
    "filter_flag": None,      # the flag value used at fit time
    "cache_generation": 0,    # increments each time fit_vectorizer completes
    "invalidation_count": 0,  # increments each time invalidate_cache is called
    "refresh_count": 0,       # increments each time refresh_cache succeeds
    "last_refreshed_at": None,# UTC ISO timestamp of last fit
}


def _is_cache_valid(db: Session) -> bool:
    """Check if cache is still valid (same movie count AND same filter flag)."""
    if _cache["vectorizer"] is None:
        return False
    current_flag = _should_filter_uploaded_only()
    if current_flag != _cache["filter_flag"]:
        return False
    current_count = _candidate_query(db).count()
    return current_count == _cache["movie_count"]


def fit_vectorizer(db: Session) -> None:
    """
    Fit the TF-IDF vectorizer on the candidate movie pool.
    Stores the fitted vectorizer and matrix in the module-level cache.
    """
    movies = _candidate_query(db).all()
    current_flag = _should_filter_uploaded_only()

    if not movies:
        _cache["vectorizer"] = None
        _cache["matrix"] = None
        _cache["movie_ids"] = []
        _cache["movie_count"] = 0
        _cache["filter_flag"] = current_flag
        _cache["cache_generation"] = _cache.get("cache_generation", 0) + 1
        _cache["last_refreshed_at"] = datetime.now(timezone.utc).isoformat()
        return

    corpus = build_movie_corpus(movies)
    movie_ids = [str(m.id) for m in movies]

    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        # max_df=0.95 requires at least 2 documents; when the corpus is
        # tiny (e.g. only 1 uploaded movie), set max_df=1.0 to avoid
        # sklearn's "max_df corresponds to < documents than min_df" error.
        max_df=0.95 if len(corpus) >= 2 else 1.0,
    )
    matrix = vectorizer.fit_transform(corpus)

    _cache["vectorizer"] = vectorizer
    _cache["matrix"] = matrix
    _cache["movie_ids"] = movie_ids
    _cache["movie_count"] = len(movies)
    _cache["filter_flag"] = current_flag
    _cache["cache_generation"] = _cache.get("cache_generation", 0) + 1
    _cache["last_refreshed_at"] = datetime.now(timezone.utc).isoformat()


def get_movie_vectors(db: Session) -> tuple[spmatrix, list[str]]:
    """
    Get the TF-IDF matrix and corresponding movie IDs.
    Fits the vectorizer if cache is stale or empty.
    
    Returns:
        (matrix, movie_ids) where matrix[i] is the vector for movie_ids[i]
    """
    if not _is_cache_valid(db):
        fit_vectorizer(db)

    return _cache["matrix"], _cache["movie_ids"]


def get_movie_vector_by_id(db: Session, movie_id: str) -> np.ndarray | None:
    """
    Get the TF-IDF vector for a specific movie by its ID.
    
    Returns:
        1D numpy array, or None if movie not found in the index.
    """
    matrix, movie_ids = get_movie_vectors(db)
    if matrix is None:
        return None

    try:
        idx = movie_ids.index(movie_id)
    except ValueError:
        return None

    return matrix[idx].toarray().flatten()


def invalidate_cache() -> None:
    """Force cache invalidation (e.g., after adding/deleting/enriching movies)."""
    _cache["vectorizer"] = None
    _cache["matrix"] = None
    _cache["movie_ids"] = []
    _cache["movie_count"] = 0
    _cache["filter_flag"] = None
    _cache["invalidation_count"] = _cache.get("invalidation_count", 0) + 1
    try:
        from .embedding_cache import invalidate_embedding_cache
        invalidate_embedding_cache()
    except Exception:
        pass


def refresh_cache(db: Session) -> bool:
    """
    Invalidate and immediately refit the TF-IDF vectorizer cache on the current
    database state. Returns True if refresh succeeded without raising errors.
    """
    invalidate_cache()
    fit_vectorizer(db)
    _cache["refresh_count"] = _cache.get("refresh_count", 0) + 1
    return True


def get_cache_stats() -> dict:
    """Return non-sensitive diagnostic counters for the TF-IDF cache."""
    return {
        "is_populated": _cache["vectorizer"] is not None,
        "movie_count": _cache["movie_count"],
        "filter_flag": _cache["filter_flag"],
        "cache_generation": _cache.get("cache_generation", 0),
        "invalidation_count": _cache.get("invalidation_count", 0),
        "refresh_count": _cache.get("refresh_count", 0),
        "last_refreshed_at": _cache.get("last_refreshed_at"),
    }
