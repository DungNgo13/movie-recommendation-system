"""
Tests for TF-IDF v1.1 Correctness Fixes:
  - R1: Seen-item exclusion (rated, completed/substantially watched, favorited; preserving previewed)
  - R2: Explicit negative feedback precedence (disliked ratings suppress watch/favorite positive weights)
  - R3: Deterministic cold start (NULL release dates sort last; deterministic tie-breaking; accurate reason)
  - Admin Explainer synchronization with R1/R2 engine behavior
"""

import os
import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.movie import Movie
from app.models.user import User
from app.models.rating import Rating
from app.models.user_favorite import UserFavorite
from app.models.watch_history import WatchHistory
from app.services.recommendation.engine import (
    get_recommendations,
    get_user_excluded_movie_ids,
    _cold_start_fallback,
    WATCH_EXCLUSION_PROGRESS_THRESHOLD,
)
from app.services.recommendation.user_profile import build_user_profile
from app.services.recommendation.vectorizer import invalidate_cache
from app.services.recommendation.explainer_admin import explain_recommendations


test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)
_env_filter_off = {"RECOMMEND_ONLY_UPLOADED_MOVIES": "false"}
_DEFAULT_DATE = object()


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=test_engine)
    invalidate_cache()
    yield
    invalidate_cache()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


def _make_movie(
    db,
    title: str,
    genres: list[str] | None = None,
    keywords: list[str] | None = None,
    director: str | None = "Director X",
    release_date: object = _DEFAULT_DATE,
    processing_status: str = "ready",
) -> Movie:
    r_date = date(2024, 1, 1) if release_date is _DEFAULT_DATE else release_date
    movie = Movie(
        id=uuid.uuid4(),
        title=title,
        overview=f"Overview for {title}",
        release_date=r_date,
        genres=genres or ["Drama"],
        keywords=keywords or ["drama"],
        director=director,
        processing_status=processing_status,
    )
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie


def _make_user(db) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:6]}@test.com",
        password_hash="$2b$12$dummy",
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ─── 1. R1: Seen-Item Exclusion Tests ─────────────────────────────────────────

class TestR1SeenItemExclusion:
    """Verify rated, favorited, and substantially watched movies are excluded."""

    def test_rated_movie_is_excluded(self, db):
        m1 = _make_movie(db, "Rated Masterpiece", genres=["Action"])
        m2 = _make_movie(db, "Action Next", genres=["Action"])
        user = _make_user(db)

        # User rates m1
        db.add(Rating(user_id=user.id, movie_id=m1.id, rating=5))
        db.commit()

        with patch.dict(os.environ, _env_filter_off):
            recs = get_recommendations(db, user.id, top_n=5)

        rec_ids = [r["id"] for r in recs]
        assert str(m1.id) not in rec_ids, "Rated movie m1 must be excluded from recommendations"
        assert str(m2.id) in rec_ids, "Unseen candidate m2 should be recommended"

    def test_watched_movie_threshold_exclusion(self, db):
        m_watched = _make_movie(db, "Fully Watched Film", genres=["Sci-Fi"])
        m_previewed = _make_movie(db, "Previewed Clip Film", genres=["Sci-Fi"])
        m_unseen = _make_movie(db, "Unseen Sci-Fi Film", genres=["Sci-Fi"])
        user = _make_user(db)

        # m_watched: 90% progress (>= 80% threshold)
        db.add(WatchHistory(user_id=user.id, movie_id=m_watched.id, progress_percent=90))
        # m_previewed: 15% progress (< 80% threshold, not completed)
        db.add(WatchHistory(user_id=user.id, movie_id=m_previewed.id, progress_percent=15, is_completed=False))
        db.commit()

        excluded = get_user_excluded_movie_ids(db, user.id)
        assert str(m_watched.id) in excluded, "Movie watched >= 80% must be in exclusion set"
        assert str(m_previewed.id) not in excluded, "Previewed movie (< 80%) must NOT be in exclusion set"

        with patch.dict(os.environ, _env_filter_off):
            recs = get_recommendations(db, user.id, top_n=5)

        rec_ids = [r["id"] for r in recs]
        assert str(m_watched.id) not in rec_ids
        assert str(m_previewed.id) in rec_ids or str(m_unseen.id) in rec_ids

    def test_completed_watch_flag_excludes_even_if_progress_zero(self, db):
        m = _make_movie(db, "Completed Film")
        user = _make_user(db)
        db.add(WatchHistory(user_id=user.id, movie_id=m.id, progress_percent=0, is_completed=True))
        db.commit()

        excluded = get_user_excluded_movie_ids(db, user.id)
        assert str(m.id) in excluded

    def test_favorite_is_excluded(self, db):
        m1 = _make_movie(db, "Favorite Film", genres=["Comedy"])
        m2 = _make_movie(db, "Comedy Alternative", genres=["Comedy"])
        user = _make_user(db)
        db.add(UserFavorite(user_id=user.id, movie_id=m1.id))
        db.commit()

        with patch.dict(os.environ, _env_filter_off):
            recs = get_recommendations(db, user.id, top_n=5)

        rec_ids = [r["id"] for r in recs]
        assert str(m1.id) not in rec_ids
        assert str(m2.id) in rec_ids

    def test_exclusion_can_be_disabled(self, db):
        m = _make_movie(db, "Movie To Retain", genres=["Action"])
        user = _make_user(db)
        db.add(Rating(user_id=user.id, movie_id=m.id, rating=5))
        db.commit()

        with patch.dict(os.environ, _env_filter_off):
            recs = get_recommendations(db, user.id, top_n=5, exclude_interacted=False)

        rec_ids = [r["id"] for r in recs]
        assert str(m.id) in rec_ids

    def test_all_candidates_seen_returns_empty_list(self, db):
        m = _make_movie(db, "Sole Movie")
        user = _make_user(db)
        db.add(Rating(user_id=user.id, movie_id=m.id, rating=5))
        db.commit()

        with patch.dict(os.environ, _env_filter_off):
            recs = get_recommendations(db, user.id, top_n=5)

        assert recs == []


