"""
Comprehensive Unit and Integration Tests for Recommendation Evaluation Framework.

Covers:
  1. Hand-calculated ranking metrics: Precision@K, Recall@K, NDCG@K, HitRate@K, MAP@K
  2. Diversity, Coverage, and Novelty metrics
  3. Metric edge cases: empty lists, k <= 0, zero relevant items, insufficient candidates
  4. Temporal per-user chronological split & leakage prevention
  5. Deterministic checksum reproducibility
  6. Numerical equivalence of BaselineTFIDFRecommender scoring against production logic
  7. Defect R1 behavior preservation (train seen vs unseen)
  8. End-to-end evaluation harness execution
"""

import math
from pathlib import Path
import numpy as np
import pytest

from app.recommendation_evaluation.config import TFIDFBaselineConfig
from app.recommendation_evaluation.dataset import (
    MovieMetadata,
    RatingEvent,
    EvaluationDataset,
    per_user_chronological_split,
    build_movielens_text_profile,
    build_evaluation_dataset,
)
from app.recommendation_evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    ndcg_at_k,
    hit_rate_at_k,
    map_at_k,
    catalog_coverage_at_k,
    intra_list_diversity_at_k,
    novelty_at_k,
    compute_latency_percentiles,
)
from app.recommendation_evaluation.baseline_engine import (
    BaselineTFIDFRecommender,
    map_rating_to_weight,
)
from app.recommendation_evaluation.evaluator import OfflineEvaluator


# ─── 1. Hand-Calculated Metric Tests ──────────────────────────────────────────

def test_precision_at_k_hand_calculated():
    """
    Recommended: ["A", "B", "C", "D", "E"]
    Relevant: {"A", "C"}
    K = 5 -> hits = 2 -> Precision@5 = 2/5 = 0.4
    K = 2 -> hits = 1 ("A") -> Precision@2 = 1/2 = 0.5
    K = 1 -> hits = 1 ("A") -> Precision@1 = 1/1 = 1.0
    """
    recs = ["A", "B", "C", "D", "E"]
    rel = {"A", "C"}
    assert precision_at_k(recs, rel, 5) == pytest.approx(0.4)
    assert precision_at_k(recs, rel, 2) == pytest.approx(0.5)
    assert precision_at_k(recs, rel, 1) == pytest.approx(1.0)
    assert precision_at_k(recs, set(), 5) == 0.0
    assert precision_at_k(recs, rel, 0) == 0.0


def test_recall_at_k_hand_calculated():
    """
    Recommended: ["A", "B", "C", "D", "E"]
    Relevant: {"A", "C", "F"} (total 3 relevant items)
    K = 5 -> hits = 2 ("A", "C") -> Recall@5 = 2/3 = 0.666666...
    K = 2 -> hits = 1 ("A") -> Recall@2 = 1/3 = 0.333333...
    K = 1 -> hits = 1 ("A") -> Recall@1 = 1/3 = 0.333333...
    """
    recs = ["A", "B", "C", "D", "E"]
    rel = {"A", "C", "F"}
    assert recall_at_k(recs, rel, 5) == pytest.approx(2.0 / 3.0)
    assert recall_at_k(recs, rel, 2) == pytest.approx(1.0 / 3.0)
    assert recall_at_k(recs, rel, 1) == pytest.approx(1.0 / 3.0)
    assert recall_at_k(recs, set(), 5) == 0.0


def test_ndcg_at_k_hand_calculated():
    """
    Recommended: ["A", "B", "C"]
    Relevant: {"B", "C"}
    Rank 1 ("A"): rel=0
    Rank 2 ("B"): rel=1 / log2(3) = 0.63092975
    Rank 3 ("C"): rel=1 / log2(4) = 0.50000000
    DCG@3 = 0 + 0.63092975 + 0.5 = 1.13092975
    Ideal ranking has relevant items at rank 1 and 2:
    IDCG@3 = 1 / log2(2) + 1 / log2(3) = 1.0 + 0.63092975 = 1.63092975
    NDCG@3 = 1.13092975 / 1.63092975 ≈ 0.693426
    """
    recs = ["A", "B", "C"]
    rel = {"B", "C"}
    dcg = 0.0 + 1.0 / math.log2(3) + 1.0 / math.log2(4)
    idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3)
    expected_ndcg = dcg / idcg

    assert ndcg_at_k(recs, rel, 3) == pytest.approx(expected_ndcg, rel=1e-5)
    # At K=1, no relevant item in top 1 -> NDCG = 0.0
    assert ndcg_at_k(recs, rel, 1) == 0.0
    # Perfect top 1
    assert ndcg_at_k(["B", "A", "C"], rel, 1) == 1.0


