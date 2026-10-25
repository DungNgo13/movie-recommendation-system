"""
Unit tests for app.services.r2_storage_service.

All S3 calls are intercepted by botocore's Stubber — NO network traffic and
NO live R2 operations.  Credentials below are fake test values.
"""

import io
import logging
import os
import sys
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.services.r2_storage_service import (
    R2_SINGLE_PUT_MAX_BYTES,
    R2NotConfiguredError,
    R2Settings,
    R2StorageError,
    R2StorageService,
)

FAKE_SECRET = "FAKE-SECRET-should-never-appear"
FAKE_ACCESS_KEY = "FAKEACCESSKEYID"
BUCKET = "movsug-unit-test-bucket"
ENDPOINT = "https://unit-test-account.r2.cloudflarestorage.com"
KEY = "sources/movie_x/session_y/token.mp4"


def _settings(**overrides) -> R2Settings:
    values = dict(
        endpoint_url=ENDPOINT,
        bucket_name=BUCKET,
        access_key_id=FAKE_ACCESS_KEY,
        secret_access_key=FAKE_SECRET,
        presign_expires_seconds=900,
        max_upload_bytes=10_000_000,
    )
    values.update(overrides)
    return R2Settings(**values)


@pytest.fixture
def stubbed():
    service = R2StorageService(_settings())
    stubber = Stubber(service.client)
    stubber.activate()
    yield service, stubber
    stubber.assert_no_pending_responses()
    stubber.deactivate()


# ── Settings ──────────────────────────────────────────────────────────────────

def _full_env(**extra):
    env = {
        "R2_ENDPOINT": ENDPOINT,
        "R2_BUCKET_NAME": BUCKET,
        "R2_ACCESS_KEY_ID": FAKE_ACCESS_KEY,
        "R2_SECRET_ACCESS_KEY": FAKE_SECRET,
    }
    env.update(extra)
    return env


def test_settings_from_env_missing_vars_lists_names_only():
    with pytest.raises(R2NotConfiguredError) as exc:
        R2Settings.from_env({"R2_ENDPOINT": ENDPOINT, "R2_SECRET_ACCESS_KEY": FAKE_SECRET})
    assert set(exc.value.missing) == {"R2_ACCESS_KEY_ID", "R2_BUCKET_NAME"}
    assert FAKE_SECRET not in str(exc.value)
    assert ENDPOINT not in str(exc.value)


def test_settings_from_env_blank_values_count_as_missing():
    with pytest.raises(R2NotConfiguredError):
        R2Settings.from_env(_full_env(R2_BUCKET_NAME="   "))


def test_settings_from_env_defaults_and_clamping():
    s = R2Settings.from_env(_full_env())
    assert s.presign_expires_seconds == 900
    assert s.max_upload_bytes == R2_SINGLE_PUT_MAX_BYTES

    s = R2Settings.from_env(_full_env(R2_PRESIGN_EXPIRES_SECONDS="999999",
                                      R2_MAX_UPLOAD_BYTES="99999999999999"))
    assert s.presign_expires_seconds == 3600
    assert s.max_upload_bytes == R2_SINGLE_PUT_MAX_BYTES

    s = R2Settings.from_env(_full_env(R2_PRESIGN_EXPIRES_SECONDS="5"))
    assert s.presign_expires_seconds == 60

    s = R2Settings.from_env(_full_env(R2_PRESIGN_EXPIRES_SECONDS="abc"))
    assert s.presign_expires_seconds == 900


def test_settings_and_service_repr_hide_credentials():
    s = _settings()
    service = R2StorageService(s)
    for text in (repr(s), repr(service)):
        assert FAKE_SECRET not in text
        assert FAKE_ACCESS_KEY not in text


# ── presign_put ───────────────────────────────────────────────────────────────

def test_presign_put_binds_key_content_type_and_expiry():
    service = R2StorageService(_settings())
    url = service.presign_put(KEY, "video/mp4", 600)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert BUCKET in (parsed.netloc + parsed.path)
    assert parsed.path.endswith(KEY)
    assert query["X-Amz-Expires"] == ["600"]
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    # Content-Type is part of the signature → the browser must send it.
    assert "content-type" in query["X-Amz-SignedHeaders"][0].split(";")
    # Secret is never embedded; no extra checksum params the browser can't send.
    assert FAKE_SECRET not in url
    assert not any(k.lower().startswith("x-amz-checksum") for k in query)
    assert not any(k.lower().startswith("x-amz-sdk-checksum") for k in query)


def test_presign_put_uses_default_expiry():
    service = R2StorageService(_settings(presign_expires_seconds=120))
    query = parse_qs(urlparse(service.presign_put(KEY, "video/mp4")).query)
    assert query["X-Amz-Expires"] == ["120"]


# ── head_object ───────────────────────────────────────────────────────────────

def test_head_object_returns_metadata(stubbed):
    service, stubber = stubbed
    stubber.add_response(
        "head_object",
        {"ContentLength": 1234, "ContentType": "video/mp4", "ETag": '"abc123"'},
        {"Bucket": BUCKET, "Key": KEY},
    )
    info = service.head_object(KEY)
    assert info.size == 1234
    assert info.content_type == "video/mp4"
    assert info.etag == "abc123"


@pytest.mark.parametrize("code", ["404", "NoSuchKey", "NotFound"])
def test_head_object_missing_returns_none(stubbed, code):
    service, stubber = stubbed
    stubber.add_client_error("head_object", service_error_code=code, http_status_code=404)
    assert service.head_object(KEY) is None


def test_head_object_other_error_raises_without_secrets(stubbed, caplog):
    service, stubber = stubbed
    stubber.add_client_error("head_object", service_error_code="403", http_status_code=403)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(R2StorageError) as exc:
            service.head_object(KEY)
    assert "403" in str(exc.value)
    assert FAKE_SECRET not in str(exc.value)
    assert FAKE_SECRET not in caplog.text


# ── download_to_path ──────────────────────────────────────────────────────────

def test_download_to_path_writes_file_atomically(stubbed, tmp_path):
    service, stubber = stubbed
    payload = b"fake-video-bytes" * 1000
    stubber.add_response(
        "get_object",
        {"Body": StreamingBody(io.BytesIO(payload), len(payload)), "ContentLength": len(payload)},
        {"Bucket": BUCKET, "Key": KEY},
    )
    dest = tmp_path / "source.mp4"
    written = service.download_to_path(KEY, str(dest))

    assert written == len(payload)
    assert dest.read_bytes() == payload
    assert not (tmp_path / "source.mp4.part").exists()


def test_download_to_path_failure_leaves_no_files(stubbed, tmp_path):
    service, stubber = stubbed
    stubber.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)
    dest = tmp_path / "source.mp4"
    with pytest.raises(R2StorageError):
        service.download_to_path(KEY, str(dest))
    assert list(tmp_path.iterdir()) == []
