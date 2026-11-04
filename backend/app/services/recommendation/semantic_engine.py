"""
Semantic Embedding User-Profile Builder and Ranking Engine for Phase 8B.

Implements content-based semantic recommendation using precomputed, versioned
movie embedding artifacts while preserving the exact TF-IDF v1.1 interaction,
exclusion, negative-feedback, cold-start, and MMR policies:
  - Explicit rating weights: 5★ → 5.0, 4★ → 3.0, 3★ → 1.0, 1–2★ → 0.0
  - Favorites weight: 3.0
  - Watch history weight: progress [1.0..3.0] × recency decay (DECAY_RATE=0.05)
  - R2 negative-feedback suppression: 1–2★ ratings suppress positive signals
    from favorites and watch history for the same movie
  - R1 seen-item exclusion: favorited, rated, or watched >= 80% movies are
    excluded from recommendation lists
  - R3 deterministic cold-start fallback: release_date DESC NULLS LAST, id ASC
  - Optional MMR re-ranking over candidate embedding vectors

Safety & Fallback Guarantees:
  - Never downloads neural model weights or runs heavy transformer inference
    during a recommendation API request.
  - Automatically falls back to TF-IDF v1.1 (`None` return with fallback reason)
    and increments the fallback counter if the precomputed embedding artifact is
    missing, corrupted, or stale relative to the database catalog.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from ...models.movie import Movie
from ..favorite_service import get_user_favorite_ids
from ..rating_service import get_user_ratings
from .embedding_cache import (
    EmbeddingArtifact,
    check_cache_staleness,
    get_in_process_artifact,
    record_semantic_fallback,
)
from .user_profile import (
    RATING_WEIGHTS,
    WEIGHT_FAVORITE,
    _get_watch_records,
    _watch_weight,
)
from .vectorizer import _candidate_query

logger = logging.getLogger(__name__)

STRATEGY_TO_MODEL_KEY: dict[str, str] = {
    "semantic_en": "english_minilm",
    "english_minilm": "english_minilm",
    "semantic_multi": "multilingual_minilm",
    "multilingual_minilm": "multilingual_minilm",
    "deterministic_test": "deterministic_test",
}


def get_recommendation_strategy() -> str:
    """
    Read the configured recommendation strategy from ``RECOMMENDATION_STRATEGY``.
    Defaults safely to ``"tfidf_v1_1"``.
    """
    raw = os.getenv("RECOMMENDATION_STRATEGY", "tfidf_v1_1").strip().lower()
    if not raw:
        return "tfidf_v1_1"
    return raw


def compute_user_interaction_weights(
    db: Session,
    user_id: UUID,
    suppress_negative: bool = True,
) -> dict[str, float]:
    """
    Compute the unified per-movie interaction weights for ``user_id`` using the
    authoritative TF-IDF v1.1 interaction policy (with R2 negative suppression).
    """
    movie_weights: dict[str, float] = {}
    disliked_movie_ids: set[str] = set()

    ratings = get_user_ratings(db, user_id)
    for r in ratings:
        mid = str(r.movie_id)
        if suppress_negative and r.rating in (1, 2):
            disliked_movie_ids.add(mid)
            continue
        weight = RATING_WEIGHTS.get(r.rating, 0.0)
        if weight > 0:
            movie_weights[mid] = max(movie_weights.get(mid, 0.0), weight)

    favorite_ids = get_user_favorite_ids(db, user_id)
    for mid in favorite_ids:
        if mid in disliked_movie_ids:
            continue
        movie_weights[mid] = max(movie_weights.get(mid, 0.0), WEIGHT_FAVORITE)

    watch_records = _get_watch_records(db, user_id)
    for rec in watch_records:
        mid = str(rec.movie_id)
        if mid in disliked_movie_ids:
            continue
        w = _watch_weight(rec.progress_percent, rec.watched_at)
        if w > 0:
            movie_weights[mid] = max(movie_weights.get(mid, 0.0), w)

    return movie_weights


def build_semantic_user_profile(
    movie_weights: dict[str, float],
    artifact: EmbeddingArtifact,
    stale_movie_ids: set[str] | None = None,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    """
    Construct an L2-normalized semantic user preference vector from a user's
    positive ``movie_weights`` and a precomputed ``EmbeddingArtifact``.

    Gracefully skips movies with missing, zero, or stale embeddings and reports
    coverage diagnostics.
    """
    stale_set = stale_movie_ids or set()
    user_vector = np.zeros(artifact.dimensions, dtype=np.float64)
    total_weight = 0.0
    used_movies: list[str] = []
    skipped_missing: list[str] = []
    skipped_stale: list[str] = []

    for mid, weight in movie_weights.items():
        if weight <= 0:
            continue
        if mid in stale_set:
            skipped_stale.append(mid)
            continue
        vec = artifact.get_vector(mid)
        if vec is None:
            skipped_missing.append(mid)
            continue
        user_vector += float(weight) * vec.astype(np.float64)
        total_weight += float(weight)
        used_movies.append(mid)

    diagnostics = {
        "total_interacted_movies": len(movie_weights),
        "used_movies_count": len(used_movies),
        "skipped_missing_count": len(skipped_missing),
        "skipped_stale_count": len(skipped_stale),
        "total_weight": round(total_weight, 4),
    }

    if total_weight <= 0.0 or not used_movies:
        return None, diagnostics

    user_vector /= total_weight
    norm = float(np.linalg.norm(user_vector))
    if norm <= 1e-12:
        return None, diagnostics

    user_vector /= norm
    return user_vector.astype(np.float32), diagnostics


def rank_semantic_candidates(
    user_vector: np.ndarray,
    artifact: EmbeddingArtifact,
    candidate_movie_ids: list[str],
    exclude_ids: set[str],
    top_n: int = 10,
    stale_movie_ids: set[str] | None = None,
    mmr_enabled: bool = False,
    mmr_lambda: float = 0.5,
    mmr_pool_size: int = 100,
) -> tuple[list[tuple[str, float]], dict[str, Any]]:
    """
    Rank candidate movies by cosine similarity between ``user_vector`` and
    precomputed item embeddings in ``artifact``.

    Excludes seen items (`exclude_ids`), zero-vector items, and stale items
    (`stale_movie_ids`). Breaks ties deterministically by ``(-score, movie_id)``.
    Optionally applies MMR diversity re-ranking when ``mmr_enabled=True``.
    """
    stale_set = stale_movie_ids or set()
    zero_set = set(artifact.zero_vector_movie_ids)

    # Compute dot product / cosine similarity against all artifact vectors at once
    # (Both user_vector and non-zero artifact vectors are L2-normalized)
    u_vec = user_vector.astype(np.float32).reshape(-1)
    u_norm = float(np.linalg.norm(u_vec))
    if u_norm > 0 and abs(u_norm - 1.0) > 1e-5:
        u_vec = u_vec / u_norm

    all_scores = np.dot(artifact.vectors, u_vec)

    scored_candidates: list[tuple[str, float]] = []
    missing_candidates = 0
    stale_candidates = 0

    for mid in candidate_movie_ids:
        if mid in exclude_ids:
            continue
        if mid in stale_set:
            stale_candidates += 1
            continue
        idx = artifact.id_to_idx.get(mid)
        if idx is None or mid in zero_set:
            missing_candidates += 1
            continue
        vec_norm = float(np.linalg.norm(artifact.vectors[idx]))
        if vec_norm <= 1e-8:
            missing_candidates += 1
            continue
        score = float(all_scores[idx]) / (vec_norm if abs(vec_norm - 1.0) > 1e-4 else 1.0)
        scored_candidates.append((mid, score))

    # Deterministic tie-breaking: descending score, ascending movie_id (numeric when possible)
    scored_candidates.sort(
        key=lambda x: (-round(x[1], 12), (0, int(x[0])) if x[0].isdigit() else (1, x[0]))
    )

    if mmr_enabled and len(scored_candidates) > 0:
        from ...recommendation_evaluation.mmr import mmr_rerank

        pool_size = min(mmr_pool_size, len(scored_candidates))
        pool = scored_candidates[:pool_size]
        pool_ids = [mid for mid, _ in pool]
        pool_scores = [s for _, s in pool]
        item_vectors = {
            mid: artifact.vectors[artifact.id_to_idx[mid]].astype(np.float64)
            for mid in pool_ids
            if mid in artifact.id_to_idx
        }
        selected = mmr_rerank(
            candidate_ids=pool_ids,
            candidate_scores=pool_scores,
            item_vectors=item_vectors,
            select_n=top_n,
            lambda_param=mmr_lambda,
        )
    else:
        selected = scored_candidates[:top_n]

    total_cands = len(candidate_movie_ids)
    unusable = missing_candidates + stale_candidates
    stats = {
        "total_candidates": total_cands,
        "scored_candidates": len(scored_candidates),
        "missing_candidates": missing_candidates,
        "stale_candidates": stale_candidates,
        "missing_vector_rate": round(unusable / float(total_cands), 6) if total_cands > 0 else 0.0,
    }
    return selected, stats


def try_get_semantic_recommendations(
    db: Session,
    user_id: UUID,
    strategy: str,
    top_n: int,
    exclude_ids: set[str],
    suppress_negative: bool = True,
    mmr_enabled: bool = False,
    mmr_lambda: float = 0.5,
    mmr_pool_size: int = 100,
    cache_dir: Path | None = None,
) -> tuple[list[Movie] | None, dict[str, Any]]:
    """
    Attempt to serve recommendations using the configured semantic embedding
    strategy.

    If precomputed artifacts are missing, corrupted, or stale relative to the
    database catalog, increments the fallback counter and returns ``(None, info)``
    so the caller (`engine.py`) seamlessly falls back to TF-IDF v1.1.
    """
    model_key = STRATEGY_TO_MODEL_KEY.get(strategy)
    if not model_key:
        record_semantic_fallback()
        return None, {
            "fallback": True,
            "reason": f"Unknown semantic strategy '{strategy}'",
        }

    artifact = get_in_process_artifact(model_key=model_key, cache_dir=cache_dir)
    if artifact is None:
        record_semantic_fallback()
        return None, {
            "fallback": True,
            "reason": f"No precomputed embedding artifact found for model_key='{model_key}'",
        }

    candidate_movies = _candidate_query(db).order_by(Movie.id).all()
    if not candidate_movies:
        return [], {"fallback": False, "reason": "Empty candidate catalog"}

    staleness = check_cache_staleness(candidate_movies, artifact)
    if staleness["is_stale"]:
        record_semantic_fallback()
        return None, {
            "fallback": True,
            "reason": (
                f"Embedding cache is stale or incomplete "
                f"(stale={staleness['stale_count']}, missing={staleness['missing_count']})"
            ),
            "staleness": staleness,
        }

    movie_weights = compute_user_interaction_weights(
        db=db,
        user_id=user_id,
        suppress_negative=suppress_negative,
    )
    if not movie_weights:
        # Cold-start user: return None for profile so caller uses deterministic cold-start fallback
        return None, {
            "fallback": False,
            "is_cold_start": True,
            "reason": "User has no positive interactions",
        }

    user_vector, profile_diag = build_semantic_user_profile(
        movie_weights=movie_weights,
        artifact=artifact,
    )
    if user_vector is None:
        return None, {
            "fallback": False,
            "is_cold_start": True,
            "reason": "No interacted movies had valid vectors in artifact",
            "profile_diagnostics": profile_diag,
        }

    candidate_ids = [str(m.id) for m in candidate_movies]
    movie_map = {str(m.id): m for m in candidate_movies}

    top_scored, rank_stats = rank_semantic_candidates(
        user_vector=user_vector,
        artifact=artifact,
        candidate_movie_ids=candidate_ids,
        exclude_ids=exclude_ids,
        top_n=top_n,
        mmr_enabled=mmr_enabled,
        mmr_lambda=mmr_lambda,
        mmr_pool_size=mmr_pool_size,
    )

    movies_out = [movie_map[mid] for mid, _ in top_scored if mid in movie_map]
    return movies_out, {
        "fallback": False,
        "is_cold_start": False,
        "strategy": strategy,
        "model_key": model_key,
        "model_name": artifact.model_name,
        "model_revision": artifact.model_revision,
        "artifact_id": artifact.artifact_id,
        "profile_diagnostics": profile_diag,
        "ranking_stats": rank_stats,
        "top_scored": top_scored,
    }