def test_hit_rate_at_k():
    recs = ["A", "B", "C"]
    assert hit_rate_at_k(recs, {"B"}, 1) == 0.0
    assert hit_rate_at_k(recs, {"B"}, 2) == 1.0
    assert hit_rate_at_k(recs, {"Z"}, 3) == 0.0
    assert hit_rate_at_k(recs, set(), 3) == 0.0


def test_map_at_k_hand_calculated():
    """
    Recommended: ["A", "B", "C", "D"]
    Relevant: {"A", "C"} (|Rel| = 2)
    Rank 1 ("A"): hit -> Precision@1 = 1/1 = 1.0
    Rank 2 ("B"): miss
    Rank 3 ("C"): hit -> Precision@3 = 2/3 ≈ 0.66667
    Rank 4 ("D"): miss
    AP@4 = (1.0 + 2/3) / min(4, 2) = (5/3) / 2 = 5/6 ≈ 0.833333
    AP@2 = 1.0 / min(2, 2) = 0.5
    """
    recs = ["A", "B", "C", "D"]
    rel = {"A", "C"}
    assert map_at_k(recs, rel, 4) == pytest.approx(5.0 / 6.0)
    assert map_at_k(recs, rel, 2) == pytest.approx(0.5)
    assert map_at_k(recs, set(), 4) == 0.0


def test_catalog_coverage_at_k():
    recs_by_user = {
        "u1": ["m1", "m2", "m3"],
        "u2": ["m2", "m4", "m5"],
    }
    catalog = {"m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9", "m10"}
    # Top-2 for u1: {m1, m2}, for u2: {m2, m4} -> union = {m1, m2, m4} (3 items)
    assert catalog_coverage_at_k(recs_by_user, catalog, 2) == pytest.approx(3 / 10.0)
    # Top-3 -> union = {m1, m2, m3, m4, m5} (5 items)
    assert catalog_coverage_at_k(recs_by_user, catalog, 3) == pytest.approx(5 / 10.0)


def test_intra_list_diversity_at_k():
    # Orthogonal vectors: cosine sim = 0 -> distance = 1.0
    item_vectors = {
        "m1": np.array([1.0, 0.0, 0.0]),
        "m2": np.array([0.0, 1.0, 0.0]),
        "m3": np.array([0.0, 0.0, 1.0]),
    }
    recs = {"u1": ["m1", "m2", "m3"]}
    ild = intra_list_diversity_at_k(recs, item_vectors, 3)
    # All 3 pairs have cos_sim = 0 -> distance = 1.0 -> average = 1.0
    assert ild == pytest.approx(1.0)

    # Identical vectors: cosine sim = 1.0 -> distance = 0.0
    item_vectors_identical = {
        "m1": np.array([1.0, 1.0, 0.0]),
        "m2": np.array([1.0, 1.0, 0.0]),
    }
    assert intra_list_diversity_at_k({"u1": ["m1", "m2"]}, item_vectors_identical, 2) == pytest.approx(0.0)


def test_novelty_at_k():
    # Total interactions = 100
    # Item A has count 50 (prob 0.5 -> -log2(0.5) = 1 bit)
    # Item B has count 25 (prob 0.25 -> -log2(0.25) = 2 bits)
    item_counts = {"A": 50, "B": 25}
    recs = {"u1": ["A", "B"]}
    nov = novelty_at_k(recs, item_counts, total_interactions=100, k=2)
    assert nov == pytest.approx((1.0 + 2.0) / 2.0)


