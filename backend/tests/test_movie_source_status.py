"""
Phase 2 finalization tests:

* GET /api/v1/admin/movies/{id}/source — admin-only storage state, no leaks.
* POST /api/v1/movies/{id}/process-hls — refused for R2 sources (409 + code).
* Upload errors carry a stable machine-readable ``code`` while ``detail``
  stays unchanged (backward compatible).

Isolation: in-memory SQLite (StaticPool), botocore Stubber, no network.
"""

import os
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
from app.models.movie import Movie
from app.models.upload_session import UploadSession
from app.models.user import User
from app.routers import movies as movies_router
from app.routers.auth import get_current_admin_user, get_current_user
from app.services.r2_storage_service import (
    R2Settings,
    R2StorageService,
    get_optional_r2_storage,
    get_r2_storage,
)

BUCKET = "movsug-source-status-test-bucket"

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
client = TestClient(app)


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


@pytest.fixture
def admin(db):
    user = User(id=uuid.uuid4(), email="admin@source.test", password_hash="x", role="admin")
    db.add(user)
    db.commit()
    db.refresh(user)
    app.dependency_overrides[get_current_admin_user] = lambda: user
    return user


@pytest.fixture
def movie(db):
    m = Movie(id=uuid.uuid4(), title="Source Status Movie")
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture
def r2():
    service = R2StorageService(R2Settings(
        endpoint_url="https://source-status-test.r2.cloudflarestorage.com",
        bucket_name=BUCKET,
        access_key_id="FAKEACCESSKEYID",
        secret_access_key="FAKE-SECRET",
        max_upload_bytes=10_000_000,
    ), max_attempts=1)
    stubber = Stubber(service.client)
    stubber.activate()
    app.dependency_overrides[get_r2_storage] = lambda: service
    app.dependency_overrides[get_optional_r2_storage] = lambda: service
    yield service, stubber
    stubber.assert_no_pending_responses()
    stubber.deactivate()


