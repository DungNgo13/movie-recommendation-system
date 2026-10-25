"""
Tests for direct-to-R2 upload sessions (admin_uploads router +
upload_session_service).

Isolation:
  * In-memory SQLite (StaticPool), fresh schema per test.
  * R2 is replaced by an R2StorageService whose boto3 client is wrapped in
    botocore's Stubber — NO network traffic, NO live R2 operations.
  * Credentials are fake test values.
"""

import logging
import os
import re
import sys
import uuid
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from botocore.stub import Stubber
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.admin_audit_log import AdminAuditLog
from app.models.movie import Movie
from app.models.upload_session import UploadSession
from app.models.user import User
from app.routers.auth import get_current_admin_user, get_current_user
from app.services import upload_session_service
from app.services.r2_storage_service import R2Settings, R2StorageService, get_r2_storage

FAKE_SECRET = "FAKE-SECRET-should-never-appear"
BUCKET = "movsug-api-test-bucket"
MAX_BYTES = 10_000_000

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    app.dependency_overrides.clear()
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


def _user(db, email: str, role: str) -> User:
    user = User(id=uuid.uuid4(), email=email, password_hash="x", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin(db):
    user = _user(db, "admin@test.com", "admin")
    app.dependency_overrides[get_current_admin_user] = lambda: user
    return user


@pytest.fixture
def other_admin(db):
    return _user(db, "other-admin@test.com", "admin")


@pytest.fixture
def movie(db):
    m = Movie(
        id=uuid.uuid4(), title="R2 Test Movie",
        video_source_path="media/videos/source/movie_x/source_old.mp4",
        processing_status="ready",
        hls_playlist_path="media/videos/hls/movie_x/master.m3u8",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture
def r2():
    settings = R2Settings(
        endpoint_url="https://api-test-account.r2.cloudflarestorage.com",
        bucket_name=BUCKET,
        access_key_id="FAKEACCESSKEYID",
        secret_access_key=FAKE_SECRET,
        presign_expires_seconds=900,
        max_upload_bytes=MAX_BYTES,
    )
    service = R2StorageService(settings)
    stubber = Stubber(service.client)
    stubber.activate()
    app.dependency_overrides[get_r2_storage] = lambda: service
    yield service, stubber
    stubber.assert_no_pending_responses()
    stubber.deactivate()


def _create(movie_id, **body):
    payload = {"filename": "trailer.mp4", "content_type": "video/mp4", "size": 2048}
    payload.update(body)
    return client.post(f"/api/v1/admin/movies/{movie_id}/uploads", json=payload)


def _complete(movie_id, session_id):
    return client.post(f"/api/v1/admin/movies/{movie_id}/uploads/{session_id}/complete")


def _stub_head(stubber, key, size=2048, content_type="video/mp4"):
    stubber.add_response(
        "head_object",
        {"ContentLength": size, "ContentType": content_type, "ETag": '"etag-1"'},
        {"Bucket": BUCKET, "Key": key},
    )


def _session_row(db, session_id) -> UploadSession:
    db.expire_all()
    return db.query(UploadSession).filter(UploadSession.id == uuid.UUID(session_id)).one()


KEY_PATTERN = re.compile(
    r"^sources/movie_[0-9a-f-]{36}/[0-9a-f-]{36}/[A-Za-z0-9_-]{24}\.mp4$"
)


# ── Initiation ────────────────────────────────────────────────────────────────

def test_create_upload_session_success(db, admin, movie, r2, caplog):
    with caplog.at_level(logging.DEBUG):
        resp = _create(movie.id)
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["upload_method"] == "PUT"
    assert data["upload_headers"] == {"Content-Type": "video/mp4"}
    assert data["expires_in_seconds"] == 900
    assert data["session"]["status"] == "pending"
    assert data["session"]["expected_size"] == 2048
    assert data["session"]["original_filename"] == "trailer.mp4"
    assert "object_key" not in data["session"]

    row = _session_row(db, data["session"]["id"])
    assert row.created_by_user_id == admin.id
    assert row.movie_id == movie.id
    assert KEY_PATTERN.match(row.object_key), row.object_key
    assert f"movie_{movie.id}" in row.object_key
    assert "trailer" not in row.object_key
    assert row.object_key in data["upload_url"]
    assert FAKE_SECRET not in data["upload_url"]

    # Presigned URL must never be logged or written to the audit log.
    assert data["upload_url"] not in caplog.text
    logs = db.query(AdminAuditLog).all()
    assert len(logs) == 1
    assert "http" not in (logs[0].description or "")


def test_object_keys_are_unique_per_session(db, admin, movie, r2):
    first = _create(movie.id).json()["session"]["id"]
    second = _create(movie.id).json()["session"]["id"]
    assert _session_row(db, first).object_key != _session_row(db, second).object_key


def test_create_upload_movie_not_found(db, admin, r2):
    resp = _create(uuid.uuid4())
    assert resp.status_code == 404
    assert db.query(UploadSession).count() == 0


@pytest.mark.parametrize("body", [
    {"content_type": "application/pdf"},
    {"content_type": "image/png"},
    {"size": 0},
    {"size": -5},
    {"filename": ""},
    {"filename": "../.."},
])
def test_create_upload_rejects_invalid_input(db, admin, movie, r2, body):
    assert _create(movie.id, **body).status_code == 422
    assert db.query(UploadSession).count() == 0


def test_create_upload_rejects_oversized_file(db, admin, movie, r2):
    resp = _create(movie.id, size=MAX_BYTES + 1)
    assert resp.status_code == 400
    assert db.query(UploadSession).count() == 0


def test_create_upload_sanitizes_filename_and_maps_extension(db, admin, movie, r2):
    resp = _create(movie.id, filename="..\\..\\secret/evil.MKV", content_type="Video/X-Matroska")
    assert resp.status_code == 201
    row = _session_row(db, resp.json()["session"]["id"])
    assert row.original_filename == "evil.MKV"
    assert row.content_type == "video/x-matroska"
    assert row.object_key.endswith(".mkv")
    assert ".." not in row.object_key


def test_create_upload_requires_admin(db, movie, r2):
    regular = _user(db, "user@test.com", "user")
    app.dependency_overrides[get_current_user] = lambda: regular
    assert _create(movie.id).status_code == 403


def test_create_upload_requires_authentication(db, movie, r2):
    assert _create(movie.id).status_code == 401


def test_create_upload_returns_503_when_r2_not_configured(db, admin, movie, monkeypatch):
    for name in ("R2_ENDPOINT", "R2_BUCKET_NAME", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)
    resp = _create(movie.id)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "R2 storage is not configured."


# ── Completion ────────────────────────────────────────────────────────────────

def test_complete_upload_success_updates_movie_only_storage_fields(db, admin, movie, r2):
    _, stubber = r2
    session_id = _create(movie.id).json()["session"]["id"]
    key = _session_row(db, session_id).object_key
    _stub_head(stubber, key)

    resp = _complete(movie.id, session_id)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["actual_size"] == 2048
    assert data["completed_at"] is not None

    row = _session_row(db, session_id)
    assert row.etag == "etag-1"
    refreshed = db.query(Movie).filter(Movie.id == movie.id).one()
    assert refreshed.source_storage == "r2"
    assert refreshed.source_object_key == key
    # Existing local/HLS fields are untouched.
    assert refreshed.video_source_path == "media/videos/source/movie_x/source_old.mp4"
    assert refreshed.processing_status == "ready"
    assert refreshed.hls_playlist_path == "media/videos/hls/movie_x/master.m3u8"


def test_complete_upload_is_idempotent(db, admin, movie, r2):
    _, stubber = r2
    session_id = _create(movie.id).json()["session"]["id"]
    _stub_head(stubber, _session_row(db, session_id).object_key)  # exactly ONE HeadObject

    first = _complete(movie.id, session_id)
    second = _complete(movie.id, session_id)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()

    completion_logs = [
        log for log in db.query(AdminAuditLog).all()
        if (log.description or "").startswith("Completed R2")
    ]
    assert len(completion_logs) == 1


def test_complete_upload_size_mismatch_marks_failed(db, admin, movie, r2):
    _, stubber = r2
    session_id = _create(movie.id, size=2048).json()["session"]["id"]
    _stub_head(stubber, _session_row(db, session_id).object_key, size=999)

    resp = _complete(movie.id, session_id)
    assert resp.status_code == 422
    row = _session_row(db, session_id)
    assert row.status == "failed"
    assert "does not match" in row.error
    assert db.query(Movie).filter(Movie.id == movie.id).one().source_storage == "local"

    # Terminal: a retry does not re-check storage and reports the state.
    assert _complete(movie.id, session_id).status_code == 409


def test_complete_upload_content_type_mismatch_marks_failed(db, admin, movie, r2):
    _, stubber = r2
    session_id = _create(movie.id).json()["session"]["id"]
    _stub_head(stubber, _session_row(db, session_id).object_key, content_type="text/html")

    assert _complete(movie.id, session_id).status_code == 422
    assert _session_row(db, session_id).status == "failed"


def test_complete_upload_object_missing_is_retryable(db, admin, movie, r2):
    _, stubber = r2
    session_id = _create(movie.id).json()["session"]["id"]
    key = _session_row(db, session_id).object_key
    stubber.add_client_error("head_object", service_error_code="404", http_status_code=404)

    resp = _complete(movie.id, session_id)
    assert resp.status_code == 409
    assert _session_row(db, session_id).status == "pending"

    _stub_head(stubber, key)
    assert _complete(movie.id, session_id).status_code == 200


def test_complete_upload_object_missing_after_expiry_marks_expired(db, admin, movie, r2):
    _, stubber = r2
    session_id = _create(movie.id).json()["session"]["id"]
    row = _session_row(db, session_id)
    row.expires_at = row.created_at - timedelta(seconds=1)
    db.commit()
    stubber.add_client_error("head_object", service_error_code="404", http_status_code=404)

    resp = _complete(movie.id, session_id)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Upload session expired"
    assert _session_row(db, session_id).status == "expired"


def test_complete_upload_storage_error_returns_502_and_stays_pending(db, admin, movie, r2):
    _, stubber = r2
    session_id = _create(movie.id).json()["session"]["id"]
    stubber.add_client_error("head_object", service_error_code="403", http_status_code=403)

    resp = _complete(movie.id, session_id)
    assert resp.status_code == 502
    assert FAKE_SECRET not in resp.text
    assert _session_row(db, session_id).status == "pending"


def test_complete_upload_by_other_admin_is_forbidden(db, admin, other_admin, movie, r2):
    session_id = _create(movie.id).json()["session"]["id"]
    app.dependency_overrides[get_current_admin_user] = lambda: other_admin

    assert _complete(movie.id, session_id).status_code == 403
    assert _session_row(db, session_id).status == "pending"


def test_complete_upload_wrong_movie_or_unknown_session_is_404(db, admin, movie, r2):
    session_id = _create(movie.id).json()["session"]["id"]
    assert _complete(uuid.uuid4(), session_id).status_code == 404
    assert _complete(movie.id, uuid.uuid4()).status_code == 404


def test_complete_upload_requires_admin(db, movie, r2):
    regular = _user(db, "user2@test.com", "user")
    app.dependency_overrides[get_current_user] = lambda: regular
    assert _complete(movie.id, uuid.uuid4()).status_code == 403


# ── Service-level guards ──────────────────────────────────────────────────────

def test_finalize_handles_concurrent_completion(db, admin, movie, r2):
    """If another request completed the session first, _finalize must not fail."""
    service, _ = r2
    from app.schemas.upload_session import UploadSessionCreateSchema

    session, _url = upload_session_service.create_upload_session(
        db, service, movie.id, admin,
        UploadSessionCreateSchema(filename="a.mp4", content_type="video/mp4", size=10),
    )
    # Simulate a concurrent winner flipping the status behind our back.
    db.query(UploadSession).filter(UploadSession.id == session.id).update(
        {"status": "completed"}, synchronize_session=False,
    )
    db.commit()

    result = upload_session_service._finalize(db, session, 10, "etag")
    assert result.status == "completed"


def test_new_movies_default_to_local_storage(db):
    m = Movie(id=uuid.uuid4(), title="Plain")
    db.add(m)
    db.commit()
    db.refresh(m)
    assert m.source_storage == "local"
    assert m.source_object_key is None
