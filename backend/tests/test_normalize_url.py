"""Tests for the centralized media URL normalization function."""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.schemas.movie import normalize_url


class TestNormalizeUrl:
    """Unit tests for normalize_url()."""

    # ── None / empty ──────────────────────────────────────────────────

    def test_none_returns_none(self):
        assert normalize_url(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_url("") is None

    # ── Relative paths ────────────────────────────────────────────────

    def test_relative_path_gets_leading_slash(self):
        assert normalize_url("media/videos/hls/abc/master.m3u8") == "/media/videos/hls/abc/master.m3u8"

    def test_relative_poster_path(self):
        assert normalize_url("media/images/posters/abc.jpg") == "/media/images/posters/abc.jpg"

    def test_relative_backdrop_path(self):
        assert normalize_url("media/images/backdrops/abc.jpg") == "/media/images/backdrops/abc.jpg"

    # ── Already root-relative ─────────────────────────────────────────

    def test_absolute_path_unchanged(self):
        assert normalize_url("/media/videos/hls/abc/master.m3u8") == "/media/videos/hls/abc/master.m3u8"

    def test_absolute_poster_path(self):
        assert normalize_url("/media/images/posters/abc.jpg") == "/media/images/posters/abc.jpg"

    # ── No /media/media/ duplication ──────────────────────────────────

    def test_no_double_media_prefix(self):
        result = normalize_url("media/videos/example.m3u8")
        assert not result.startswith("/media/media/")
        assert result == "/media/videos/example.m3u8"

    def test_no_double_slash(self):
        result = normalize_url("/media/images/posters/test.jpg")
        assert "//" not in result.replace("://", "")

    # ── Stale HTTP URLs ───────────────────────────────────────────────

    def test_stale_http_ip_url_stripped_to_relative(self):
        url = "http://172.35.53.158/media/videos/hls/abc/master.m3u8"
        assert normalize_url(url) == "/media/videos/hls/abc/master.m3u8"

    def test_stale_http_localhost_url_stripped(self):
        url = "http://localhost:8000/media/images/posters/test.jpg"
        assert normalize_url(url) == "/media/images/posters/test.jpg"

    def test_stale_http_url_without_media_returns_none(self):
        url = "http://172.35.53.158/some/other/path.jpg"
        assert normalize_url(url) is None

    # ── Valid external HTTPS URLs ─────────────────────────────────────

    def test_https_external_url_preserved(self):
        url = "https://cdn.example.com/posters/movie123.jpg"
        assert normalize_url(url) == url

    def test_https_same_origin_preserved(self):
        url = "https://laetus.io.vn/media/images/posters/abc.jpg"
        assert normalize_url(url) == url

    # ── Edge cases ────────────────────────────────────────────────────

    def test_backslash_path_normalized(self):
        result = normalize_url("\\media\\images\\posters\\abc.jpg")
        assert result == "/media\\images\\posters\\abc.jpg" or result.startswith("/media")

    def test_double_leading_slashes_cleaned(self):
        result = normalize_url("//media/images/posters/abc.jpg")
        assert result == "/media/images/posters/abc.jpg"


class TestNormalizeUrlIntegration:
    """Integration: verify schemas use normalize_url consistently."""

    def test_movie_detail_schema_uses_normalize(self):
        """MovieDetailSchema computed fields use normalize_url."""
        from app.schemas.movie import MovieDetailSchema
        import uuid

        schema = MovieDetailSchema(
            id=uuid.uuid4(),
            title="Test",
            poster_path="media/images/posters/test.jpg",
            hls_playlist_path="media/videos/hls/abc/master.m3u8",
        )
        assert schema.poster_url == "/media/images/posters/test.jpg"
        assert schema.hls_playlist_url == "/media/videos/hls/abc/master.m3u8"

    def test_movie_list_schema_uses_normalize(self):
        """MovieListItemSchema computed fields use normalize_url."""
        from app.schemas.movie import MovieListItemSchema
        import uuid

        schema = MovieListItemSchema(
            id=uuid.uuid4(),
            title="Test",
            poster_path="media/images/posters/test.jpg",
            backdrop_path="media/images/backdrops/test.jpg",
        )
        assert schema.poster_url == "/media/images/posters/test.jpg"
        assert schema.backdrop_url == "/media/images/backdrops/test.jpg"

    def test_stale_url_in_schema_gets_sanitized(self):
        """A stale HTTP URL stored in poster_path is sanitized."""
        from app.schemas.movie import MovieDetailSchema
        import uuid

        schema = MovieDetailSchema(
            id=uuid.uuid4(),
            title="Test",
            poster_path="http://172.35.53.158/media/images/posters/old.jpg",
        )
        assert schema.poster_url == "/media/images/posters/old.jpg"
        assert not schema.poster_url.startswith("http://")
