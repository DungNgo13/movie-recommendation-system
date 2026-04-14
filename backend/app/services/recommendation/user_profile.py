"""
User Preference Profile Builder

Constructs a user preference vector by combining the TF-IDF movie vectors
of movies the user has interacted with, weighted by interaction type.

WEIGHTING STRATEGY
──────────────────
Explicit signals (user consciously expressed a preference):

  ┌──────────────┬────────┬─────────────────────────────────────────────┐
  │ Signal       │ Weight │ Rationale                                   │
  ├──────────────┼────────┼─────────────────────────────────────────────┤
  │ Rating (5/5) │  5.0   │ Strongest explicit signal; user loved it    │
  │ Rating (4/5) │  3.0   │ Strong positive signal                      │
  │ Rating (3/5) │  1.0   │ Neutral, still some interest                │
  │ Rating (2/5) │  0.0   │ Negative — excluded from profile            │
  │ Rating (1/5) │  0.0   │ Negative — excluded from profile            │
  │ Favorite     │  3.0   │ Strong explicit signal (≈ 4-star)           │
  └──────────────┴────────┴─────────────────────────────────────────────┘

Implicit signal — watch history (two-factor formula):

  base_weight = 1.0 + (progress_percent / 100) × 2.0
    → 0 % watched  →  1.0  (user opened the movie)
    → 50% watched  →  2.0  (user watched half)
    → 100% watched →  3.0  (user finished the movie)

  decay_factor = 1.0 / (1.0 + days_since_watched × 0.05)
    → watched today  →  1.00  (no decay)
    → watched 20 days ago  →  0.50  (half weight)
    → watched 40 days ago  →  0.33  (one-third weight)

  watch_weight = base_weight × decay_factor   (capped at 3.0)

General rules:
  - Ratings ≤ 2 are excluded to avoid pulling the profile toward disliked content.
  - A movie may produce signals from multiple sources (e.g. favorited AND rated);
    the maximum weight across all signals is kept — no double-counting.
  - The final user vector is the weighted average of movie TF-IDF vectors,
    then L2-normalized for cosine similarity compatibility.
"""

import math
from datetime import datetime, timezone

import numpy as np
from sqlalchemy.orm import Session
from uuid import UUID

from ..favorite_service import get_user_favorite_ids
from ..rating_service import get_user_ratings
from .vectorizer import get_movie_vectors
from ...models.watch_history import WatchHistory

# ─── Weight constants ──────────────────────────────────────────────────────────
WEIGHT_FAVORITE   = 3.0   # explicit: user saved the movie
WEIGHT_WATCH_MIN  = 1.0   # implicit base: user started the movie (0 % progress)
WEIGHT_WATCH_MAX  = 3.0   # implicit cap: prevents watch from outscoring 5-star

# Rating weights: key = rating value (1–5)
RATING_WEIGHTS = {
    1: 0.0,   # disliked → exclude
    2: 0.0,   # disliked → exclude
    3: 1.0,   # neutral
    4: 3.0,   # liked
    5: 5.0,   # loved
}

# Time-decay rate: 0.05 means 20 days ≈ half-weight, 40 days ≈ one-third weight.
# Easy to tune without touching anything else.
DECAY_RATE = 0.05


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _watch_weight(progress_percent: int | None, watched_at: datetime | None) -> float:
    """
    Compute the watch-event weight from two independent factors.

    Factor 1 — progress scaling (linear):
        base = 1.0 + (progress_percent / 100) * 2.0
        Range: 1.0 (started) … 3.0 (completed)

    Factor 2 — time decay (inverse linear):
        decay = 1.0 / (1.0 + days_since * DECAY_RATE)
        Range: 1.0 (today) → 0.5 (20 days ago) → 0.33 (40 days ago) …

    The two factors are multiplied and capped at WEIGHT_WATCH_MAX so a
    recently-finished film never outweighs an explicit 5-star rating.

    Pure Python + math — no extra libraries required.
    """
    # ── Factor 1: progress ────────────────────────────────────────────────────
    pct = max(0, min(100, progress_percent or 0))        # clamp 0–100
    base = WEIGHT_WATCH_MIN + (pct / 100.0) * 2.0       # 1.0 … 3.0

    # ── Factor 2: time decay ──────────────────────────────────────────────────
    if watched_at is not None:
        # Ensure both datetimes are timezone-aware for safe subtraction
        now = datetime.now(timezone.utc)
        if watched_at.tzinfo is None:
            watched_at = watched_at.replace(tzinfo=timezone.utc)
        days_since = max(0.0, (now - watched_at).total_seconds() / 86_400.0)
        decay = 1.0 / (1.0 + days_since * DECAY_RATE)
    else:
        decay = 1.0  # no timestamp → no decay applied

    raw = base * decay
    return min(raw, WEIGHT_WATCH_MAX)   # cap so implicit ≤ explicit ceiling