# ─── 2. R2: Negative Feedback Precedence Tests ────────────────────────────────

class TestR2NegativeFeedbackPrecedence:
    """Verify explicit 1-2 star ratings suppress positive signals from watch or favorites."""

    def test_disliked_movie_with_completed_watch_has_zero_profile_weight(self, db):
        m_disliked = _make_movie(db, "Disliked Movie", genres=["Horror"], keywords=["ghost"])
        m_liked = _make_movie(db, "Liked Movie", genres=["Sci-Fi"], keywords=["alien"])
        user = _make_user(db)

        # 1-star rating on m_disliked, but 100% watched
        db.add(Rating(user_id=user.id, movie_id=m_disliked.id, rating=1))
        db.add(WatchHistory(user_id=user.id, movie_id=m_disliked.id, progress_percent=100))

        # 5-star rating on m_liked
        db.add(Rating(user_id=user.id, movie_id=m_liked.id, rating=5))
        db.commit()

        with patch.dict(os.environ, _env_filter_off):
            # Profile with R2 fix (suppress_negative=True)
            user_vec_fixed = build_user_profile(db, user.id, suppress_negative=True)
            # Legacy v1.0 profile (suppress_negative=False)
            user_vec_legacy = build_user_profile(db, user.id, suppress_negative=False)

        assert user_vec_fixed is not None
        assert user_vec_legacy is not None

        # In fixed mode, user profile must be based solely on m_liked (Sci-Fi)
        from app.services.recommendation.vectorizer import get_movie_vector_by_id
        vec_liked = get_movie_vector_by_id(db, str(m_liked.id))
        vec_disliked = get_movie_vector_by_id(db, str(m_disliked.id))

        cos_liked_fixed = float(np.dot(user_vec_fixed, vec_liked))
        cos_disliked_fixed = float(np.dot(user_vec_fixed, vec_disliked))

        assert cos_liked_fixed == pytest.approx(1.0, abs=1e-4)
        assert cos_disliked_fixed == pytest.approx(0.0, abs=1e-4)

        # In legacy mode, disliked movie had positive watch weight, polluting profile
        cos_disliked_legacy = float(np.dot(user_vec_legacy, vec_disliked))
        assert cos_disliked_legacy > 0.1, "Legacy mode incorrectly leaks positive weight for disliked movie"

    def test_disliked_rating_overrides_stale_favorite(self, db):
        m = _make_movie(db, "Favorite Turned Bad", genres=["Action"])
        user = _make_user(db)

        # User favorited the movie, but subsequently rated it 2 stars (disliked)
        db.add(UserFavorite(user_id=user.id, movie_id=m.id))
        db.add(Rating(user_id=user.id, movie_id=m.id, rating=2))
        db.commit()

        with patch.dict(os.environ, _env_filter_off):
            user_vec = build_user_profile(db, user.id, suppress_negative=True)

        # Since the user's only interaction is disliked, profile must return None (cold start)
        assert user_vec is None

    def test_positive_rating_and_watch_retains_positive_signal(self, db):
        m = _make_movie(db, "Loved Movie", genres=["Drama"])
        user = _make_user(db)
        db.add(Rating(user_id=user.id, movie_id=m.id, rating=4))
        db.add(WatchHistory(user_id=user.id, movie_id=m.id, progress_percent=100))
        db.commit()

        with patch.dict(os.environ, _env_filter_off):
            user_vec = build_user_profile(db, user.id, suppress_negative=True)

        assert user_vec is not None


