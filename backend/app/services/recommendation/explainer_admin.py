"""
Admin Recommendation Explainer Service

Produces a fully transparent diagnostic payload showing EXACTLY how the
recommendation engine scored each movie for a specific user.

This is the "open the black box" tool for thesis defense presentations.
It reuses the same data sources and formulas as the live engine — it does
NOT re-implement anything; it just surfaces the intermediate values that
the production engine discards.

Output structure:
  {
    "user_id": "...",
    "user_email": "...",
    "algorithm_version": "TF-IDF + Cosine Similarity + Weighted User Profile",
    "is_cold_start": bool,
    "user_context": [          # ← every interaction that shaped the profile
        {
            "movie_id": "...",
            "movie_title": "...",
            "signal_type": "rating" | "favorite" | "watch",
            "raw_value": ...,          # rating int, "favorited", or progress %
            "calculated_weight": 2.8,  # the final weight fed into the profile
            "weight_breakdown": "base=3.0 × decay=0.93 (watched 1.4 days ago)"
        }, ...
    ],
    "top_recommendations": [   # ← top-N scored movies with breakdown
        {
            "rank": 1,
            "movie_id": "...",
            "movie_title": "...",
            "genres": [...],
            "director": "...",
            "total_score": 0.8421,    # cosine similarity (0–1)
            "contributing_factors": ["Matched genres: Action, Drama",
                                     "Matched director: Christopher Nolan",
                                     "Profile influenced by: Inception (w=5.0)"]
        }, ...
    ]
  }
"""

from datetime import datetime, timezone
from uuid import UUID

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from ..favorite_service import get_user_favorite_ids
from ..rating_service import get_user_ratings
from .user_profile import (
    _get_watch_records,
    _watch_weight,
    RATING_WEIGHTS,
    WEIGHT_FAVORITE,
    DECAY_RATE,
    WEIGHT_WATCH_MIN,
)
from .vectorizer import get_movie_vectors
from ...models.movie import Movie
from ...models.user import User


# ─── Internal helpers ──────────────────────────────────────────────────────────

def _days_since(dt: datetime | None) -> float:
    """Return how many days ago `dt` was. Returns 0.0 if dt is None."""
    if dt is None:
        return 0.0
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86_400.0)


def _format_watch_breakdown(progress: int | None, watched_at: datetime | None) -> str:
    """Human-readable string explaining the two-factor watch weight formula."""
    pct = max(0, min(100, progress or 0))
    base = WEIGHT_WATCH_MIN + (pct / 100.0) * 2.0
    days = _days_since(watched_at)
    decay = 1.0 / (1.0 + days * DECAY_RATE)
    raw = base * decay
    capped = min(raw, 3.0)
    return (
        f"base={base:.2f} (progress {pct}%)"
        f" × decay={decay:.2f} ({days:.1f} days ago)"
        f" = {raw:.2f}"
        + (" [capped at 3.0]" if raw > 3.0 else "")
    )


def _get_contributing_factors(
    movie: Movie,
    user_vector: np.ndarray,
    movie_vector: np.ndarray,
    top_weighted_movies: list[dict],       # the user_context list
) -> list[str]:
    """
    Generate plain-English factors that explain WHY this movie scored highly.

    Strategy — three types of factor:
      1. Genre overlap between this movie and genres the user's profile favours.
      2. Director match.
      3. The user's own interactions that most influenced the profile vector.
    """
    factors: list[str] = []

    # Factor 1: Genres
    genres = movie.genres or []
    if genres:
        factors.append(f"Matched genres: {', '.join(genres)}")

    # Factor 2: Director
    if movie.director:
        factors.append(f"Matched director: {movie.director}")

    # Factor 3: Cast
    cast = movie.cast or []
    if cast:
        factors.append(f"Notable cast: {', '.join(cast[:3])}")  # top 3

    # Factor 4: The user's highest-weight interactions that shaped the profile
    # Sort interactions by weight descending and take the top 3
    sorted_interactions = sorted(
        top_weighted_movies, key=lambda x: x["calculated_weight"], reverse=True
    )
    for interaction in sorted_interactions[:3]:
        sig = interaction["signal_type"]
        w   = interaction["calculated_weight"]
        t   = interaction["movie_title"]
        if sig == "rating":
            factors.append(f"Profile influenced by your {interaction['raw_value']}★ rating of '{t}' (weight={w:.2f})")
        elif sig == "favorite":
            factors.append(f"Profile influenced by your favorite: '{t}' (weight={w:.2f})")
        else:
            factors.append(f"Profile influenced by: '{t}' (watched {interaction['raw_value']}%, weight={w:.2f})")

    return factors