def _get_watch_records(db: Session, user_id: UUID) -> list[WatchHistory]:
    """
    Return full WatchHistory rows for the user so we can access
    progress_percent and watched_at alongside the movie_id.
    """
    return (
        db.query(WatchHistory)
        .filter(WatchHistory.user_id == user_id)
        .all()
    )


# ─── Public API ────────────────────────────────────────────────────────────────

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

    # Build a movie_id → matrix-row-index lookup for fast access
    id_to_idx: dict[str, int] = {mid: i for i, mid in enumerate(movie_ids)}

    # Collect the maximum weight per movie across all signal sources.
    # Taking the max (not the sum) prevents double-counting when a movie
    # appears in both watch history and ratings.
    movie_weights: dict[str, float] = {}

    # ── Signal 1: Star ratings (strongest explicit signal) ────────────────────
    ratings = get_user_ratings(db, user_id)
    for r in ratings:
        mid = str(r.movie_id)
        weight = RATING_WEIGHTS.get(r.rating, 0.0)
        if weight > 0 and mid in id_to_idx:
            movie_weights[mid] = max(movie_weights.get(mid, 0.0), weight)

    # ── Signal 2: Favorites (explicit binary signal) ───────────────────────────
    fav_ids = get_user_favorite_ids(db, user_id)
    for mid in fav_ids:
        if mid in id_to_idx:
            movie_weights[mid] = max(movie_weights.get(mid, 0.0), WEIGHT_FAVORITE)

    # ── Signal 3: Watch history (implicit — progress + time decay) ────────────
    # Each row carries progress_percent (0–100) and watched_at (datetime).
    # _watch_weight() converts those two values into a single float weight.
    watch_records = _get_watch_records(db, user_id)
    for record in watch_records:
        mid = str(record.movie_id)
        if mid not in id_to_idx:
            continue
        weight = _watch_weight(record.progress_percent, record.watched_at)
        movie_weights[mid] = max(movie_weights.get(mid, 0.0), weight)

    # Cold start: no interactions at all
    if not movie_weights:
        return None

    # ── Weighted average of movie content vectors ─────────────────────────────
    user_vector = np.zeros(n_features, dtype=np.float64)
    total_weight = 0.0

    for mid, weight in movie_weights.items():
        idx = id_to_idx[mid]
        user_vector += weight * matrix[idx].toarray().flatten()
        total_weight += weight

    if total_weight == 0:
        return None

    user_vector /= total_weight

    # ── L2 normalize for cosine similarity compatibility ──────────────────────
    norm = np.linalg.norm(user_vector)
    if norm > 0:
        user_vector /= norm

    return user_vector


def get_interaction_summary(db: Session, user_id: UUID) -> dict:
    """
    Returns a summary of user interactions used by the explainer layer.
    """
    ratings      = get_user_ratings(db, user_id)
    fav_ids      = get_user_favorite_ids(db, user_id)
    watch_records = _get_watch_records(db, user_id)

    return {
        "ratings_count":   len(ratings),
        "favorites_count": len(fav_ids),
        "watched_count":   len(watch_records),
        "has_profile":     len(ratings) + len(fav_ids) + len(watch_records) > 0,
    }
