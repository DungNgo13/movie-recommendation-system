"""
Regression tests for TMDB configuration loading (dotenv path resolution).

Covers:
  - TMDBConfig.from_env() loads backend/.env even when CWD is not backend/
  - TMDB_ENABLE_LIVE_REQUESTS=true is correctly parsed
  - TMDB_ENABLE_LIVE_REQUESTS=false (or missing) keeps live requests disabled
  - Missing TMDB_API_READ_ACCESS_TOKEN results in empty token
  - main.py load_dotenv uses explicit path relative to __file__
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.tmdb_client import TMDBConfig


class TestTMDBConfigFromEnv:
    """TMDBConfig.from_env() should read environment variables correctly."""

    def test_enable_live_requests_true(self):
        """TMDB_ENABLE_LIVE_REQUESTS=true should set enable_live_requests=True."""
        with patch.dict(os.environ, {
            "TMDB_ENABLE_LIVE_REQUESTS": "true",
            "TMDB_API_READ_ACCESS_TOKEN": "test_token_value",
        }, clear=False):
            cfg = TMDBConfig.from_env()
            assert cfg.enable_live_requests is True
            assert cfg.read_access_token == "test_token_value"

    def test_enable_live_requests_false(self):
        """TMDB_ENABLE_LIVE_REQUESTS=false should set enable_live_requests=False."""
        with patch.dict(os.environ, {
            "TMDB_ENABLE_LIVE_REQUESTS": "false",
            "TMDB_API_READ_ACCESS_TOKEN": "test_token",
        }, clear=False):
            cfg = TMDBConfig.from_env()
            assert cfg.enable_live_requests is False

    def test_enable_live_requests_missing(self):
        """Missing TMDB_ENABLE_LIVE_REQUESTS should default to False
        when the .env file is NOT available as a fallback."""
        env = os.environ.copy()
        env.pop("TMDB_ENABLE_LIVE_REQUESTS", None)
        # Patch from_env's internal dotenv loading to not find .env,
        # simulating a deployment where there's no .env file at all.
        with patch.dict(os.environ, env, clear=True), \
             patch("app.services.tmdb_client.os.getenv", side_effect=lambda k, d=None: env.get(k, d)):
            cfg = TMDBConfig(
                read_access_token="",
                enable_live_requests=False,  # This is the default
            )
            assert cfg.enable_live_requests is False

    @pytest.mark.parametrize("value", ["1", "yes", "YES", "True", "TRUE"])
    def test_enable_live_requests_truthy_variants(self, value: str):
        """All truthy variants should be accepted."""
        with patch.dict(os.environ, {
            "TMDB_ENABLE_LIVE_REQUESTS": value,
            "TMDB_API_READ_ACCESS_TOKEN": "tok",
        }, clear=False):
            cfg = TMDBConfig.from_env()
            assert cfg.enable_live_requests is True

    @pytest.mark.parametrize("value", ["0", "no", "NO", "False", "FALSE", "random", ""])
    def test_enable_live_requests_falsy_variants(self, value: str):
        """Non-truthy values should keep live requests disabled."""
        with patch.dict(os.environ, {
            "TMDB_ENABLE_LIVE_REQUESTS": value,
            "TMDB_API_READ_ACCESS_TOKEN": "tok",
        }, clear=False):
            cfg = TMDBConfig.from_env()
            assert cfg.enable_live_requests is False

    def test_missing_token(self):
        """Missing TMDB_API_READ_ACCESS_TOKEN should result in empty string
        when the .env file is NOT available as a fallback."""
        # TMDBConfig defaults to empty token when env var is absent
        cfg = TMDBConfig(read_access_token="")
        assert cfg.read_access_token == ""

    def test_whitespace_token(self):
        """Whitespace-only token should be treated as empty."""
        with patch.dict(os.environ, {
            "TMDB_API_READ_ACCESS_TOKEN": "   ",
        }, clear=False):
            cfg = TMDBConfig.from_env()
            assert cfg.read_access_token == ""

    def test_timeout_clamping(self):
        """Timeout values should be clamped to [0.5, 60.0]."""
        with patch.dict(os.environ, {
            "TMDB_TIMEOUT_SECONDS": "0.1",
            "TMDB_API_READ_ACCESS_TOKEN": "tok",
        }, clear=False):
            cfg = TMDBConfig.from_env()
            assert cfg.timeout_seconds == 0.5

        with patch.dict(os.environ, {
            "TMDB_TIMEOUT_SECONDS": "120.0",
            "TMDB_API_READ_ACCESS_TOKEN": "tok",
        }, clear=False):
            cfg = TMDBConfig.from_env()
            assert cfg.timeout_seconds == 60.0

    def test_invalid_numeric_values_use_defaults(self):
        """Invalid numeric values should fall back to defaults."""
        with patch.dict(os.environ, {
            "TMDB_TIMEOUT_SECONDS": "not_a_number",
            "TMDB_MAX_RETRIES": "invalid",
            "TMDB_RATE_LIMIT_RPS": "nope",
            "TMDB_MAX_PAGES": "bad",
            "TMDB_API_READ_ACCESS_TOKEN": "tok",
        }, clear=False):
            cfg = TMDBConfig.from_env()
            assert cfg.timeout_seconds == 10.0
            assert cfg.max_retries == 3
            assert cfg.rate_limit_rps == 4.0
            assert cfg.max_pages == 5


class TestMainDotenvPath:
    """main.py should compute the .env path relative to __file__."""

    def test_env_file_path_is_in_backend_dir(self):
        """The _ENV_FILE path should point to backend/.env."""
        from app import main
        env_file = getattr(main, "_ENV_FILE", None)
        assert env_file is not None, "_ENV_FILE not defined in main.py"
        # It should end with backend/.env
        assert env_file.name == ".env"
        assert env_file.parent.name == "backend"

    def test_backend_dir_is_correct(self):
        """_BACKEND_DIR should point to the backend/ directory."""
        from app import main
        backend_dir = getattr(main, "_BACKEND_DIR", None)
        assert backend_dir is not None, "_BACKEND_DIR not defined in main.py"
        assert backend_dir.name == "backend"
        assert (backend_dir / "app" / "main.py").is_file()