def test_latency_percentiles():
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
    p = compute_latency_percentiles(latencies)
    assert p["p50_ms"] == 30.0
    assert p["mean_ms"] == 30.0
    assert p["p95_ms"] > 45.0


# ─── 2. Temporal Splitting & Leakage Prevention ───────────────────────────────

def test_temporal_split_monotonicity_and_no_leakage():
    ratings = [
        RatingEvent("u1", "m1", 4.0, 100),
        RatingEvent("u1", "m2", 5.0, 110),
        RatingEvent("u1", "m3", 3.0, 120),
        RatingEvent("u1", "m4", 4.0, 130),
        RatingEvent("u1", "m5", 2.0, 140),
        RatingEvent("u1", "m6", 5.0, 150),
        RatingEvent("u1", "m7", 4.0, 160),
        RatingEvent("u1", "m8", 3.0, 170),
        RatingEvent("u1", "m9", 5.0, 180),
        RatingEvent("u1", "m10", 4.0, 190),
    ]
    train_by_u, val_by_u, test_by_u, split_chk = per_user_chronological_split(
        ratings, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15, min_interactions=5
    )

    u1_train = train_by_u["u1"]
    u1_val = val_by_u["u1"]
    u1_test = test_by_u["u1"]

    assert len(u1_train) == 7
    assert len(u1_val) == 1
    assert len(u1_test) == 2

    max_train_ts = max(r.timestamp for r in u1_train)
    min_val_ts = min(r.timestamp for r in u1_val)
    max_val_ts = max(r.timestamp for r in u1_val)
    min_test_ts = min(r.timestamp for r in u1_test)

    # Strictly non-decreasing temporal partition
    assert max_train_ts <= min_val_ts
    assert max_val_ts <= min_test_ts


def test_split_determinism():
    ratings = [
        RatingEvent(f"u{i}", f"m{j}", 4.0, 100 + i * 10 + j)
        for i in range(1, 5)
        for j in range(1, 8)
    ]
    _, _, _, chk1 = per_user_chronological_split(ratings)
    _, _, _, chk2 = per_user_chronological_split(ratings)
    assert chk1 == chk2
    assert len(chk1) == 64


# ─── 3. Baseline Scoring & Defect R1 Preservation ─────────────────────────────

def test_map_rating_to_weight():
    # Integer tests matching production
    assert map_rating_to_weight(5.0) == 5.0
    assert map_rating_to_weight(4.0) == 3.0
    assert map_rating_to_weight(3.0) == 1.0
    assert map_rating_to_weight(2.0) == 0.0
    assert map_rating_to_weight(1.0) == 0.0

    # Half-star intervals
    assert map_rating_to_weight(4.5) == 5.0
    assert map_rating_to_weight(3.5) == 3.0
    assert map_rating_to_weight(2.5) == 1.0
    assert map_rating_to_weight(1.5) == 0.0
    assert map_rating_to_weight(0.5) == 0.0


def test_baseline_scoring_and_defect_r1():
    """
    Verify BaselineTFIDFRecommender respects Defect R1:
    When exclude_seen='none', highly rated training items ARE recommended back.
    When exclude_seen='train', training items are excluded.
    """
    movies = {
        "1": MovieMetadata("1", "Action Blast", ["Action"], ["explosion", "chase"], "Action Blast Action Blast Action explosion chase explosion chase"),
        "2": MovieMetadata("2", "Action Boom", ["Action"], ["explosion", "guns"], "Action Boom Action Boom Action explosion guns explosion guns"),
        "3": MovieMetadata("3", "Love Story", ["Romance"], ["love", "heart"], "Love Story Love Story Romance love heart love heart"),
    }
    recommender = BaselineTFIDFRecommender(TFIDFBaselineConfig(exclude_seen_policy="none"))
    recommender.fit(movies)

    # User rated movie 1 with 5 stars
    user_ratings = [RatingEvent("u1", "1", 5.0, 100)]

    # Run with Defect R1 active: movie 1 should be recommended at top rank #1
    recs_r1 = recommender.recommend(user_ratings, top_n=3, exclude_seen="none")
    assert recs_r1[0][0] == "1", "Defect R1 must recommend training movie 1 at top rank"
    assert recs_r1[0][1] == pytest.approx(1.0, abs=1e-4)

    # Run with train items excluded: movie 1 must NOT appear
    recs_clean = recommender.recommend(user_ratings, top_n=3, exclude_seen="train")
    top_clean_ids = [m for m, _ in recs_clean]
    assert "1" not in top_clean_ids
    assert recs_clean[0][0] == "2", "Movie 2 (Action) should be top recommendation among unseen"