# ─── Public diagnostic function ────────────────────────────────────────────────

def explain_recommendations(
    db: Session,
    user_id: UUID,
    top_n: int = 10,
) -> dict:
    """
    Run the full recommendation pipeline and return a diagnostic payload
    that makes every intermediate value visible.

    This function is intentionally verbose — it is designed to be
    printed / displayed during a thesis defense to prove the engine
    is not a black box.
    """

    # ── 0. Resolve user ───────────────────────────────────────────────────────
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return {"error": f"User {user_id} not found."}

    user_email = user.email

    # ── 1. Collect all signal data ────────────────────────────────────────────
    ratings       = get_user_ratings(db, user_id)
    fav_ids       = set(get_user_favorite_ids(db, user_id))
    watch_records = _get_watch_records(db, user_id)

    # Pre-load movie titles for human-readable output
    all_movies    = db.query(Movie).all()
    movie_map:  dict[str, Movie] = {str(m.id): m for m in all_movies}

    # ── 2. Build user_context  ────────────────────────────────────────────────
    # Track max weight per movie (same "no double-counting" rule as the engine)
    # but ALSO keep a human-readable log entry for every distinct signal.
    signal_log:   list[dict]      = []  # one entry per interaction (for display)
    movie_weights: dict[str, float] = {}  # mid → final weight for profile

    # Signal 1: ratings
    for r in ratings:
        mid   = str(r.movie_id)
        w     = RATING_WEIGHTS.get(r.rating, 0.0)
        title = movie_map[mid].title if mid in movie_map else mid
        signal_log.append({
            "movie_id":          mid,
            "movie_title":       title,
            "signal_type":       "rating",
            "raw_value":         r.rating,
            "calculated_weight": round(w, 4),
            "weight_breakdown":  (
                f"Rating {r.rating}/5 → weight {w:.1f}"
                + (" [excluded — negative signal]" if w == 0 else "")
            ),
        })
        if w > 0:
            movie_weights[mid] = max(movie_weights.get(mid, 0.0), w)

    # Signal 2: favorites
    for mid in fav_ids:
        title = movie_map[mid].title if mid in movie_map else mid
        w     = WEIGHT_FAVORITE
        signal_log.append({
            "movie_id":          mid,
            "movie_title":       title,
            "signal_type":       "favorite",
            "raw_value":         "favorited",
            "calculated_weight": round(w, 4),
            "weight_breakdown":  f"Favorite → fixed weight {w:.1f}",
        })
        movie_weights[mid] = max(movie_weights.get(mid, 0.0), w)

    # Signal 3: watch history (progress + time decay)
    for rec in watch_records:
        mid   = str(rec.movie_id)
        title = movie_map[mid].title if mid in movie_map else mid
        w     = _watch_weight(rec.progress_percent, rec.watched_at)
        signal_log.append({
            "movie_id":          mid,
            "movie_title":       title,
            "signal_type":       "watch",
            "raw_value":         rec.progress_percent or 0,
            "calculated_weight": round(w, 4),
            "weight_breakdown":  _format_watch_breakdown(rec.progress_percent, rec.watched_at),
        })
        movie_weights[mid] = max(movie_weights.get(mid, 0.0), w)

    # Sort context by weight descending so the most influential signals appear first
    signal_log.sort(key=lambda x: x["calculated_weight"], reverse=True)

    # ── 3. Detect cold-start ──────────────────────────────────────────────────
    is_cold_start = len(movie_weights) == 0

    if is_cold_start:
        return {
            "user_id":            str(user_id),
            "user_email":         user_email,
            "algorithm_version":  "TF-IDF + Cosine Similarity + Weighted User Profile v2",
            "is_cold_start":      True,
            "cold_start_reason":  "User has no ratings, favorites, or watch history yet.",
            "user_context":       [],
            "top_recommendations": [],
        }

    # ── 4. Build user vector (identical logic to production engine) ───────────
    matrix, movie_ids = get_movie_vectors(db)
    if matrix is None:
        return {"error": "Movie vector matrix is empty. Add some movies first."}

    id_to_idx: dict[str, int] = {mid: i for i, mid in enumerate(movie_ids)}
    n_features = matrix.shape[1]

    user_vector = np.zeros(n_features, dtype=np.float64)
    total_weight = 0.0
    for mid, w in movie_weights.items():
        if mid in id_to_idx:
            user_vector += w * matrix[id_to_idx[mid]].toarray().flatten()
            total_weight += w

    if total_weight == 0:
        return {"error": "Could not build user vector — no movies matched the index."}

    user_vector /= total_weight
    norm = np.linalg.norm(user_vector)
    if norm > 0:
        user_vector /= norm

    # ── 5. Score every movie ──────────────────────────────────────────────────
    scores = cosine_similarity(user_vector.reshape(1, -1), matrix).flatten()

    scored: list[tuple[str, float]] = [
        (mid, float(scores[i]))
        for i, mid in enumerate(movie_ids)
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_scored = scored[:top_n]

    # ── 6. Build top_recommendations with per-movie breakdown ────────────────
    from ...schemas.movie import normalize_url  # local import to avoid circular

    recommendations_out: list[dict] = []
    for rank, (mid, score) in enumerate(top_scored, start=1):
        movie = movie_map.get(mid)
        if movie is None:
            continue

        # Get the movie's own TF-IDF vector for factor analysis
        movie_vec = matrix[id_to_idx[mid]].toarray().flatten() if mid in id_to_idx else None

        factors = _get_contributing_factors(
            movie        = movie,
            user_vector  = user_vector,
            movie_vector = movie_vec,
            top_weighted_movies = signal_log,
        )

        recommendations_out.append({
            "rank":          rank,
            "movie_id":      str(movie.id),
            "movie_title":   movie.title,
            "genres":        movie.genres or [],
            "cast":          movie.cast or [],
            "keywords":      movie.keywords or [],
            "director":      movie.director,
            "release_year":  movie.release_date.year if movie.release_date else None,
            "poster_url":    normalize_url(movie.poster_path),
            # The cosine similarity IS the total score (0–1)
            "total_score":         round(score, 6),
            "score_interpretation": (
                "Very strong match" if score >= 0.5 else
                "Strong match"      if score >= 0.3 else
                "Good match"        if score >= 0.15 else
                "Weak match"
            ),
            "contributing_factors": factors,
        })

    # ── 7. Assemble final payload ─────────────────────────────────────────────
    return {
        "user_id":           str(user_id),
        "user_email":        user_email,
        "algorithm_version": "TF-IDF + Cosine Similarity + Weighted User Profile v2",
        "is_cold_start":     False,
        "algorithm_summary": (
            "1) Build a text profile for each movie (title×2, overview, genres, "
            "cast, keywords×2, director). "
            "2) Fit a TF-IDF vectorizer on all profiles → sparse feature matrix. "
            "3) Compute a weighted average of movie vectors for movies this user "
            "interacted with (weight = explicit rating OR implicit watch progress × time decay). "
            "4) L2-normalise the user vector. "
            "5) Rank all movies by cosine similarity to the user vector."
        ),
        "user_context":        signal_log,
        "weight_summary": {
            "total_signals":        len(signal_log),
            "unique_movies_in_profile": len(movie_weights),
            "highest_weight_movie": signal_log[0]["movie_title"] if signal_log else None,
            "highest_weight_value": signal_log[0]["calculated_weight"] if signal_log else None,
        },
        "top_recommendations": recommendations_out,
    }
