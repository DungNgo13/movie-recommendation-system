"""
Tests for Phase 8A Admin Review APIs, Safe Metadata Application, and Recommendation Cache Sync.

Covers:
  - Admin RBAC enforcement (401 unauthenticated, 403 non-admin)
  - Full staging -> candidate selection -> field approval -> atomic DB application
  - Preservation of unapproved manual fields, protected media/streaming fields, and user interactions
  - Explicit overwrite confirmation guard (`allow_overwrite_existing`)
  - Optimistic concurrency conflict detection (`expected_metadata_version`)
  - Idempotent repeated approval and application calls
  - Rejection workflow and active lock release
  - Transaction rollback on database error during application
  - TF-IDF recommendation cache invalidation and updated recommendation ranking after enrichment
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.admin_audit_log import AdminAuditLog
from app.models.metadata_enrichment import (
    MetadataFieldProvenance,
    MetadataReviewEvent,
)
from app.models.movie import Movie
from app.models.movie_asset import MovieAsset
from app.models.rating import Rating
from app.models.user import User
from app.models.user_favorite import UserFavorite
from app.models.watch_history import WatchHistory
from app.services.recommendation.engine import get_recommendations
from app.services.recommendation.vectorizer import (
    get_cache_stats,
    get_movie_vectors,
    invalidate_cache,
)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        invalidate_cache()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _create_user(db_session, role: str = "admin") -> tuple[User, dict[str, str]]:
    user = User(
        id=uuid4(),
        email=f"{role}-{uuid4().hex[:6]}@movsug.test",
        password_hash="$2b$12$dummyhash",
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return user, {"Authorization": f"Bearer {token}"}


class _FakeTMDBClient:
    """Deterministic fake TMDB client returning realistic search & detail payloads."""

    is_mocked = True

    class _Stats:
        retry_count = 0
        http_429_count = 0

    stats = _Stats()

    def search_movies(self, query: str, year=None, language: str = "en-US", page: int = 1):
        return {
            "page": 1,
            "total_results": 2,
            "total_pages": 1,
            "results": [
                {
                    "id": 278,
                    "title": "The Shawshank Redemption",
                    "original_title": "The Shawshank Redemption",
                    "release_date": "1994-09-23",
                    "original_language": "en",
                    "popularity": 140.5,
                    "vote_count": 26000,
                },
                {
                    "id": 999278,
                    "title": "Shawshank: The Documentary",
                    "original_title": "Shawshank: The Documentary",
                    "release_date": "2014-05-01",
                    "original_language": "en",
                    "popularity": 5.0,
                    "vote_count": 20,
                },
            ],
        }

    def get_movie_details(
        self,
        tmdb_id: int,
        language: str = "en-US",
        append_credits_and_keywords: bool = True,
    ):
        if tmdb_id == 278:
            if language == "vi-VN":
                return {
                    "id": 278,
                    "title": "Nhà Tù Shawshank",
                    "overview": "Hai tù nhân kết bạn trong suốt nhiều năm tại nhà tù Shawshank.",
                }
            return {
                "id": 278,
                "imdb_id": "tt0111161",
                "title": "The Shawshank Redemption",
                "original_title": "The Shawshank Redemption",
                "original_language": "en",
                "release_date": "1994-09-23",
                "runtime": 142,
                "overview": "Imprisoned in the 1940s for the double murder of his wife and her lover, upstanding banker Andy Dufresne begins a new life at the Shawshank prison.",
                "poster_path": "/9cqNxx0GxF0bflZmeSMuL5tnGzr.jpg",
                "backdrop_path": "/kXfqcdQKsToO0OUXHcrrNCHDBzO.jpg",
                "genres": [{"id": 18, "name": "Drama"}, {"id": 80, "name": "Crime"}],
                "credits": {
                    "cast": [
                        {"name": "Tim Robbins", "order": 0},
                        {"name": "Morgan Freeman", "order": 1},
                        {"name": "Bob Gunton", "order": 2},
                    ],
                    "crew": [
                        {"name": "Frank Darabont", "job": "Director"},
                        {"name": "Roger Deakins", "job": "Director of Photography"},
                    ],
                },
                "keywords": {
                    "keywords": [
                        {"id": 378, "name": "prison"},
                        {"id": 999, "name": "wrongful imprisonment"},
                        {"id": 1001, "name": "hope"},
                    ]
                },
            }
        return {
            "id": tmdb_id,
            "imdb_id": "tt9999999",
            "title": "Shawshank: The Documentary",
            "original_title": "Shawshank: The Documentary",
            "original_language": "en",
            "release_date": "2014-05-01",
            "runtime": 60,
            "overview": "Behind the scenes documentary.",
            "genres": [{"id": 99, "name": "Documentary"}],
            "credits": {"cast": [], "crew": [{"name": "Doc Maker", "job": "Director"}]},
            "keywords": {"keywords": []},
        }

    def find_by_external_id(self, external_id: str, external_source: str = "imdb_id", language: str = "en-US"):
        return []

    def get_movie_localized_details(self, tmdb_id: int, language: str = "vi-VN"):
        return self.get_movie_details(tmdb_id=tmdb_id, language=language, append_credits_and_keywords=False)

    def close(self):
        pass


def test_unauthorized_and_non_admin_access_rejected(client, db_session):
    movie = Movie(id=uuid4(), title="Test Movie", release_date=date(1994, 1, 1))
    db_session.add(movie)
    db_session.commit()

    # Unauthenticated -> 401
    res_unauth = client.post(f"/api/v1/admin/movies/{movie.id}/enrichment/start")
    assert res_unauth.status_code == 401

    # Regular user -> 403
    _, user_headers = _create_user(db_session, role="user")
    res_forbidden = client.post(
        f"/api/v1/admin/movies/{movie.id}/enrichment/start",
        headers=user_headers,
    )
    assert res_forbidden.status_code == 403


def test_full_admin_enrichment_approval_and_application_preserves_protected_fields(
    client, db_session
):
    admin, admin_headers = _create_user(db_session, role="admin")
    viewer, _ = _create_user(db_session, role="user")

    movie = Movie(
        id=uuid4(),
        title="The Shawshank Redemption 1994 - Nhà tù Shawshank 1994",
        overview="Manual custom overview we want to keep",
        release_date=date(1994, 1, 1),
        genres=["Drama"],
        cast=[],
        keywords=[],
        director="Frank Darabont",
        video_source_path="media/videos/source/shawshank.mp4",
        source_storage="r2",
        source_object_key="movies/shawshank/source.mp4",
        hls_playlist_path="media/videos/hls/shawshank/master.m3u8",
        processing_status="ready",
    )
    db_session.add(movie)
    db_session.flush()

    # Add user interactions to ensure they are untouched
    db_session.add(Rating(user_id=viewer.id, movie_id=movie.id, rating=5))
    db_session.add(UserFavorite(user_id=viewer.id, movie_id=movie.id))
    db_session.add(
        WatchHistory(
            user_id=viewer.id,
            movie_id=movie.id,
            playback_position_seconds=420,
            progress_percent=50,
        )
    )
    db_session.commit()

    with patch(
        "app.services.metadata_staging_service.TMDBClient",
        return_value=_FakeTMDBClient(),
    ):
        start_res = client.post(
            f"/api/v1/admin/movies/{movie.id}/enrichment/start",
            json={"source_language": "en-US", "include_vi_localization": True},
            headers=admin_headers,
        )
    assert start_res.status_code == 201
    job_data = start_res.json()
    job_id = job_data["id"]
    assert job_data["status"] == "awaiting_review"
    assert len(job_data["candidates"]) == 2

    top_candidate = job_data["candidates"][0]
    assert top_candidate["provider_movie_id"] == "278"

    # Attempt to approve `overview` without `allow_overwrite_existing=True` -> 409
    conflict_res = client.post(
        f"/api/v1/admin/enrichment/jobs/{job_id}/approve",
        json={
            "candidate_id": top_candidate["id"],
            "approved_fields": ["overview", "cast"],
            "allow_overwrite_existing": False,
        },
        headers=admin_headers,
    )
    assert conflict_res.status_code == 409
    assert conflict_res.json()["code"] == "enrichment_validation_failed"

    # Approve missing fields (`cast`, `keywords`, `title_vi`, `overview_vi`, `tmdb_id`, `imdb_id`, `poster_path`)
    # while leaving `overview` and `title` unapproved so manual values stay intact
    approve_res = client.post(
        f"/api/v1/admin/enrichment/jobs/{job_id}/approve",
        json={
            "candidate_id": top_candidate["id"],
            "approved_fields": [
                "cast",
                "keywords",
                "title_vi",
                "overview_vi",
                "tmdb_id",
                "imdb_id",
                "poster_path",
            ],
            "allow_overwrite_existing": False,
            "expected_metadata_version": 1,
            "apply_immediately": True,
            "notes": "Approve missing cast, keywords, VI localization, and IDs.",
        },
        headers=admin_headers,
    )
    assert approve_res.status_code == 200
    applied_job = approve_res.json()
    assert applied_job["status"] == "applied"
    assert applied_job["application_status"] == "applied"
    assert applied_job["movie_metadata_version"] == 2
    assert len(applied_job["provenances"]) == 7

    # Verify DB state on Movie
    db_session.expire_all()
    updated_movie = db_session.query(Movie).filter(Movie.id == movie.id).first()
    assert updated_movie.metadata_version == 2
    assert updated_movie.cast == ["Tim Robbins", "Morgan Freeman", "Bob Gunton"]
    assert updated_movie.keywords == ["prison", "wrongful imprisonment", "hope"]
    assert updated_movie.title_vi == "Nhà Tù Shawshank"
    assert "Shawshank" in (updated_movie.overview_vi or "")
    assert updated_movie.tmdb_id == 278
    assert updated_movie.imdb_id == "tt0111161"
    # Manual overview & title were not in approved_fields -> untouched!
    assert updated_movie.overview == "Manual custom overview we want to keep"
    assert updated_movie.title == "The Shawshank Redemption 1994 - Nhà tù Shawshank 1994"
    # Protected media / R2 / HLS fields -> untouched!
    assert updated_movie.video_source_path == "media/videos/source/shawshank.mp4"
    assert updated_movie.source_storage == "r2"
    assert updated_movie.source_object_key == "movies/shawshank/source.mp4"
    assert updated_movie.hls_playlist_path == "media/videos/hls/shawshank/master.m3u8"
    assert updated_movie.processing_status == "ready"
    # TMDB attribution & MovieAsset created
    assert updated_movie.source_name == "TMDB"
    assert "TMDB API" in (updated_movie.attribution or "")
    poster_asset = (
        db_session.query(MovieAsset)
        .filter(MovieAsset.movie_id == movie.id, MovieAsset.asset_type == "poster")
        .first()
    )
    assert poster_asset is not None
    assert poster_asset.source_name == "TMDB"
    assert poster_asset.media_rights_status == "attribution_required"

    # User interactions untouched
    assert db_session.query(Rating).filter(Rating.movie_id == movie.id).count() == 1
    assert db_session.query(UserFavorite).filter(UserFavorite.movie_id == movie.id).count() == 1
    assert db_session.query(WatchHistory).filter(WatchHistory.movie_id == movie.id).count() == 1

    # Idempotent repeated approval & application calls
    repeat_approve = client.post(
        f"/api/v1/admin/enrichment/jobs/{job_id}/approve",
        json={
            "candidate_id": top_candidate["id"],
            "approved_fields": [
                "cast",
                "keywords",
                "title_vi",
                "overview_vi",
                "tmdb_id",
                "imdb_id",
                "poster_path",
            ],
            "apply_immediately": True,
        },
        headers=admin_headers,
    )
    assert repeat_approve.status_code == 200

    repeat_apply = client.post(
        f"/api/v1/admin/enrichment/jobs/{job_id}/apply",
        json={"expected_metadata_version": 2},
        headers=admin_headers,
    )
    assert repeat_apply.status_code == 200

    db_session.expire_all()
    assert db_session.query(Movie).filter(Movie.id == movie.id).first().metadata_version == 2
    assert (
        db_session.query(MetadataFieldProvenance)
        .filter(MetadataFieldProvenance.job_id == UUID(applied_job["id"]))
        .count()
        == 7
    )
    assert (
        db_session.query(AdminAuditLog)
        .filter(AdminAuditLog.action_type == "movie_metadata_enrichment_apply")
        .count()
        == 1
    )


def test_concurrent_review_conflict_and_rejection_workflow(client, db_session):
    _, admin_headers = _create_user(db_session, role="admin")
    movie = Movie(
        id=uuid4(),
        title="The Shawshank Redemption",
        release_date=date(1994, 9, 23),
        metadata_version=3,
    )
    db_session.add(movie)
    db_session.commit()

    with patch(
        "app.services.metadata_staging_service.TMDBClient",
        return_value=_FakeTMDBClient(),
    ):
        start_res = client.post(
            f"/api/v1/admin/movies/{movie.id}/enrichment/start",
            headers=admin_headers,
        )
    assert start_res.status_code == 201
    job_data = start_res.json()
    job_id = job_data["id"]
    cand_id = job_data["candidates"][0]["id"]

    # Select second candidate explicitly
    second_cand_id = job_data["candidates"][1]["id"]
    sel_res = client.post(
        f"/api/v1/admin/enrichment/jobs/{job_id}/select-candidate",
        json={"candidate_id": second_cand_id, "notes": "Inspecting second candidate"},
        headers=admin_headers,
    )
    assert sel_res.status_code == 200
    assert sel_res.json()["selected_candidate_id"] == second_cand_id

    # Stale expected_metadata_version (passing 1 when Movie is at version 3) -> 409
    stale_res = client.post(
        f"/api/v1/admin/enrichment/jobs/{job_id}/approve",
        json={
            "candidate_id": cand_id,
            "approved_fields": ["cast"],
            "expected_metadata_version": 1,
            "apply_immediately": True,
        },
        headers=admin_headers,
    )
    assert stale_res.status_code == 409
    assert stale_res.json()["code"] == "enrichment_concurrent_modification"

    # Reject the job -> releases active_lock
    reject_res = client.post(
        f"/api/v1/admin/enrichment/jobs/{job_id}/reject",
        json={"reason": "Admin decided to reject candidate batch."},
        headers=admin_headers,
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"

    # Movie remains at version 3 and a new enrichment job can now be started
    db_session.expire_all()
    assert db_session.query(Movie).filter(Movie.id == movie.id).first().metadata_version == 3

    with patch(
        "app.services.metadata_staging_service.TMDBClient",
        return_value=_FakeTMDBClient(),
    ):
        restart_res = client.post(
            f"/api/v1/admin/movies/{movie.id}/enrichment/start",
            headers=admin_headers,
        )
    assert restart_res.status_code == 201


def test_transaction_rollback_on_database_failure_during_application(client, db_session):
    _, admin_headers = _create_user(db_session, role="admin")
    movie = Movie(
        id=uuid4(),
        title="The Shawshank Redemption",
        release_date=date(1994, 1, 1),
        cast=[],
        metadata_version=1,
    )
    db_session.add(movie)
    db_session.commit()

    with patch(
        "app.services.metadata_staging_service.TMDBClient",
        return_value=_FakeTMDBClient(),
    ):
        start_res = client.post(
            f"/api/v1/admin/movies/{movie.id}/enrichment/start",
            headers=admin_headers,
        )
    job_data = start_res.json()
    job_id = job_data["id"]
    cand_id = job_data["candidates"][0]["id"]

    # Approve without immediate apply
    approve_res = client.post(
        f"/api/v1/admin/enrichment/jobs/{job_id}/approve",
        json={
            "candidate_id": cand_id,
            "approved_fields": ["cast", "keywords"],
            "apply_immediately": False,
        },
        headers=admin_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "partially_approved"

    # Simulate database failure when creating AdminAuditLog during apply_approved_metadata
    with patch(
        "app.services.metadata_application_service.AdminAuditLog",
        side_effect=SQLAlchemyError("Simulated DB failure on audit log insert"),
    ):
        apply_res = client.post(
            f"/api/v1/admin/enrichment/jobs/{job_id}/apply",
            json={"expected_metadata_version": 1},
            headers=admin_headers,
        )
    assert apply_res.status_code == 500
    assert apply_res.json()["code"] == "enrichment_application_failed"

    # Verify rollback: Movie was NOT partially updated and metadata_version is still 1
    db_session.expire_all()
    rolled_back_movie = db_session.query(Movie).filter(Movie.id == movie.id).first()
    assert rolled_back_movie.metadata_version == 1
    assert rolled_back_movie.cast == []
    assert (
        db_session.query(MetadataFieldProvenance)
        .filter(MetadataFieldProvenance.movie_id == movie.id)
        .count()
        == 0
    )


def test_recommendation_cache_refresh_and_updated_tfidf_ranking_after_enrichment(
    client, db_session
):
    _, admin_headers = _create_user(db_session, role="admin")
    viewer, _ = _create_user(db_session, role="user")

    # Anchor movie rated 5 stars by user: prison drama by Frank Darabont with Morgan Freeman
    anchor_movie = Movie(
        id=uuid4(),
        title="The Green Mile",
        overview="A prison guard discovers a death row inmate possesses miraculous powers inside a penitentiary.",
        release_date=date(1999, 12, 10),
        genres=["Drama", "Crime"],
        cast=["Tom Hanks", "Morgan Freeman"],
        keywords=["prison", "wrongful imprisonment", "hope"],
        director="Frank Darabont",
        processing_status="ready",
    )
    # Distractor movie: romantic comedy with slight overlap on word 'story'
    distractor_movie = Movie(
        id=uuid4(),
        title="Summer Bakery Romance",
        overview="A chef opens a bakery in Paris and falls in love during a summer festival.",
        release_date=date(2020, 6, 1),
        genres=["Romance", "Comedy"],
        cast=["Actor One", "Actor Two"],
        keywords=["bakery", "paris", "romance"],
        director="Jane Doe",
        processing_status="ready",
    )
    # Target movie BEFORE enrichment: missing cast, keywords, director, and genres
    target_movie = Movie(
        id=uuid4(),
        title="The Shawshank Redemption",
        overview="Placeholder text",
        release_date=date(1994, 1, 1),
        genres=[],
        cast=[],
        keywords=[],
        director=None,
        processing_status="ready",
    )
    db_session.add_all([anchor_movie, distractor_movie, target_movie])
    db_session.flush()
    db_session.add(Rating(user_id=viewer.id, movie_id=anchor_movie.id, rating=5))
    db_session.commit()

    # Warm the TF-IDF cache BEFORE enrichment
    get_movie_vectors(db_session)
    stats_before = get_cache_stats()
    assert stats_before["is_populated"] is True
    gen_before = stats_before["cache_generation"]
    inv_before = stats_before["invalidation_count"]

    # Stage & apply TMDB enrichment for target_movie
    with patch(
        "app.services.metadata_staging_service.TMDBClient",
        return_value=_FakeTMDBClient(),
    ):
        start_res = client.post(
            f"/api/v1/admin/movies/{target_movie.id}/enrichment/start",
            headers=admin_headers,
        )
    job_data = start_res.json()
    job_id = job_data["id"]
    cand_id = job_data["candidates"][0]["id"]

    approve_res = client.post(
        f"/api/v1/admin/enrichment/jobs/{job_id}/approve",
        json={
            "candidate_id": cand_id,
            "approved_fields": ["overview", "genres", "cast", "keywords", "director"],
            "allow_overwrite_existing": True,
            "apply_immediately": True,
        },
        headers=admin_headers,
    )
    assert approve_res.status_code == 200

    # Cache must have been invalidated immediately upon commit
    stats_after_apply = get_cache_stats()
    assert stats_after_apply[" is_populated" if False else "is_populated"] is False
    assert stats_after_apply["invalidation_count"] > inv_before

    # Requesting recommendations now rebuilds the TF-IDF matrix with the enriched profile
    rec_result = get_recommendations(db_session, viewer.id, top_n=5)
    stats_after_rec = get_cache_stats()
    assert stats_after_rec["is_populated"] is True
    assert stats_after_rec["cache_generation"] > gen_before

    rec_items = rec_result
    assert len(rec_items) >= 1
    assert str(rec_items[0]["id"]) == str(target_movie.id)
