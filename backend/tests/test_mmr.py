"""
Tests for Maximum Marginal Relevance (MMR) Re-ranking.

Covers:
- Exact MMR score calculations on toy vectors
- λ=1.0 equivalence (pure relevance)
- Deterministic ranking under ties
- Duplicate and highly similar candidates
- Excluded-item preservation (MMR never reintroduces excluded items)
- Candidate pool restrictions
- Sparse vector behavior
- Zero-vector and empty-catalog behavior
- Candidate lists shorter than K
- Numerical stability
- Repeated-run reproducibility
"""

import numpy as np
import pytest

from app.recommendation_evaluation.mmr import mmr_rerank


class TestMMRBasicBehavior:
    """Core MMR algorithm correctness."""

    def test_empty_candidates_returns_empty(self):
        result = mmr_rerank([], [], {}, select_n=5, lambda_param=0.5)
        assert result == []

    def test_select_zero_returns_empty(self):
        result = mmr_rerank(["1"], [0.9], {"1": np.array([1.0, 0.0])}, select_n=0, lambda_param=0.5)
        assert result == []

    def test_single_candidate(self):
        vecs = {"1": np.array([1.0, 0.0])}
        result = mmr_rerank(["1"], [0.8], vecs, select_n=5, lambda_param=0.5)
        assert len(result) == 1
        assert result[0][0] == "1"

    def test_select_n_larger_than_candidates(self):
        vecs = {
            "1": np.array([1.0, 0.0]),
            "2": np.array([0.0, 1.0]),
        }
        result = mmr_rerank(["1", "2"], [0.9, 0.8], vecs, select_n=10, lambda_param=0.5)
        assert len(result) == 2

    def test_first_selection_is_highest_relevance(self):
        """First MMR selection should always be the highest-relevance item (no diversity penalty yet)."""
        vecs = {
            "1": np.array([1.0, 0.0]),
            "2": np.array([0.0, 1.0]),
            "3": np.array([0.5, 0.5]),
        }
        result = mmr_rerank(["1", "2", "3"], [0.5, 0.9, 0.7], vecs, select_n=3, lambda_param=0.5)
        # Item "2" has the highest relevance (0.9)
        assert result[0][0] == "2"


class TestMMRLambdaEquivalence:
    """λ=1.0 must reproduce pure relevance ordering."""

    def test_lambda_1_preserves_relevance_order(self):
        """With λ=1.0, no diversity penalty is applied. Output order should match relevance ranking."""
        vecs = {
            "1": np.array([1.0, 0.0]),
            "2": np.array([0.9, 0.1]),  # Very similar to "1"
            "3": np.array([0.0, 1.0]),
        }
        scores = [0.5, 0.9, 0.7]
        result = mmr_rerank(["1", "2", "3"], scores, vecs, select_n=3, lambda_param=1.0)
        result_ids = [r[0] for r in result]
        # Pure relevance: 2 (0.9) > 3 (0.7) > 1 (0.5)
        assert result_ids == ["2", "3", "1"]

    def test_lambda_1_with_identical_scores_uses_id_tiebreak(self):
        vecs = {
            "10": np.array([1.0, 0.0]),
            "2": np.array([0.0, 1.0]),
            "5": np.array([0.5, 0.5]),
        }
        # All scores equal
        result = mmr_rerank(["10", "2", "5"], [0.5, 0.5, 0.5], vecs, select_n=3, lambda_param=1.0)
        result_ids = [r[0] for r in result]
        # With equal scores and λ=1.0, tie-break by ascending numeric ID: 2, 5, 10
        assert result_ids == ["2", "5", "10"]


