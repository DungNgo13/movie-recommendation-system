"""Tests for user profile endpoints: avatar upload and password change flow."""

import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, create_short_lived_token, hash_password


client = TestClient(app)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _auth_headers(user_id: str = "00000000-0000-0000-0000-000000000001") -> dict:
    """Create a valid JWT Authorization header for testing."""
    token = create_access_token(data={"sub": user_id})
    return {"Authorization": f"Bearer {token}"}


def _make_fake_user(**overrides):
    """Create a mock User object with sensible defaults."""
    user = MagicMock()
    user.id = overrides.get("id", "00000000-0000-0000-0000-000000000001")
    user.email = overrides.get("email", "test@example.com")
    user.password_hash = overrides.get(
        "password_hash", hash_password("OldPass123!")
    )
    user.role = overrides.get("role", "user")
    user.status = overrides.get("status", "active")
    user.avatar_path = overrides.get("avatar_path", None)
    user.created_at = overrides.get("created_at", "2026-01-01T00:00:00")
    user.last_login_at = overrides.get("last_login_at", None)
    user.failed_login_attempts = overrides.get("failed_login_attempts", 0)
    return user


# ─── Avatar Upload Tests ─────────────────────────────────────────────────────


class TestAvatarUpload:

    @patch("app.routers.auth.get_current_user")
    @patch("app.services.avatar_service.upload_avatar")
    def test_upload_valid_avatar(self, mock_upload, mock_auth):
        """A valid JPEG upload should succeed."""
        fake_user = _make_fake_user()
        mock_auth.return_value = fake_user
        mock_upload.return_value = fake_user

        file_data = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        response = client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("avatar.jpg", file_data, "image/jpeg")},
            headers=_auth_headers(),
        )
        assert response.status_code == 200

    @patch("app.routers.auth.get_current_user")
    def test_upload_invalid_type_rejected(self, mock_auth):
        """A non-image file type should be rejected with 400."""
        mock_auth.return_value = _make_fake_user()

        file_data = io.BytesIO(b"not an image")
        response = client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("avatar.txt", file_data, "text/plain")},
            headers=_auth_headers(),
        )
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    @patch("app.routers.auth.get_current_user")
    def test_upload_oversized_file_rejected(self, mock_auth):
        """A file larger than 2 MB should be rejected with 400."""
        mock_auth.return_value = _make_fake_user()

        # 2 MB + 1 byte
        big_data = io.BytesIO(b"\x00" * (2 * 1024 * 1024 + 1))
        response = client.post(
            "/api/v1/users/me/avatar",
            files={"file": ("big.jpg", big_data, "image/jpeg")},
            headers=_auth_headers(),
        )
        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()


# ─── Password Change Request Tests ───────────────────────────────────────────


class TestChangePasswordRequest:

    @patch("app.routers.auth.get_current_user")
    @patch("app.services.mail_service.send_password_change_email")
    def test_valid_request(self, mock_mail, mock_auth):
        """A valid current + strong new password should trigger a confirmation email."""
        mock_auth.return_value = _make_fake_user()
        response = client.post(
            "/api/v1/auth/change-password-request",
            json={
                "current_password": "OldPass123!",
                "new_password": "NewStr0ng!Pass",
            },
            headers=_auth_headers(),
        )
        assert response.status_code == 200
        assert "Confirmation email sent" in response.json()["message"]
        mock_mail.assert_called_once()

    @patch("app.routers.auth.get_current_user")
    def test_wrong_current_password(self, mock_auth):
        """Wrong current password should return 400."""
        mock_auth.return_value = _make_fake_user()
        response = client.post(
            "/api/v1/auth/change-password-request",
            json={
                "current_password": "WrongPass1!",
                "new_password": "NewStr0ng!Pass",
            },
            headers=_auth_headers(),
        )
        assert response.status_code == 400

    def test_weak_new_password_rejected(self):
        """A weak new password should fail Pydantic validation (422)."""
        response = client.post(
            "/api/v1/auth/change-password-request",
            json={
                "current_password": "anything",
                "new_password": "weak",  # fails complexity
            },
            headers=_auth_headers(),
        )
        assert response.status_code == 422


# ─── Password Change Confirm Tests ───────────────────────────────────────────


class TestChangePasswordConfirm:

    @patch("app.services.auth_service.get_user_by_id")
    @patch("app.services.auth_service.change_password")
    def test_valid_confirmation(self, mock_change, mock_get_user):
        """A valid, non-expired token should apply the password change."""
        fake_user = _make_fake_user()
        mock_get_user.return_value = fake_user

        token = create_short_lived_token(
            data={
                "sub": str(fake_user.id),
                "purpose": "change_password",
                "new_hash": hash_password("NewStr0ng!Pass"),
            },
            expire_minutes=15,
        )
        response = client.post(
            "/api/v1/auth/change-password-confirm",
            json={"token": token},
        )
        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()
        mock_change.assert_called_once()

    def test_expired_token(self):
        """An expired token should be rejected."""
        token = create_short_lived_token(
            data={
                "sub": "00000000-0000-0000-0000-000000000001",
                "purpose": "change_password",
                "new_hash": "fakehash",
            },
            expire_minutes=-1,  # Already expired
        )
        response = client.post(
            "/api/v1/auth/change-password-confirm",
            json={"token": token},
        )
        assert response.status_code == 400

    def test_wrong_purpose_token(self):
        """A token with wrong purpose should be rejected."""
        token = create_short_lived_token(
            data={
                "sub": "00000000-0000-0000-0000-000000000001",
                "purpose": "wrong_purpose",
                "new_hash": "fakehash",
            },
            expire_minutes=15,
        )
        response = client.post(
            "/api/v1/auth/change-password-confirm",
            json={"token": token},
        )
        assert response.status_code == 400
        assert "purpose" in response.json()["detail"].lower()
