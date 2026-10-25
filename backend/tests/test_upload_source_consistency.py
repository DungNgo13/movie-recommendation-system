"""
Phase 1.5 regression tests: local ↔ R2 source consistency and concurrent
completion.

Isolation: in-memory SQLite (StaticPool) for API tests, a throwaway file
SQLite in pytest's tmp_path for the multi-threaded test, botocore Stubber /
fake storage for R2.  No network access.  Local uploads write under the
process CWD's media/ directory (the test runner uses a scratch CWD).
"""

import os
import sys
import threading
import uuid
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from botocore.stub import Stubber
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.movie import Movie
from app.models.upload_session import UploadSession
from app.models.user import User
from app.routers.auth import get_current_admin_user
from app.schemas.upload_session import UploadSessionCreateSchema
from app.services import upload_session_service
from app.services.r2_storage_service import (
    R2ObjectInfo,
    R2Settings,
    R2StorageService,
    get_optional_r2_storage,
    get_r2_storage,
)

BUCKET = "movsug-consistency-test-bucket"

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
    user = User(id=uuid.uuid4(), email="admin@consistency.test", password_hash="x", role="admin")
    db.add(user)
    db.commit()
    db.refresh(user)
    app.dependency_overrides[get_current_admin_user] = lambda: user
    return user


@pytest.fixture
def movie(db):
    m = Movie(id=uuid.uuid4(), title="Consistency Movie")
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture
def r2():
    service = R2StorageService(R2Settings(
        endpoint_url="https://consistency-test.r2.cloudflarestorage.com",
        bucket_name=BUCKET,
        access_key_id="FAKEACCESSKEYID",
        secret_access_key="FAKE-SECRET",
        max_upload_bytes=10_000_000,
    ))
    stubber = Stubber(service.client)
    stubber.activate()
    app.dependency_overrides[get_r2_storage] = lambda: service
    app.dependency_overrides[get_optional_r2_storage] = lambda: service
    yield service, stubber
    stubber.assert_no_pending_responses()
    stubber.deactivate()


def _fresh_movie(db, movie_id) -> Movie:
    db.expire_all()
    return db.query(Movie).filter(Movie.id == movie_id).one()


def _local_upload(movie_id, content_type="video/mp4", name="clip.mp4"):
    files = {"file": (name, b"\x00\x00\x00\x18ftypmp42fake", content_type)}
    return client.post(f"/api/v1/movies/{movie_id}/video", files=files)


def _r2_upload(db, stubber, movie_id, size=2048, actual_size=None):
    resp = client.post(
        f"/api/v1/admin/movies/{movie_id}/uploads",
        json={"filename": "r2.mp4", "content_type": "video/mp4", "size": size},
    )
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["session"]["id"]
    db.expire_all()
    key = db.query(UploadSession).filter(UploadSession.id == uuid.UUID(session_id)).one().object_key
    stubber.add_response(
        "head_object",
        {"ContentLength": actual_size or size, "ContentType": "video/mp4", "ETag": '"e"'},
        {"Bucket": BUCKET, "Key": key},
    )
    done = client.post(f"/api/v1/admin/movies/{movie_id}/uploads/{session_id}/complete")
    return done, key


# ── local → R2 ────────────────────────────────────────────────────────────────

def test_local_then_r2_switches_active_source_and_keeps_local_fields(db, admin, movie, r2):
    _, stubber = r2
    assert _local_upload(movie.id).status_code == 200
    local = _fresh_movie(db, movie.id)
    local_path, status = local.video_source_path, local.processing_status
    assert local.source_storage == "local" and local.source_object_key is None

    done, key = _r2_upload(db, stubber, movie.id)
    assert done.status_code == 200

    m = _fresh_movie(db, movie.id)
    assert m.source_storage == "r2"
    assert m.source_object_key == key
    # Existing local/HLS behaviour preserved until the R2 resolver exists.
    assert m.video_source_path == local_path
    assert m.processing_status == status


def test_local_then_failed_r2_keeps_local_source(db, admin, movie, r2):
    _, stubber = r2
    assert _local_upload(movie.id).status_code == 200
    local_path = _fresh_movie(db, movie.id).video_source_path

    done, _ = _r2_upload(db, stubber, movie.id, size=2048, actual_size=1)
    assert done.status_code == 422

    m = _fresh_movie(db, movie.id)
    assert m.source_storage == "local"
    assert m.source_object_key is None
    assert m.video_source_path == local_path