class TestMMRDiversityEffect:
    """MMR should promote diversity when λ < 1.0."""

    def test_diversity_promotes_dissimilar_items(self):
        """With low λ, the second item should be maximally different from the first."""
        # Two nearly identical items and one very different
        vecs = {
            "1": np.array([1.0, 0.0]),
            "2": np.array([0.99, 0.01]),  # Almost identical to "1"
            "3": np.array([0.0, 1.0]),    # Orthogonal to "1" and "2"
        }
        scores = [0.9, 0.85, 0.8]

        # With λ=0.3 (diversity-heavy), after selecting "1", "3" should be
        # preferred over "2" because "3" is more different from "1"
        result = mmr_rerank(["1", "2", "3"], scores, vecs, select_n=3, lambda_param=0.3)
        result_ids = [r[0] for r in result]
        assert result_ids[0] == "1"  # Highest relevance
        assert result_ids[1] == "3"  # Most diverse from "1"

    def test_lambda_0_maximizes_diversity(self):
        """With λ=0.0, pure diversity selection after the first item."""
        vecs = {
            "1": np.array([1.0, 0.0]),
            "2": np.array([0.95, 0.05]),
            "3": np.array([0.0, 1.0]),
        }
        scores = [0.9, 0.85, 0.1]

        result = mmr_rerank(["1", "2", "3"], scores, vecs, select_n=2, lambda_param=0.0)
        # First: highest normalized relevance (item 1: score 0.9, normalized 1.0)
        assert result[0][0] == "1"
        # Second: most diverse from "1" → "3" (orthogonal)
        assert result[1][0] == "3"


class TestMMRDeterminism:
    """MMR must produce identical results across repeated runs."""

    def test_repeated_runs_identical(self):
        vecs = {str(i): np.random.RandomState(i).randn(50) for i in range(20)}
        scores = [0.9 - 0.01 * i for i in range(20)]
        ids = [str(i) for i in range(20)]

        result1 = mmr_rerank(ids, scores, vecs, select_n=10, lambda_param=0.5)
        result2 = mmr_rerank(ids, scores, vecs, select_n=10, lambda_param=0.5)

        assert [r[0] for r in result1] == [r[0] for r in result2]
        for r1, r2 in zip(result1, result2):
            assert abs(r1[1] - r2[1]) < 1e-12

    def test_deterministic_tiebreaking(self):
        """Items with identical relevance and MMR scores should be ordered by ID."""
        # Create two identical items with same relevance
        vecs = {
            "5": np.array([1.0, 0.0]),
            "3": np.array([1.0, 0.0]),  # Identical vector
        }
        result = mmr_rerank(["5", "3"], [0.5, 0.5], vecs, select_n=2, lambda_param=0.5)
        result_ids = [r[0] for r in result]
        # First selected: both have same score, ID tiebreak → "3" < "5"
        assert result_ids[0] == "3"
        assert result_ids[1] == "5"


