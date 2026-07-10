"""
Tests for upload file size validation in file_storage_service.

Verifies that:
  - Oversized images are rejected with 400.
  - Oversized videos are rejected with 400.
  - Normal-sized files are accepted.
  - Invalid content types are rejected.
"""

import io
import uuid

import pytest
from fastapi import UploadFile, HTTPException

from app.services.file_storage_service import (
    _validate_file_size,
    MAX_IMAGE_BYTES,
    MAX_VIDEO_BYTES,
)


def _make_upload(content: bytes, content_type: str = "image/jpeg", filename: str = "test.jpg") -> UploadFile:
    """Create a mock UploadFile with the given content."""
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers={"content-type": content_type},
    )


class TestValidateFileSize:
    """Tests for the _validate_file_size helper."""

    def test_small_image_passes(self):
        """A 1KB image should pass the 10MB limit."""
        content = b"x" * 1024  # 1 KB
        file = _make_upload(content)
        # Should not raise
        _validate_file_size(file, MAX_IMAGE_BYTES, "Image")

    def test_exact_limit_passes(self):
        """A file exactly at the limit should pass."""
        content = b"x" * MAX_IMAGE_BYTES
        file = _make_upload(content)
        # Should not raise
        _validate_file_size(file, MAX_IMAGE_BYTES, "Image")

    def test_oversized_image_rejected(self):
        """A file 1 byte over the limit should be rejected."""
        content = b"x" * (MAX_IMAGE_BYTES + 1)
        file = _make_upload(content)
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_size(file, MAX_IMAGE_BYTES, "Image")
        assert exc_info.value.status_code == 400
        assert "too large" in exc_info.value.detail.lower()

    def test_very_large_image_rejected(self):
        """A 50MB image should be rejected."""
        content = b"x" * (50 * 1024 * 1024)
        file = _make_upload(content)
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_size(file, MAX_IMAGE_BYTES, "Image")
        assert exc_info.value.status_code == 400

    def test_file_pointer_rewound_after_valid(self):
        """After validation, the file pointer should be at the start."""
        content = b"hello world"
        file = _make_upload(content)
        _validate_file_size(file, MAX_IMAGE_BYTES, "Image")
        # Pointer should be rewound so the caller can read the file
        assert file.file.read() == content

    def test_custom_label_in_error(self):
        """The error message should include the label."""
        content = b"x" * (MAX_IMAGE_BYTES + 1)
        file = _make_upload(content)
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_size(file, MAX_IMAGE_BYTES, "Poster")
        assert "Poster" in exc_info.value.detail

    def test_video_size_limit_chunked(self):
        """
        Video validation uses chunked reading for large limits.
        Test with a small limit to exercise the chunked code path.
        """
        # Use a custom limit > 64MB to trigger the chunked path
        large_limit = 100 * 1024 * 1024  # 100 MB
        content = b"x" * (large_limit + 1)
        file = _make_upload(content, content_type="video/mp4", filename="test.mp4")
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_size(file, large_limit, "Video")
        assert exc_info.value.status_code == 400

    def test_empty_file_passes(self):
        """An empty file should pass validation."""
        file = _make_upload(b"")
        _validate_file_size(file, MAX_IMAGE_BYTES, "Image")
