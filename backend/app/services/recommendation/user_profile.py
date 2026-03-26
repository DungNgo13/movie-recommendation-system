"""
User Preference Profile Builder

Constructs a user preference vector by combining the TF-IDF movie vectors
of movies the user has interacted with, weighted by interaction type:

  WEIGHTING STRATEGY
  ──────────────────
  ┌──────────────┬────────┬─────────────────────────────────────────┐
  │ Signal       │ Weight │ Rationale                               │
  ├──────────────┼────────┼─────────────────────────────────────────┤
  │ Rating (5/5) │ 5.0    │ Strongest explicit signal; user loved   │
  │ Rating (4/5) │ 3.0    │ Strong positive signal                  │
  │ Rating (3/5) │ 1.0    │ Neutral, still some interest            │
  │ Rating (2/5) │ 0.0    │ Negative — excluded from profile        │
  │ Rating (1/5) │ 0.0    │ Negative — excluded from profile        │
  │ Favorite     │ 3.0    │ Strong explicit signal (≈ 4-star)       │
  │ Watch history│ 1.0    │ Weakest implicit signal                 │
  └──────────────┴────────┴─────────────────────────────────────────┘

  Ratings ≤ 2 are excluded entirely to avoid pulling the user profile
  toward disliked content. A movie may appear in multiple signals
  (e.g., favorited + rated); the maximum weight across all signals
  is used (no double-counting).

  The final user vector is the weighted average of movie vectors,
  then L2-normalized for cosine similarity compatibility.
"""

import numpy as np
from sqlalchemy.orm import Session
from uuid import UUID

from ..favorite_service import get_user_favorite_ids
from ..rating_service import get_user_ratings
from .vectorizer import get_movie_vectors
from ...models.watch_history import WatchHistory

# ─── Weight constants ─────────────────────────────────────────────
WEIGHT_FAVORITE = 3.0
WEIGHT_WATCH = 1.0

# Rating weights: index = rating value (1-5), 0 is unused
RATING_WEIGHTS = {
    1: 0.0,   # disliked → exclude
    2: 0.0,   # disliked → exclude
    3: 1.0,   # neutral
    4: 3.0,   # liked
    5: 5.0,   # loved
}


def _get_watched_movie_ids(db: Session, user_id: UUID) -> list[str]:
    """Get movie IDs from user's watch history."""
    rows = (
        db.query(WatchHistory.movie_id)
        .filter(WatchHistory.user_id == user_id)
        .all()
    )
    return [str(row.movie_id) for row in rows]


def build_user_profile(
    db: Session,
    user_id: UUID,
) -> np.ndarray | None:
    """
    Build a user preference vector from their interaction history.

    Returns:
        L2-normalized 1D numpy array (same dimension as movie vectors),
        or None if user has no interactions or no movies exist.
    """
    matrix, movie_ids = get_movie_vectors(db)
    if matrix is None or len(movie_ids) == 0:
        return None

    n_features = matrix.shape[1]

    # Build a movie_id → index lookup for fast access
    id_to_idx: dict[str, int] = {mid: i for i, mid in enumerate(movie_ids)}

    # Collect max weight per movie across all signals
    movie_weights: dict[str, float] = {}

    # 1. Ratings (strongest signal)
    ratings = get_user_ratings(db, user_id)
    for r in ratings:
        mid = str(r.movie_id)
        weight = RATING_WEIGHTS.get(r.rating, 0.0)
        if weight > 0 and mid in id_to_idx:
            movie_weights[mid] = max(movie_weights.get(mid, 0.0), weight)

    # 2. Favorites
    fav_ids = get_user_favorite_ids(db, user_id)
    for mid in fav_ids:
        if mid in id_to_idx:
            movie_weights[mid] = max(movie_weights.get(mid, 0.0), WEIGHT_FAVORITE)

    # 3. Watch history (weakest signal)
    watched_ids = _get_watched_movie_ids(db, user_id)
    for mid in watched_ids:
        if mid in id_to_idx:
            movie_weights[mid] = max(movie_weights.get(mid, 0.0), WEIGHT_WATCH)

    # No interactions → cold start
    if not movie_weights:
        return None

    # Compute weighted average of movie vectors
    user_vector = np.zeros(n_features, dtype=np.float64)
    total_weight = 0.0

    for mid, weight in movie_weights.items():
        idx = id_to_idx[mid]
        user_vector += weight * matrix[idx].toarray().flatten()
        total_weight += weight

    if total_weight == 0:
        return None

    user_vector /= total_weight

    # L2 normalize for cosine similarity compatibility
    norm = np.linalg.norm(user_vector)
    if norm > 0:
        user_vector /= norm

    return user_vector


def get_interaction_summary(db: Session, user_id: UUID) -> dict:
    """
    Returns a summary of user interactions for debugging/explanation.
    """
    ratings = get_user_ratings(db, user_id)
    fav_ids = get_user_favorite_ids(db, user_id)
    watched_ids = _get_watched_movie_ids(db, user_id)

    return {
        "ratings_count": len(ratings),
        "favorites_count": len(fav_ids),
        "watched_count": len(watched_ids),
        "has_profile": len(ratings) + len(fav_ids) + len(watched_ids) > 0,
    }