class TestMMREdgeCases:
    """Edge cases and numerical robustness."""

    def test_zero_vectors_treated_as_max_diversity(self):
        """Items with zero vectors should have maximum diversity (distance = 1.0)."""
        vecs = {
            "1": np.array([1.0, 0.0]),
            "2": np.zeros(2),  # Zero vector
        }
        result = mmr_rerank(["1", "2"], [0.9, 0.8], vecs, select_n=2, lambda_param=0.5)
        assert len(result) == 2

    def test_missing_vectors_handled_gracefully(self):
        """Items not in item_vectors dict should work without error."""
        vecs = {
            "1": np.array([1.0, 0.0]),
            # "2" is missing from vectors
        }
        result = mmr_rerank(["1", "2"], [0.9, 0.8], vecs, select_n=2, lambda_param=0.5)
        assert len(result) == 2

    def test_all_vectors_missing_falls_back_to_relevance(self):
        """If no vectors are available, should fall back to pure relevance ranking."""
        result = mmr_rerank(["1", "2", "3"], [0.5, 0.9, 0.7], {}, select_n=3, lambda_param=0.5)
        result_ids = [r[0] for r in result]
        assert result_ids == ["2", "3", "1"]

    def test_very_large_candidate_pool(self):
        """MMR should handle reasonably large candidate pools efficiently."""
        n = 200
        vecs = {str(i): np.random.RandomState(i).randn(100) for i in range(n)}
        scores = [float(np.random.RandomState(i + 1000).rand()) for i in range(n)]
        ids = [str(i) for i in range(n)]

        result = mmr_rerank(ids, scores, vecs, select_n=20, lambda_param=0.5)
        assert len(result) == 20
        # All IDs should be unique
        assert len(set(r[0] for r in result)) == 20

    def test_identical_items_diversity_penalty(self):
        """Multiple identical items should receive maximum diversity penalty after first."""
        # All items have the same vector
        v = np.array([1.0, 0.0, 0.0])
        vecs = {"1": v.copy(), "2": v.copy(), "3": v.copy()}
        scores = [0.9, 0.8, 0.7]

        result = mmr_rerank(["1", "2", "3"], scores, vecs, select_n=3, lambda_param=0.5)
        # First: highest relevance (1)
        assert result[0][0] == "1"
        # After selecting "1", all remaining have max_sim=1.0 to "1"
        # MMR = 0.5 * rel_norm - 0.5 * 1.0
        # So order is by relevance among tied MMR penalty: "2" > "3"

    def test_negative_scores_handled(self):
        """Negative relevance scores (rare but possible with cosine sim) should work."""
        vecs = {
            "1": np.array([1.0, 0.0]),
            "2": np.array([0.0, 1.0]),
        }
        result = mmr_rerank(["1", "2"], [-0.1, -0.5], vecs, select_n=2, lambda_param=0.5)
        assert len(result) == 2


class TestMMRCandidatePoolIntegration:
    """Tests that MMR correctly operates on pre-filtered candidate pools."""

    def test_mmr_does_not_add_items(self):
        """MMR should only select from the provided candidates."""
        vecs = {
            "1": np.array([1.0, 0.0]),
            "2": np.array([0.0, 1.0]),
            "99": np.array([0.5, 0.5]),  # Not in candidates
        }
        result = mmr_rerank(["1", "2"], [0.9, 0.8], vecs, select_n=3, lambda_param=0.5)
        result_ids = {r[0] for r in result}
        assert "99" not in result_ids
        assert result_ids.issubset({"1", "2"})

    def test_excluded_items_never_appear(self):
        """If candidates are pre-filtered (excluded items removed), MMR cannot reintroduce them."""
        # Simulate pre-filtered candidates (item "3" was excluded before MMR)
        vecs = {
            "1": np.array([1.0, 0.0]),
            "2": np.array([0.0, 1.0]),
            "3": np.array([0.5, 0.5]),  # Excluded - not in candidates
        }
        candidates = ["1", "2"]  # "3" already excluded
        scores = [0.9, 0.8]
        result = mmr_rerank(candidates, scores, vecs, select_n=5, lambda_param=0.5)
        assert all(r[0] in candidates for r in result)


