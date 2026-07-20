"""
Tests for password-reset email URL construction, template rendering,
and multipart email structure.

Covers:
- URL uses FRONTEND_URL (not BACKEND_URL or hardcoded IP)
- Token is URL-encoded
- Trailing slash handling
- Multipart text/plain + text/html
- No internal IPs in rendered email
- Expiry text matches real configuration
- Subject line
- Email address not displayed in full
"""
import os
import re
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from unittest.mock import patch, MagicMock

import pytest

# Must be imported before mail_service to control FRONTEND_URL
os.environ.setdefault("FRONTEND_URL", "https://tltn.laetus.io.vn")

from app.services.mail_service import (
    build_frontend_url,
    format_expiry_text,
    send_password_reset_email,
    FRONTEND_URL,
)
from app.services.auth_service import PASSWORD_RESET_TOKEN_EXPIRE_MINUTES


# ─── build_frontend_url ──────────────────────────────────────────────────────


class TestBuildFrontendUrl:
    """Unit tests for the URL construction helper."""

    def test_basic_url(self):
        with patch("app.services.mail_service.FRONTEND_URL", "https://example.com"):
            url = build_frontend_url("reset-password", token="abc123")
        assert url == "https://example.com/reset-password?token=abc123"

    def test_trailing_slash_no_double_slash(self):
        with patch("app.services.mail_service.FRONTEND_URL", "https://example.com/"):
            url = build_frontend_url("reset-password", token="abc")
        assert "//reset-password" not in url
        assert url.startswith("https://example.com/reset-password")

    def test_leading_slash_in_path(self):
        with patch("app.services.mail_service.FRONTEND_URL", "https://example.com"):
            url = build_frontend_url("/reset-password", token="abc")
        assert "//reset-password" not in url
        assert "/reset-password?token=abc" in url

    def test_token_is_url_encoded(self):
        with patch("app.services.mail_service.FRONTEND_URL", "https://example.com"):
            url = build_frontend_url("reset-password", token="a b+c=d&e")
        # urllib.parse.urlencode encodes special chars
        assert "a+b%2Bc%3Dd%26e" in url or "a%20b%2Bc%3Dd%26e" in url

    def test_whitespace_stripped(self):
        with patch("app.services.mail_service.FRONTEND_URL", "  https://example.com  "):
            url = build_frontend_url("reset-password", token="x")
        assert url.startswith("https://example.com/")

    def test_production_url(self):
        with patch("app.services.mail_service.FRONTEND_URL", "https://tltn.laetus.io.vn"):
            url = build_frontend_url("reset-password", token="tok123")
        assert url == "https://tltn.laetus.io.vn/reset-password?token=tok123"

    def test_matches_frontend_route(self):
        """The path matches the React route defined in App.tsx."""
        with patch("app.services.mail_service.FRONTEND_URL", "https://example.com"):
            url = build_frontend_url("reset-password", token="t")
        assert "/reset-password?" in url


# ─── format_expiry_text ──────────────────────────────────────────────────────


class TestFormatExpiryText:
    """Unit tests for the human-readable expiry formatter."""

    def test_15_minutes(self):
        assert format_expiry_text(15) == "15 minutes"

    def test_1_hour(self):
        assert format_expiry_text(60) == "1 hour"

    def test_2_hours(self):
        assert format_expiry_text(120) == "2 hours"

    def test_90_minutes(self):
        assert format_expiry_text(90) == "90 minutes"

    def test_1_minute(self):
        assert format_expiry_text(1) == "1 minute"

    def test_zero(self):
        assert format_expiry_text(0) == "a few moments"


# ─── send_password_reset_email rendering ─────────────────────────────────────


class TestPasswordResetEmailRendering:
    """Integration tests for the rendered password-reset email."""

    @pytest.fixture(autouse=True)
    def _capture_email(self, monkeypatch):
        """Capture all send_email calls without sending."""
        self.captured: list[dict] = []

        def _capture(to, subject, html_body, text_body=None):
            self.captured.append({
                "to": to,
                "subject": subject,
                "html_body": html_body,
                "text_body": text_body,
            })

        monkeypatch.setattr("app.services.mail_service.send_email", _capture)

    def _send(self, email="user@example.com", token="test-token-abc"):
        send_password_reset_email(email, token)
        assert len(self.captured) == 1
        return self.captured[0]

    def test_html_contains_reset_url(self):
        msg = self._send(token="my-token")
        assert "reset-password?token=my-token" in msg["html_body"]

    def test_plain_text_contains_reset_url(self):
        msg = self._send(token="my-token")
        assert msg["text_body"] is not None
        assert "reset-password?token=my-token" in msg["text_body"]

    def test_both_parts_have_same_url(self):
        msg = self._send(token="same-token")
        # Extract URL from both parts
        url_pattern = r"reset-password\?token=same-token"
        assert re.search(url_pattern, msg["html_body"])
        assert re.search(url_pattern, msg["text_body"])

    def test_html_does_not_contain_internal_ip(self):
        msg = self._send()
        assert "172.35.53.158" not in msg["html_body"]

    def test_text_does_not_contain_internal_ip(self):
        msg = self._send()
        assert "172.35.53.158" not in msg["text_body"]

    def test_html_does_not_contain_localhost(self):
        with patch("app.services.mail_service.FRONTEND_URL", "https://tltn.laetus.io.vn"):
            msg = self._send()
        assert "localhost" not in msg["html_body"]

    def test_html_does_not_contain_127(self):
        with patch("app.services.mail_service.FRONTEND_URL", "https://tltn.laetus.io.vn"):
            msg = self._send()
        assert "127.0.0.1" not in msg["html_body"]

    def test_subject_line(self):
        msg = self._send()
        assert msg["subject"] == "Reset your Laetus password"

    def test_html_contains_cta(self):
        msg = self._send()
        assert "Reset password" in msg["html_body"]

    def test_html_contains_fallback_link(self):
        msg = self._send(token="fallback-tok")
        # Fallback URL appears twice in HTML (href + visible text)
        count = msg["html_body"].count("reset-password?token=fallback-tok")
        assert count >= 2

    def test_email_not_displayed_in_full(self):
        """The recipient's full email should not appear in the rendered email."""
        msg = self._send(email="secret.user@example.com")
        assert "secret.user@example.com" not in msg["html_body"]
        assert "secret.user@example.com" not in (msg["text_body"] or "")

    def test_expiry_text_matches_config(self):
        """The expiry shown in the email must match the real token lifetime."""
        expected_text = format_expiry_text(PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
        msg = self._send()
        assert expected_text in msg["html_body"]
        assert expected_text in msg["text_body"]

    def test_html_has_role_presentation(self):
        """Layout tables should have role='presentation' for accessibility."""
        msg = self._send()
        assert 'role="presentation"' in msg["html_body"]

    def test_html_has_viewport_meta(self):
        msg = self._send()
        assert 'name="viewport"' in msg["html_body"]

    def test_year_is_current(self):
        msg = self._send()
        current_year = str(datetime.now(timezone.utc).year)
        assert current_year in msg["html_body"]
        assert current_year in msg["text_body"]

    def test_url_uses_frontend_url(self):
        """Reset URL uses FRONTEND_URL, not BACKEND_URL."""
        with patch("app.services.mail_service.FRONTEND_URL", "https://my-frontend.test"):
            msg = self._send(token="t")
        assert "https://my-frontend.test/reset-password" in msg["html_body"]
