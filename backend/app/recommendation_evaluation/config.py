"""
Configuration and frozen parameters for recommendation evaluation.

Freezes the exact algorithm parameters for baseline TFIDF-v1.0-as-is,
reproducing the production recommender behavior from:
  - backend/app/services/recommendation/movie_profile.py
  - backend/app/services/recommendation/vectorizer.py
  - backend/app/services/recommendation/user_profile.py
  - backend/app/services/recommendation/engine.py
"""

from dataclasses import dataclass, field
from typing import Literal
import hashlib
import json


@dataclass(frozen=True)
class TFIDFBaselineConfig:
    """
    Frozen configuration of the TFIDF-v1.0 recommendation engine.
    """
    # ── Algorithm Identity ──────────────────────────────────────────────
    algorithm_name: str = "TFIDF-v1.0-as-is"
    algorithm_version: str = "1.0.0"
    description: str = (
        "Production baseline: TF-IDF over concatenated movie metadata, "
        "interaction-weighted user profile vector, cosine similarity ranking. "
        "Preserves known defects R1 (train items not excluded) and R2 (negative ratings ignored)."
    )

    # ── TF-IDF Parameters (matching vectorizer.py) ──────────────────────
    max_features: int = 5000
    stop_words: str = "english"
    ngram_min: int = 1
    ngram_max: int = 2
    min_df: int = 1
    max_df: float = 0.95
    norm: str = "l2"
    use_idf: bool = True
    smooth_idf: bool = True
    sublinear_tf: bool = False

    # ── Content Repetition Weights (matching movie_profile.py) ──────────
    title_weight: int = 2
    keywords_weight: int = 2
    overview_weight: int = 1
    genres_weight: int = 1
    cast_weight: int = 1
    director_weight: int = 1

    # ── User Profile Signal Weights (matching user_profile.py) ──────────
    weight_rating_5: float = 5.0
    weight_rating_4: float = 3.0
    weight_rating_3: float = 1.0
    weight_rating_2: float = 0.0
    weight_rating_1: float = 0.0
    weight_favorite: float = 3.0
    weight_watch_min: float = 1.0
    weight_watch_max: float = 3.0
    watch_decay_rate: float = 0.05

    # ── Candidate & Exclusion Policies ──────────────────────────────────
    # In production v1.0, only favorites are excluded; rated/watched items are NOT (Defect R1).
    # Options: "none" (v1.0-as-is: no train exclusion), "train" (clean RecSys: exclude train items)
    exclude_seen_policy: Literal["none", "train"] = "none"

    # ── Evaluation Protocol ─────────────────────────────────────────────
    dataset_name: str = "MovieLens ml-latest-small"
    dataset_url: str = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
    relevance_threshold: float = 4.0
    k_values: tuple[int, ...] = (5, 10, 20)
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    min_user_interactions: int = 5
    random_seed: int = 42

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "algorithm_name": self.algorithm_name,
            "algorithm_version": self.algorithm_version,
            "description": self.description,
            "tfidf_params": {
                "max_features": self.max_features,
                "stop_words": self.stop_words,
                "ngram_range": [self.ngram_min, self.ngram_max],
                "min_df": self.min_df,
                "max_df": self.max_df,
                "norm": self.norm,
                "use_idf": self.use_idf,
                "smooth_idf": self.smooth_idf,
                "sublinear_tf": self.sublinear_tf,
            },
            "content_weights": {
                "title": self.title_weight,
                "keywords": self.keywords_weight,
                "overview": self.overview_weight,
                "genres": self.genres_weight,
                "cast": self.cast_weight,
                "director": self.director_weight,
            },
            "signal_weights": {
                "rating_5": self.weight_rating_5,
                "rating_4": self.weight_rating_4,
                "rating_3": self.weight_rating_3,
                "rating_2": self.weight_rating_2,
                "rating_1": self.weight_rating_1,
                "favorite": self.weight_favorite,
                "watch_min": self.weight_watch_min,
                "watch_max": self.weight_watch_max,
                "watch_decay_rate": self.watch_decay_rate,
            },
            "policies": {
                "exclude_seen_policy": self.exclude_seen_policy,
                "defect_r1_active": self.exclude_seen_policy == "none",
                "defect_r2_active": True,
            },
            "evaluation_protocol": {
                "dataset_name": self.dataset_name,
                "dataset_url": self.dataset_url,
                "relevance_threshold": self.relevance_threshold,
                "k_values": list(self.k_values),
                "split_ratios": {
                    "train": self.train_ratio,
                    "val": self.val_ratio,
                    "test": self.test_ratio,
                },
                "min_user_interactions": self.min_user_interactions,
                "random_seed": self.random_seed,
            },
        }

    def compute_checksum(self) -> str:
        """Compute SHA256 checksum of canonical configuration JSON."""
        canonical_json = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TFIDFV11Config:
    """
    Configuration for TF-IDF v1.1 Recommender Engine with Correctness Fixes:
      - R1: Seen-item exclusion (train interactions excluded from recommendations)
      - R2: Explicit negative feedback precedence (disliked ratings suppress positive signals)
      - R3: Deterministic cold-start fallback policy (NULL dates last, deterministic tie-breaking)
    """
    # ── Algorithm Identity ──────────────────────────────────────────────
    algorithm_name: str = "TFIDF-v1.1"
    algorithm_version: str = "1.1.0"
    description: str = (
        "TF-IDF v1.1: Content-based recommender with correctness fixes: "
        "R1 seen-item exclusion, R2 explicit negative feedback precedence, "
        "and R3 deterministic cold-start fallback."
    )

    # ── TF-IDF Parameters (matching vectorizer.py) ──────────────────────
    max_features: int = 5000
    stop_words: str = "english"
    ngram_min: int = 1
    ngram_max: int = 2
    min_df: int = 1
    max_df: float = 0.95
    norm: str = "l2"
    use_idf: bool = True
    smooth_idf: bool = True
    sublinear_tf: bool = False

    # ── Content Repetition Weights (matching movie_profile.py) ──────────
    title_weight: int = 2
    keywords_weight: int = 2
    overview_weight: int = 1
    genres_weight: int = 1
    cast_weight: int = 1
    director_weight: int = 1

    # ── User Profile Signal Weights (matching user_profile.py) ──────────
    weight_rating_5: float = 5.0
    weight_rating_4: float = 3.0
    weight_rating_3: float = 1.0
    weight_rating_2: float = 0.0
    weight_rating_1: float = 0.0
    weight_favorite: float = 3.0
    weight_watch_min: float = 1.0
    weight_watch_max: float = 3.0
    watch_decay_rate: float = 0.05

    # ── Correctness Policies (R1, R2, R3) ───────────────────────────────
    exclude_seen_policy: Literal["none", "train"] = "train"
    negative_feedback_policy: Literal["ignore", "suppress"] = "suppress"
    cold_start_policy: Literal["release_date_desc", "deterministic_v1_1"] = "deterministic_v1_1"

    # ── Evaluation Protocol ─────────────────────────────────────────────
    dataset_name: str = "MovieLens ml-latest-small"
    dataset_url: str = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
    relevance_threshold: float = 4.0
    k_values: tuple[int, ...] = (5, 10, 20)
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    min_user_interactions: int = 5
    random_seed: int = 42

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "algorithm_name": self.algorithm_name,
            "algorithm_version": self.algorithm_version,
            "description": self.description,
            "tfidf_params": {
                "max_features": self.max_features,
                "stop_words": self.stop_words,
                "ngram_range": [self.ngram_min, self.ngram_max],
                "min_df": self.min_df,
                "max_df": self.max_df,
                "norm": self.norm,
                "use_idf": self.use_idf,
                "smooth_idf": self.smooth_idf,
                "sublinear_tf": self.sublinear_tf,
            },
            "content_weights": {
                "title": self.title_weight,
                "keywords": self.keywords_weight,
                "overview": self.overview_weight,
                "genres": self.genres_weight,
                "cast": self.cast_weight,
                "director": self.director_weight,
            },
            "signal_weights": {
                "rating_5": self.weight_rating_5,
                "rating_4": self.weight_rating_4,
                "rating_3": self.weight_rating_3,
                "rating_2": self.weight_rating_2,
                "rating_1": self.weight_rating_1,
                "favorite": self.weight_favorite,
                "watch_min": self.weight_watch_min,
                "watch_max": self.weight_watch_max,
                "watch_decay_rate": self.watch_decay_rate,
            },
            "policies": {
                "exclude_seen_policy": self.exclude_seen_policy,
                "negative_feedback_policy": self.negative_feedback_policy,
                "cold_start_policy": self.cold_start_policy,
                "defect_r1_active": self.exclude_seen_policy == "none",
                "defect_r2_active": self.negative_feedback_policy == "ignore",
                "defect_r3_active": self.cold_start_policy == "release_date_desc",
            },
            "evaluation_protocol": {
                "dataset_name": self.dataset_name,
                "dataset_url": self.dataset_url,
                "relevance_threshold": self.relevance_threshold,
                "k_values": list(self.k_values),
                "split_ratios": {
                    "train": self.train_ratio,
                    "val": self.val_ratio,
                    "test": self.test_ratio,
                },
                "min_user_interactions": self.min_user_interactions,
                "random_seed": self.random_seed,
            },
        }

    def compute_checksum(self) -> str:
        """Compute SHA256 checksum of canonical configuration JSON."""
        canonical_json = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