# ─── 3. R3: Deterministic Cold Start Tests ────────────────────────────────────

class TestR3DeterministicColdStart:
    """Verify cold start ordering handles NULL release dates and deterministic tie-breaking."""

    def test_null_release_dates_placed_last_and_deterministic_order(self, db):
        # Create movies with known dates and NULL dates
        m_new = _make_movie(db, "Newest 2024", release_date=date(2024, 12, 1))
        m_mid = _make_movie(db, "Mid 2023", release_date=date(2023, 6, 1))
        m_null_1 = _make_movie(db, "Null Date A", release_date=None)
        m_null_2 = _make_movie(db, "Null Date B", release_date=None)

        with patch.dict(os.environ, _env_filter_off):
            recs = _cold_start_fallback(db, top_n=10)

        assert len(recs) == 4
        # Newest date first, then older date, then NULL dates last
        assert recs[0]["title"] == "Newest 2024"
        assert recs[1]["title"] == "Mid 2023"
        assert recs[2]["title"] in ("Null Date A", "Null Date B")
        assert recs[3]["title"] in ("Null Date A", "Null Date B")

        # Tie-breaker deterministic check
        null_ids = [recs[2]["id"], recs[3]["id"]]
        assert null_ids == sorted(null_ids), "Equal/NULL release dates must break ties by id ASC"

    def test_cold_start_reason_label_is_accurate(self, db):
        _make_movie(db, "Cold Movie")
        with patch.dict(os.environ, _env_filter_off):
            recs = _cold_start_fallback(db, top_n=1)

        assert len(recs) == 1
        assert "recently released" in recs[0]["reason"].lower()
        assert "popular movie" not in recs[0]["reason"].lower()


# ─── 4. Admin Explainer Synchronization Tests ─────────────────────────────────

class TestAdminExplainerSynchronization:
    """Verify admin explainer matches get_recommendations and documents negative suppression."""

    def test_explainer_matches_engine_recommendations_and_suppresses_disliked(self, db):
        m1 = _make_movie(db, "Hated Movie", genres=["Action"])
        m2 = _make_movie(db, "Action Pick", genres=["Action"])
        m3 = _make_movie(db, "Drama Pick", genres=["Drama"])
        user = _make_user(db)

        # 1-star rating on m1 with 100% watch progress
        db.add(Rating(user_id=user.id, movie_id=m1.id, rating=1))
        db.add(WatchHistory(user_id=user.id, movie_id=m1.id, progress_percent=100))
        # 5-star rating on m2
        db.add(Rating(user_id=user.id, movie_id=m2.id, rating=5))
        db.commit()

        with patch.dict(os.environ, _env_filter_off):
            engine_recs = get_recommendations(db, user.id, top_n=5)
            diag = explain_recommendations(db, user.id, top_n=5)

        # 1. Both engine and explainer must exclude rated movies (m1 and m2) from recommended picks
        engine_ids = [r["id"] for r in engine_recs]
        explainer_ids = [r["movie_id"] for r in diag["top_recommendations"]]
        assert str(m1.id) not in engine_ids
        assert str(m1.id) not in explainer_ids
        assert str(m2.id) not in engine_ids
        assert str(m2.id) not in explainer_ids

        # 2. Explainer user_context must document that m1 watch weight was suppressed by 1-star rating
        hated_ctx = next(x for x in diag["user_context"] if x["movie_id"] == str(m1.id) and x["signal_type"] == "watch")
        assert hated_ctx["calculated_weight"] == 0.0
        assert "suppressed" in hated_ctx["weight_breakdown"].lower()