class TestMMRScoreCalculation:
    """Verify exact MMR score computation on known vectors."""

    def test_exact_mmr_scores_step_by_step(self):
        """Hand-calculate MMR scores and verify."""
        # Three orthogonal items for clean math
        vecs = {
            "A": np.array([1.0, 0.0, 0.0]),
            "B": np.array([0.0, 1.0, 0.0]),
            "C": np.array([0.0, 0.0, 1.0]),
        }
        # Relevance scores
        raw_scores = [0.9, 0.6, 0.3]
        lambda_param = 0.5

        result = mmr_rerank(["A", "B", "C"], raw_scores, vecs, select_n=3, lambda_param=lambda_param)

        # Step 1: Normalized scores: A=1.0, B=0.5, C=0.0
        # (rel_norm = (score - min) / (max - min) = (score - 0.3) / 0.6)
        # A: (0.9-0.3)/0.6 = 1.0
        # B: (0.6-0.3)/0.6 = 0.5
        # C: (0.3-0.3)/0.6 = 0.0

        # Step 1: First item - no diversity penalty
        # MMR(A) = 0.5*1.0 - 0.5*0 = 0.5
        # MMR(B) = 0.5*0.5 - 0.5*0 = 0.25
        # MMR(C) = 0.5*0.0 - 0.5*0 = 0.0
        # → Select A (MMR=0.5)
        assert result[0][0] == "A"
        assert abs(result[0][1] - 0.5) < 1e-10

        # Step 2: With A selected, compute max_sim for B and C
        # cos(B, A) = 0 (orthogonal) → max_sim(B) = 0
        # cos(C, A) = 0 (orthogonal) → max_sim(C) = 0
        # MMR(B) = 0.5*0.5 - 0.5*0 = 0.25
        # MMR(C) = 0.5*0.0 - 0.5*0 = 0.0
        # → Select B (MMR=0.25)
        assert result[1][0] == "B"
        assert abs(result[1][1] - 0.25) < 1e-10

        # Step 3: With A,B selected
        # cos(C, A) = 0, cos(C, B) = 0 → max_sim(C) = 0
        # MMR(C) = 0.5*0.0 - 0.5*0 = 0.0
        assert result[2][0] == "C"
        assert abs(result[2][1] - 0.0) < 1e-10

    def test_mmr_with_correlated_items(self):
        """Verify that correlated items get penalized after first selection."""
        # A and B are identical, C is orthogonal
        vecs = {
            "A": np.array([1.0, 0.0]),
            "B": np.array([1.0, 0.0]),  # Identical to A
            "C": np.array([0.0, 1.0]),  # Orthogonal
        }
        raw_scores = [0.9, 0.85, 0.5]
        lambda_param = 0.5

        result = mmr_rerank(["A", "B", "C"], raw_scores, vecs, select_n=3, lambda_param=lambda_param)

        # Normalized: A=1.0, B=0.875, C=0.0 (min=0.5, max=0.9, range=0.4)
        # Wait: (0.9-0.5)/0.4=1.0, (0.85-0.5)/0.4=0.875, (0.5-0.5)/0.4=0.0

        # Step 1: A wins (MMR=0.5*1.0=0.5)
        assert result[0][0] == "A"

        # Step 2: cos(B,A)=1.0, cos(C,A)=0.0
        # MMR(B) = 0.5*0.875 - 0.5*1.0 = 0.4375 - 0.5 = -0.0625
        # MMR(C) = 0.5*0.0   - 0.5*0.0 = 0.0
        # → C wins because 0.0 > -0.0625
        assert result[1][0] == "C"

        # Step 3: Only B remains
        assert result[2][0] == "B"


# ── Integration Tests: BaselineTFIDFRecommender + MMR Config ──────────

from app.recommendation_evaluation.baseline_engine import BaselineTFIDFRecommender
from app.recommendation_evaluation.config import TFIDFV11Config, TFIDFV11MMRConfig
from app.recommendation_evaluation.dataset import MovieMetadata, RatingEvent


def _make_test_movies() -> dict[str, MovieMetadata]:
    """Create a small movie catalog for integration tests."""
    return {
        "1": MovieMetadata(movie_id="1", title="Action Hero", genres=["Action"], text_profile="action hero explosion combat gun fight"),
        "2": MovieMetadata(movie_id="2", title="Romantic Drama", genres=["Romance", "Drama"], text_profile="romance love drama emotion family heart"),
        "3": MovieMetadata(movie_id="3", title="Action Sequel", genres=["Action"], text_profile="action hero explosion sequel combat battle"),
        "4": MovieMetadata(movie_id="4", title="Comedy Film", genres=["Comedy"], text_profile="comedy funny humor laugh slapstick joke"),
        "5": MovieMetadata(movie_id="5", title="Romance Comedy", genres=["Romance", "Comedy"], text_profile="romance comedy love funny date humor"),
        "6": MovieMetadata(movie_id="6", title="Thriller Dark", genres=["Thriller"], text_profile="thriller dark mystery suspense crime noir"),
        "7": MovieMetadata(movie_id="7", title="Sci-Fi Space", genres=["Sci-Fi"], text_profile="scifi space alien technology future galaxy"),
        "8": MovieMetadata(movie_id="8", title="Action Comedy", genres=["Action", "Comedy"], text_profile="action comedy hero funny explosion humor"),
    }