# ── R2 → local ────────────────────────────────────────────────────────────────

def test_r2_then_local_clears_r2_reference(db, admin, movie, r2):
    _, stubber = r2
    done, _ = _r2_upload(db, stubber, movie.id)
    assert done.status_code == 200
    assert _fresh_movie(db, movie.id).source_storage == "r2"

    resp = _local_upload(movie.id)
    assert resp.status_code == 200

    m = _fresh_movie(db, movie.id)
    assert m.source_storage == "local"
    assert m.source_object_key is None
    assert m.video_source_path and m.video_source_path.startswith("media/videos/source/")
    assert m.processing_status == "uploaded"


def test_r2_then_failed_local_upload_keeps_r2_reference(db, admin, movie, r2):
    _, stubber = r2
    done, key = _r2_upload(db, stubber, movie.id)
    assert done.status_code == 200

    resp = _local_upload(movie.id, content_type="text/plain", name="notes.txt")
    assert resp.status_code == 400

    m = _fresh_movie(db, movie.id)
    assert m.source_storage == "r2"
    assert m.source_object_key == key


def test_second_r2_upload_replaces_key(db, admin, movie, r2):
    _, stubber = r2
    _, first_key = _r2_upload(db, stubber, movie.id)
    done, second_key = _r2_upload(db, stubber, movie.id)
    assert done.status_code == 200
    assert first_key != second_key
    assert _fresh_movie(db, movie.id).source_object_key == second_key


# ── No public exposure of the R2 source ───────────────────────────────────────

def test_public_movie_endpoints_do_not_expose_r2_source(db, admin, movie, r2):
    _, stubber = r2
    _, key = _r2_upload(db, stubber, movie.id)

    for url in (f"/api/v1/movies/{movie.id}", "/api/v1/movies"):
        body = client.get(url).text
        assert key not in body
        assert "source_object_key" not in body
        assert "source_storage" not in body
        assert BUCKET not in body
        assert "r2.cloudflarestorage.com" not in body


# ── Real concurrent completion (two threads, two DB connections) ─────────────

class _BarrierStorage:
    """Fake storage: both callers pass HeadObject before either finalizes."""

    def __init__(self, size: int):
        self.size = size
        self.calls = 0
        self._lock = threading.Lock()
        self.barrier = threading.Barrier(2, timeout=10)

    def head_object(self, key):
        with self._lock:
            self.calls += 1
        self.barrier.wait()
        return R2ObjectInfo(size=self.size, content_type="video/mp4", etag="etag")


def test_concurrent_completion_transitions_exactly_once(tmp_path):
    file_engine = create_engine(
        f"sqlite:///{(tmp_path / 'concurrency.db').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    Base.metadata.create_all(bind=file_engine)
    Factory = sessionmaker(autocommit=False, autoflush=False, bind=file_engine)

    setup = Factory()
    owner = User(id=uuid.uuid4(), email="race@test.com", password_hash="x", role="admin")
    target = Movie(id=uuid.uuid4(), title="Race")
    setup.add_all([owner, target])
    setup.commit()
    stub_presigner = SimpleNamespace(
        settings=SimpleNamespace(max_upload_bytes=10_000, presign_expires_seconds=900),
        presign_put=lambda key, ctype, exp: "https://example.invalid/presigned",
    )
    session, _ = upload_session_service.create_upload_session(
        setup, stub_presigner, target.id, owner,
        UploadSessionCreateSchema(filename="r.mp4", content_type="video/mp4", size=100),
    )
    session_id, movie_id = session.id, target.id
    acting_user = SimpleNamespace(id=owner.id)
    setup.close()

    storage = _BarrierStorage(size=100)
    results, errors = [], []

    def worker():
        db = Factory()
        try:
            results.append(upload_session_service.complete_upload_session(
                db, storage, movie_id, session_id, acting_user))
        except HTTPException as exc:  # pragma: no cover - reported below
            errors.append(exc)
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert errors == []
    assert storage.calls == 2                       # both really raced past HeadObject
    assert sorted(r.newly_completed for r in results) == [False, True]

    check = Factory()
    row = check.query(UploadSession).filter(UploadSession.id == session_id).one()
    assert row.status == "completed"
    assert check.query(Movie).filter(Movie.id == movie_id).one().source_object_key == row.object_key
    check.close()
    file_engine.dispose()
