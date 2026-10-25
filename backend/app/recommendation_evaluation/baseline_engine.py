"""
Baseline TF-IDF Recommender Engine (TFIDF-v1.0-as-is).

Re-implements the production recommendation scoring and user profile builder
as a pure, standalone ML module independent of FastAPI and SQLAlchemy.

Reuses the exact mathematical logic from:
- backend/app/services/recommendation/movie_profile.py
- backend/app/services/recommendation/vectorizer.py
- backend/app/services/recommendation/user_profile.py
- backend/app/services/recommendation/engine.py
"""

from typing import Sequence, Literal
import numpy as np
from scipy.sparse import spmatrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import TFIDFBaselineConfig
from .dataset import MovieMetadata, RatingEvent


def map_rating_to_weight(rating: float) -> float:
    """
    Map an explicit star rating to a user profile weight.

    Production MovSug uses integer 1-5 ratings:
      5 -> 5.0
      4 -> 3.0
      3 -> 1.0
      1..2 -> 0.0

    For MovieLens half-star ratings, intervals map continuously:
      >= 4.5       -> 5.0 (Loved)
      >= 3.5 < 4.5 -> 3.0 (Liked)
      >= 2.5 < 3.5 -> 1.0 (Neutral)
      < 2.5        -> 0.0 (Disliked - excluded)
    """
    if rating >= 4.5:
        return 5.0
    elif rating >= 3.5:
        return 3.0
    elif rating >= 2.5:
        return 1.0
    else:
        return 0.0


class BaselineTFIDFRecommender:
    """
    Frozen TFIDF-v1.0-as-is Content-Based Recommender.
    """

    def __init__(self, config: TFIDFBaselineConfig | None = None):
        self.config = config or TFIDFBaselineConfig()
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix: spmatrix | None = None
        self.movie_ids: list[str] = []
        self.id_to_idx: dict[str, int] = {}
        self.n_features: int = 0
        self.item_vectors: dict[str, np.ndarray] = {}

    def fit(self, movies: dict[str, MovieMetadata]) -> "BaselineTFIDFRecommender":
        """
        Fit the TF-IDF vectorizer on movie text representations.
        """
        # Sort movie IDs for deterministic ordering
        self.movie_ids = sorted(movies.keys(), key=lambda x: int(x) if x.isdigit() else x)
        self.id_to_idx = {mid: i for i, mid in enumerate(self.movie_ids)}
        corpus = [movies[mid].text_profile for mid in self.movie_ids]

        if not corpus:
            self.vectorizer = None
            self.matrix = None
            self.n_features = 0
            self.item_vectors = {}
            return self

        max_df_val = self.config.max_df if len(corpus) >= 2 else 1.0

        self.vectorizer = TfidfVectorizer(
            max_features=self.config.max_features,
            stop_words=self.config.stop_words,
            ngram_range=(self.config.ngram_min, self.config.ngram_max),
            min_df=self.config.min_df,
            max_df=max_df_val,
            norm=self.config.norm,
            use_idf=self.config.use_idf,
            smooth_idf=self.config.smooth_idf,
            sublinear_tf=self.config.sublinear_tf,
        )
        self.matrix = self.vectorizer.fit_transform(corpus)
        self.n_features = self.matrix.shape[1]

        # Cache dense 1D vectors for diversity calculations
        self.item_vectors = {}
        for mid, idx in self.id_to_idx.items():
            self.item_vectors[mid] = self.matrix[idx].toarray().flatten()

        return self

    def build_user_vector(self, user_ratings: Sequence[RatingEvent]) -> np.ndarray | None:
        """
        Build an L2-normalized user preference vector from training interactions.
        Matches user_profile.py build_user_profile().
        """
        if self.matrix is None or not self.movie_ids:
            return None

        movie_weights: dict[str, float] = {}

        # Signal 1: star ratings (taking maximum if multiple interactions exist for the same movie)
        for r in user_ratings:
            mid = str(r.movie_id)
            if mid not in self.id_to_idx:
                continue
            weight = map_rating_to_weight(r.rating)
            if weight > 0:
                movie_weights[mid] = max(movie_weights.get(mid, 0.0), weight)

        # Cold start: no positive interactions in candidate pool
        if not movie_weights:
            return None

        # Weighted average of movie TF-IDF vectors
        user_vector = np.zeros(self.n_features, dtype=np.float64)
        total_weight = 0.0

        for mid, weight in movie_weights.items():
            idx = self.id_to_idx[mid]
            user_vector += weight * self.item_vectors[mid]
            total_weight += weight

        if total_weight == 0.0:
            return None

        user_vector /= total_weight

        # L2-normalize
        norm = float(np.linalg.norm(user_vector))
        if norm > 0:
            user_vector /= norm

        return user_vector

    def recommend(
        self,
        user_ratings: Sequence[RatingEvent],
        top_n: int = 20,
        exclude_seen: Literal["none", "train"] | None = None,
    ) -> list[tuple[str, float]]:
        """
        Generate ranked movie recommendations for a user.

        Args:
            user_ratings: Training interaction history of the user.
            top_n: Number of recommendations to return.
            exclude_seen:
                "none"  - (Baseline Defect R1): training items are NOT excluded.
                "train" - Standard RecSys evaluation: training items are excluded.
                Defaults to config.exclude_seen_policy.

        Returns:
            List of (movie_id, similarity_score) sorted descending by score.
        """
        policy = exclude_seen or self.config.exclude_seen_policy

        if self.matrix is None or not self.movie_ids:
            return []

        user_vector = self.build_user_vector(user_ratings)

        # Fallback for cold-start (no positive ratings)
        if user_vector is None:
            # Cold-start fallback: return first top_n items in catalog with score 0.0
            return [(mid, 0.0) for mid in self.movie_ids[:top_n]]

        # Compute cosine similarity
        scores = cosine_similarity(user_vector.reshape(1, -1), self.matrix).flatten()

        exclude_ids: set[str] = set()
        if policy == "train":
            exclude_ids = {str(r.movie_id) for r in user_ratings}

        scored_candidates: list[tuple[str, float]] = []
        for i, mid in enumerate(self.movie_ids):
            if mid not in exclude_ids:
                scored_candidates.append((mid, float(scores[i])))

        # Sort descending by score; break ties deterministically by movie_id
        scored_candidates.sort(
            key=lambda x: (-x[1], int(x[0]) if x[0].isdigit() else x[0])
        )

        return scored_candidates[:top_n]