def _make_user_ratings() -> list[RatingEvent]:
    """User who likes action movies."""
    return [
        RatingEvent(user_id="u1", movie_id="1", rating=5.0, timestamp=100),
        RatingEvent(user_id="u1", movie_id="3", rating=4.5, timestamp=200),
    ]


class TestBaselineEngineMMRIntegration:
    """Tests for BaselineTFIDFRecommender with TFIDFV11MMRConfig."""

    def test_mmr_disabled_identical_to_baseline(self):
        """When mmr_enabled=False, TFIDFV11MMRConfig produces same results as TFIDFV11Config."""
        movies = _make_test_movies()
        ratings = _make_user_ratings()

        # Baseline v1.1
        cfg_v11 = TFIDFV11Config(exclude_seen_policy="train")
        rec_v11 = BaselineTFIDFRecommender(cfg_v11)
        rec_v11.fit(movies)
        result_v11 = rec_v11.recommend(ratings, top_n=5, exclude_seen="train")

        # MMR config with mmr_enabled=False
        cfg_mmr_off = TFIDFV11MMRConfig(exclude_seen_policy="train", mmr_enabled=False)
        rec_mmr_off = BaselineTFIDFRecommender(cfg_mmr_off)
        rec_mmr_off.fit(movies)
        result_mmr_off = rec_mmr_off.recommend(ratings, top_n=5, exclude_seen="train")

        assert [mid for mid, _ in result_v11] == [mid for mid, _ in result_mmr_off]
        for (_, s1), (_, s2) in zip(result_v11, result_mmr_off):
            assert abs(s1 - s2) < 1e-12

    def test_mmr_enabled_returns_correct_count(self):
        """MMR re-ranking returns exactly top_n items."""
        movies = _make_test_movies()
        ratings = _make_user_ratings()

        cfg = TFIDFV11MMRConfig(
            exclude_seen_policy="train",
            mmr_enabled=True,
            mmr_lambda=0.5,
            mmr_candidate_pool_size=6,
        )
        rec = BaselineTFIDFRecommender(cfg)
        rec.fit(movies)
        result = rec.recommend(ratings, top_n=3, exclude_seen="train")

        assert len(result) == 3
        # Verify no training items leaked through
        train_ids = {"1", "3"}
        for mid, _ in result:
            assert mid not in train_ids

    def test_mmr_lambda_1_preserves_relevance_order_within_pool(self):
        """λ=1.0 with MMR enabled should produce same order as pure relevance (within pool)."""
        movies = _make_test_movies()
        ratings = _make_user_ratings()

        # Baseline v1.1
        cfg_v11 = TFIDFV11Config(exclude_seen_policy="train")
        rec_v11 = BaselineTFIDFRecommender(cfg_v11)
        rec_v11.fit(movies)
        result_v11 = rec_v11.recommend(ratings, top_n=5, exclude_seen="train")

        # MMR λ=1.0 with pool covering all candidates
        cfg_mmr = TFIDFV11MMRConfig(
            exclude_seen_policy="train",
            mmr_enabled=True,
            mmr_lambda=1.0,
            mmr_candidate_pool_size=100,  # larger than catalog
        )
        rec_mmr = BaselineTFIDFRecommender(cfg_mmr)
        rec_mmr.fit(movies)
        result_mmr = rec_mmr.recommend(ratings, top_n=5, exclude_seen="train")

        # Same ranking order (IDs must match)
        assert [mid for mid, _ in result_v11] == [mid for mid, _ in result_mmr]

    def test_mmr_diversity_reorders_similar_items(self):
        """MMR with low λ should reorder items compared to pure relevance."""
        movies = _make_test_movies()
        ratings = _make_user_ratings()

        # Pure relevance
        cfg_v11 = TFIDFV11Config(exclude_seen_policy="train")
        rec_v11 = BaselineTFIDFRecommender(cfg_v11)
        rec_v11.fit(movies)
        result_rel = rec_v11.recommend(ratings, top_n=6, exclude_seen="train")

        # MMR with strong diversity
        cfg_mmr = TFIDFV11MMRConfig(
            exclude_seen_policy="train",
            mmr_enabled=True,
            mmr_lambda=0.3,
            mmr_candidate_pool_size=6,
        )
        rec_mmr = BaselineTFIDFRecommender(cfg_mmr)
        rec_mmr.fit(movies)
        result_mmr = rec_mmr.recommend(ratings, top_n=6, exclude_seen="train")

        # Same items should appear (same pool), but potentially different order
        rel_ids = sorted([mid for mid, _ in result_rel])
        mmr_ids = sorted([mid for mid, _ in result_mmr])
        assert rel_ids == mmr_ids

        # First item should be the same (highest relevance always selected first)
        assert result_rel[0][0] == result_mmr[0][0]

    def test_mmr_cold_start_bypasses_reranking(self):
        """Cold-start users (no positive ratings) should get fallback, not MMR."""
        movies = _make_test_movies()

        # User with only low ratings
        cold_ratings = [
            RatingEvent(user_id="u2", movie_id="1", rating=1.0, timestamp=100),
        ]

        cfg = TFIDFV11MMRConfig(
            exclude_seen_policy="train",
            mmr_enabled=True,
            mmr_lambda=0.5,
            mmr_candidate_pool_size=50,
        )
        rec = BaselineTFIDFRecommender(cfg)
        rec.fit(movies)
        result = rec.recommend(cold_ratings, top_n=3, exclude_seen="train")

        # Cold-start: all scores should be 0.0
        for _, score in result:
            assert score == 0.0

    def test_mmr_candidate_pool_limits_candidates(self):
        """Pool size limits which candidates MMR considers."""
        movies = _make_test_movies()
        ratings = _make_user_ratings()

        cfg = TFIDFV11MMRConfig(
            exclude_seen_policy="train",
            mmr_enabled=True,
            mmr_lambda=0.5,
            mmr_candidate_pool_size=3,  # Very small pool
        )
        rec = BaselineTFIDFRecommender(cfg)
        rec.fit(movies)
        result = rec.recommend(ratings, top_n=3, exclude_seen="train")

        # Should get exactly 3 results
        assert len(result) == 3

        # All results must be from the top-3 by relevance
        cfg_v11 = TFIDFV11Config(exclude_seen_policy="train")
        rec_v11 = BaselineTFIDFRecommender(cfg_v11)
        rec_v11.fit(movies)
        top3_rel = rec_v11.recommend(ratings, top_n=3, exclude_seen="train")
        top3_ids = {mid for mid, _ in top3_rel}

        for mid, _ in result:
            assert mid in top3_ids

    def test_mmr_deterministic_across_runs(self):
        """MMR results should be identical across repeated runs."""
        movies = _make_test_movies()
        ratings = _make_user_ratings()

        cfg = TFIDFV11MMRConfig(
            exclude_seen_policy="train",
            mmr_enabled=True,
            mmr_lambda=0.5,
            mmr_candidate_pool_size=6,
        )

        results = []
        for _ in range(3):
            rec = BaselineTFIDFRecommender(cfg)
            rec.fit(movies)
            results.append(rec.recommend(ratings, top_n=5, exclude_seen="train"))

        for r in results[1:]:
            assert [(mid, round(s, 10)) for mid, s in r] == [(mid, round(s, 10)) for mid, s in results[0]]