def _initiate(movie_id, size=2048):
    resp = client.post(
        f"/api/v1/admin/movies/{movie_id}/uploads",
        json={"filename": "r2.mp4", "content_type": "video/mp4", "size": size},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["session"]["id"]


def _key(db, session_id):
    db.expire_all()
    return db.query(UploadSession).filter(UploadSession.id == uuid.UUID(session_id)).one().object_key


def _complete(movie_id, session_id):
    return client.post(f"/api/v1/admin/movies/{movie_id}/uploads/{session_id}/complete")


def _complete_r2(db, stubber, movie_id, size=2048):
    sid = _initiate(movie_id, size)
    key = _key(db, sid)
    stubber.add_response(
        "head_object",
        {"ContentLength": size, "ContentType": "video/mp4", "ETag": '"e"'},
        {"Bucket": BUCKET, "Key": key},
    )
    assert _complete(movie_id, sid).status_code == 200
    return key


def _source(movie_id):
    return client.get(f"/api/v1/admin/movies/{movie_id}/source")


# ── Source status endpoint ────────────────────────────────────────────────────

def test_source_status_requires_authentication(db, movie):
    assert _source(movie.id).status_code == 401


def test_source_status_forbidden_for_non_admin(db, movie):
    user = User(id=uuid.uuid4(), email="user@source.test", password_hash="x", role="user")
    db.add(user)
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    assert _source(movie.id).status_code == 403


def test_source_status_unknown_movie_is_404_with_code(db, admin):
    resp = _source(uuid.uuid4())
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Movie not found", "code": "movie_not_found"}


def test_source_status_local_without_file(db, admin, movie):
    body = _source(movie.id).json()
    assert body["source_storage"] == "local"
    assert body["source_available"] is False
    assert body["hls_processing_supported"] is True
    assert body["hls_ready"] is False


def test_source_status_local_with_file_on_disk(db, admin, movie, tmp_path):
    clip = tmp_path / "source.mp4"
    clip.write_bytes(b"\x00" * 16)
    movie.video_source_path = str(clip)
    movie.processing_status = "uploaded"
    db.commit()

    body = _source(movie.id).json()
    assert body == {
        "movie_id": str(movie.id),
        "source_storage": "local",
        "source_available": True,
        "processing_status": "uploaded",
        "hls_ready": False,
        "hls_processing_supported": True,
    }


def test_source_status_r2_after_verified_completion(db, admin, movie, r2):
    _, stubber = r2
    key = _complete_r2(db, stubber, movie.id)

    resp = _source(movie.id)
    body = resp.json()
    assert body["source_storage"] == "r2"
    assert body["source_available"] is True
    # In Phase 3, HLS processing is supported for verified R2 sources when configured
    assert body["hls_processing_supported"] is True
    # No private storage details leak.
    assert key not in resp.text
    assert BUCKET not in resp.text
    assert "object_key" not in resp.text and "source_object_key" not in resp.text


def test_source_status_r2_without_completed_session_is_unavailable(db, admin, movie):
    movie.source_storage = "r2"
    movie.source_object_key = "sources/movie_x/y/z.mp4"
    db.commit()
    body = _source(movie.id).json()
    assert body["source_storage"] == "r2"
    assert body["source_available"] is False
    assert body["hls_processing_supported"] is False


def test_public_movie_endpoint_does_not_expose_storage_fields(db, admin, movie, r2):
    _, stubber = r2
    key = _complete_r2(db, stubber, movie.id)
    resp = client.get(f"/api/v1/movies/{movie.id}")
    assert resp.status_code == 200
    assert key not in resp.text
    assert "source_object_key" not in resp.text
    assert "source_storage" not in resp.text


# ── HLS processing ────────────────────────────────────────────────────────────

def test_process_hls_accepts_verified_r2_source(db, admin, movie, r2, monkeypatch):
    _, stubber = r2
    movie.video_source_path = "media/videos/source/stale_local.mp4"  # stale local file
    movie.processing_status = "uploaded"
    db.commit()
    _complete_r2(db, stubber, movie.id)

    queued = []
    monkeypatch.setattr(movies_router, "queue_encode_task", lambda mid: queued.append(mid) or 1)

    resp = client.post(f"/api/v1/movies/{movie.id}/process-hls")
    assert resp.status_code == 202
    assert queued == [movie.id]
    db.expire_all()
    assert db.query(Movie).filter(Movie.id == movie.id).one().processing_status == "processing"


def test_process_hls_still_queues_local_source(db, admin, movie, monkeypatch):
    movie.video_source_path = "media/videos/source/local.mp4"
    movie.processing_status = "uploaded"
    db.commit()
    queued = []
    monkeypatch.setattr(movies_router, "queue_encode_task", lambda mid: queued.append(mid) or 1)

    resp = client.post(f"/api/v1/movies/{movie.id}/process-hls")
    assert resp.status_code == 202
    assert queued == [movie.id]


# ── Machine-readable upload error codes ───────────────────────────────────────

def test_completion_object_missing_has_retryable_code(db, admin, movie, r2):
    _, stubber = r2
    sid = _initiate(movie.id)
    stubber.add_client_error("head_object", service_error_code="404", http_status_code=404,
                             expected_params={"Bucket": BUCKET, "Key": _key(db, sid)})
    resp = _complete(movie.id, sid)
    assert resp.status_code == 409
    assert resp.json() == {
        "detail": "Uploaded object not found. Finish the upload, then retry completion.",
        "code": "upload_object_missing",
    }


def test_completion_expired_has_code(db, admin, movie, r2):
    _, stubber = r2
    sid = _initiate(movie.id)
    session = db.query(UploadSession).filter(UploadSession.id == uuid.UUID(sid)).one()
    session.expires_at = session.created_at - timedelta(seconds=1)
    db.commit()
    stubber.add_client_error("head_object", service_error_code="404", http_status_code=404,
                             expected_params={"Bucket": BUCKET, "Key": session.object_key})
    first = _complete(movie.id, sid)
    assert first.status_code == 409
    assert first.json()["code"] == "upload_session_expired"
    # A replay on the now-expired session keeps the same code (no R2 call).
    replay = _complete(movie.id, sid)
    assert replay.status_code == 409
    assert replay.json() == {"detail": "Upload session is expired", "code": "upload_session_expired"}


def test_completion_mismatch_has_code_and_failed_replay_is_not_pending(db, admin, movie, r2):
    _, stubber = r2
    sid = _initiate(movie.id, size=2048)
    stubber.add_response("head_object", {"ContentLength": 1, "ContentType": "video/mp4", "ETag": '"e"'},
                         {"Bucket": BUCKET, "Key": _key(db, sid)})
    resp = _complete(movie.id, sid)
    assert resp.status_code == 422
    assert resp.json()["code"] == "upload_verification_failed"
    assert "does not match declared size" in resp.json()["detail"]

    replay = _complete(movie.id, sid)
    assert replay.status_code == 409
    assert replay.json()["code"] == "upload_session_not_pending"


def test_completion_storage_error_has_retryable_code(db, admin, movie, r2):
    _, stubber = r2
    sid = _initiate(movie.id)
    stubber.add_client_error("head_object", service_error_code="AccessDenied", http_status_code=403,
                             expected_params={"Bucket": BUCKET, "Key": _key(db, sid)})
    resp = _complete(movie.id, sid)
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Could not verify upload with storage.", "code": "storage_unavailable"}


def test_completion_without_storage_has_code(db, admin, movie, r2):
    sid = _initiate(movie.id)
    app.dependency_overrides[get_optional_r2_storage] = lambda: None
    resp = _complete(movie.id, sid)
    assert resp.status_code == 503
    assert resp.json() == {"detail": "R2 storage is not configured.", "code": "storage_not_configured"}


def test_initiate_codes_for_too_large_and_unknown_movie(db, admin, movie, r2):
    big = client.post(f"/api/v1/admin/movies/{movie.id}/uploads",
                      json={"filename": "a.mp4", "content_type": "video/mp4", "size": 10_000_001})
    assert big.status_code == 400 and big.json()["code"] == "upload_too_large"
    missing = client.post(f"/api/v1/admin/movies/{uuid.uuid4()}/uploads",
                          json={"filename": "a.mp4", "content_type": "video/mp4", "size": 1})
    assert missing.status_code == 404 and missing.json()["code"] == "movie_not_found"


def test_initiate_without_r2_config_has_code(db, admin, movie, monkeypatch):
    for name in ("R2_ENDPOINT", "R2_BUCKET_NAME", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(name, "")
    resp = client.post(f"/api/v1/admin/movies/{movie.id}/uploads",
                       json={"filename": "a.mp4", "content_type": "video/mp4", "size": 1})
    assert resp.status_code == 503
    assert resp.json() == {"detail": "R2 storage is not configured.", "code": "storage_not_configured"}


def test_session_owned_by_other_admin_has_code(db, admin, movie, r2):
    sid = _initiate(movie.id)
    other = User(id=uuid.uuid4(), email="other@source.test", password_hash="x", role="admin")
    db.add(other)
    db.commit()
    app.dependency_overrides[get_current_admin_user] = lambda: other
    resp = _complete(movie.id, sid)
    assert resp.status_code == 403
    assert resp.json()["code"] == "upload_session_forbidden"
