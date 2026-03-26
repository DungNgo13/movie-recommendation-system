"""
TF-IDF vectorizer for movie content.

Manages fitting the vectorizer on a movie corpus and transforming movies
into feature vectors. Includes a simple in-memory cache so we don't refit
on every request.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import spmatrix
from sqlalchemy.orm import Session
import numpy as np

from ...models.movie import Movie
from .movie_profile import build_movie_corpus

# ─── In-memory cache ─────────────────────────────────────────────
_cache: dict = {
    "vectorizer": None,       # fitted TfidfVectorizer
    "matrix": None,           # sparse TF-IDF matrix (n_movies × n_features)
    "movie_ids": [],           # list[str] parallel to matrix rows
    "movie_count": 0,          # number of movies at fit time
}


def _is_cache_valid(db: Session) -> bool:
    """Check if cache is still valid (same movie count)."""
    if _cache["vectorizer"] is None:
        return False
    current_count = db.query(Movie).count()
    return current_count == _cache["movie_count"]


def fit_vectorizer(db: Session) -> None:
    """
    Fit the TF-IDF vectorizer on all movies in the database.
    Stores the fitted vectorizer and matrix in the module-level cache.
    """
    movies = db.query(Movie).all()
    if not movies:
        _cache["vectorizer"] = None
        _cache["matrix"] = None
        _cache["movie_ids"] = []
        _cache["movie_count"] = 0
        return

    corpus = build_movie_corpus(movies)
    movie_ids = [str(m.id) for m in movies]

    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
    )
    matrix = vectorizer.fit_transform(corpus)

    _cache["vectorizer"] = vectorizer
    _cache["matrix"] = matrix
    _cache["movie_ids"] = movie_ids
    _cache["movie_count"] = len(movies)


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
    """Force cache invalidation (e.g., after adding/deleting movies)."""
    _cache["vectorizer"] = None
    _cache["matrix"] = None
    _cache["movie_ids"] = []
    _cache["movie_count"] = 0