def test_baseline_numerical_equivalence():
    """
    Verify user vector aggregation formula: sum(w_i * m_i) / sum(w_i) -> L2 norm
    produces identical results to direct manual computation.
    """
    movies = {
        "1": MovieMetadata("1", "SciFi Space", ["Sci-Fi"], ["alien"], "SciFi Space SciFi Space Sci-Fi alien alien"),
        "2": MovieMetadata("2", "SciFi Stars", ["Sci-Fi"], ["galaxy"], "SciFi Stars SciFi Stars Sci-Fi galaxy galaxy"),
    }
    rec = BaselineTFIDFRecommender()
    rec.fit(movies)

    # 5-star rating on movie 1 (weight 5.0) and 4-star on movie 2 (weight 3.0)
    ratings = [
        RatingEvent("u1", "1", 5.0, 100),
        RatingEvent("u1", "2", 4.0, 110),
    ]
    user_vec = rec.build_user_vector(ratings)
    assert user_vec is not None

    v1 = rec.item_vectors["1"]
    v2 = rec.item_vectors["2"]
    expected_unnorm = (5.0 * v1 + 3.0 * v2) / 8.0
    expected_norm = expected_unnorm / np.linalg.norm(expected_unnorm)

    assert np.allclose(user_vec, expected_norm, atol=1e-9)


# ─── 4. End-to-End Evaluator Harness ──────────────────────────────────────────

def test_evaluator_harness_end_to_end():
    movies = {
        "1": MovieMetadata("1", "Action Hero", ["Action"], ["hero"], "Action Hero Action Hero Action hero hero"),
        "2": MovieMetadata("2", "Action Super", ["Action"], ["hero"], "Action Super Action Super Action hero hero"),
        "3": MovieMetadata("3", "Comedy Laugh", ["Comedy"], ["funny"], "Comedy Laugh Comedy Laugh Comedy funny funny"),
        "4": MovieMetadata("4", "Comedy Joke", ["Comedy"], ["funny"], "Comedy Joke Comedy Joke Comedy funny funny"),
    }
    # 2 users: u1 likes Action, u2 likes Comedy
    train_by_u = {
        "u1": [RatingEvent("u1", "1", 5.0, 10)],
        "u2": [RatingEvent("u2", "3", 5.0, 10)],
    }
    val_by_u = {"u1": [], "u2": []}
    test_by_u = {
        "u1": [RatingEvent("u1", "2", 5.0, 20)],  # relevant
        "u2": [RatingEvent("u2", "4", 4.0, 20)],  # relevant
    }
    dataset = EvaluationDataset(
        movies=movies,
        train_by_user=train_by_u,
        val_by_user=val_by_u,
        test_by_user=test_by_u,
        raw_files_checksum="dummy_raw",
        split_checksum="dummy_split",
        total_ratings_count=4,
        users_count=2,
        movies_count=4,
    )

    config = TFIDFBaselineConfig(k_values=(2,), exclude_seen_policy="train")
    evaluator = OfflineEvaluator(config)
    res = evaluator.evaluate(dataset)

    assert res.total_users_evaluated == 2
    assert res.users_with_relevant_items == 2
    # With clean exclusion, u1 gets movie 2 (Action) ranked 1st; u2 gets movie 4 (Comedy) ranked 1st
    assert res.aggregate_metrics["by_k"]["k_2"]["hit_rate"] == 1.0
    assert res.aggregate_metrics["by_k"]["k_2"]["precision"] == 0.5  # 1 hit out of 2 recommendations
    assert res.aggregate_metrics["by_k"]["k_2"]["recall"] == 1.0     # 1 hit out of 1 test relevant


# ─── 5. Numerical Equivalence Against Live Production Engine ──────────────────

def test_exact_numerical_equivalence_with_production_engine(monkeypatch):
    """
    Directly verify that BaselineTFIDFRecommender computes the identical
    cosine similarity scores as the production engine.py + user_profile.py.
    """
    import uuid
    from datetime import date
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models.movie import Movie
    from app.models.user import User
    from app.models.rating import Rating
    from app.services.recommendation.engine import get_recommendations
    from app.services.recommendation.vectorizer import invalidate_cache
    from app.services.recommendation.movie_profile import build_movie_text

    # Enable all movies in candidate pool
    monkeypatch.setenv("RECOMMEND_ONLY_UPLOADED_MOVIES", "false")
    invalidate_cache()

    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    Session = sessionmaker(bind=test_engine)
    session = Session()

    try:
        user_id = uuid.uuid4()
        user = User(id=user_id, email="equiv_test@test.com", password_hash="dummy", role="user")
        session.add(user)

        m1_id = uuid.uuid4()
        m2_id = uuid.uuid4()
        m3_id = uuid.uuid4()

        m1 = Movie(
            id=m1_id,
            title="Inception Dream",
            genres=["Action", "Sci-Fi"],
            keywords=["dream", "mind"],
            director="Christopher Nolan",
            cast=["Leonardo DiCaprio"],
            overview="Heist inside dreams",
            release_date=date(2010, 7, 16),
            processing_status="ready",
        )
        m2 = Movie(
            id=m2_id,
            title="Interstellar Stars",
            genres=["Adventure", "Drama", "Sci-Fi"],
            keywords=["space", "wormhole"],
            director="Christopher Nolan",
            cast=["Matthew McConaughey"],
            overview="Journey through wormhole",
            release_date=date(2014, 11, 7),
            processing_status="ready",
        )
        m3 = Movie(
            id=m3_id,
            title="The Notebook Romance",
            genres=["Drama", "Romance"],
            keywords=["love", "diary"],
            director="Nick Cassavetes",
            cast=["Ryan Gosling"],
            overview="True love story",
            release_date=date(2004, 6, 25),
            processing_status="ready",
        )
        session.add_all([m1, m2, m3])

        # User gave 5 stars to Inception, 4 stars to Interstellar
        r1 = Rating(user_id=user_id, movie_id=m1_id, rating=5)
        r2 = Rating(user_id=user_id, movie_id=m2_id, rating=4)
        session.add_all([r1, r2])
        session.commit()

        # 1. Run production engine (with exclude_interacted=False to verify raw cosine scoring)
        prod_recs = get_recommendations(session, user_id, top_n=3, exclude_interacted=False)
        prod_scores = {r["id"]: r["score"] for r in prod_recs}

        # 2. Run BaselineTFIDFRecommender using identical text profiles
        eval_movies = {
            str(m.id): MovieMetadata(
                movie_id=str(m.id),
                title=m.title,
                genres=m.genres or [],
                tags=m.keywords or [],
                text_profile=build_movie_text(m),
            )
            for m in [m1, m2, m3]
        }
        baseline = BaselineTFIDFRecommender(TFIDFBaselineConfig(exclude_seen_policy="none"))
        baseline.fit(eval_movies)

        eval_ratings = [
            RatingEvent(str(user_id), str(m1_id), 5.0, 100),
            RatingEvent(str(user_id), str(m2_id), 4.0, 110),
        ]
        base_recs = baseline.recommend(eval_ratings, top_n=3, exclude_seen="none")
        base_scores = {mid: round(score, 4) for mid, score in base_recs}

        # Verify exact numerical match for all movies
        for mid in [str(m1_id), str(m2_id), str(m3_id)]:
            assert mid in prod_scores
            assert mid in base_scores
            assert prod_scores[mid] == pytest.approx(base_scores[mid], abs=1e-4)

    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        invalidate_cache()
