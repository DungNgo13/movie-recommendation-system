"""
Secure, reusable backend HTTP client for The Movie Database (TMDB) v3 API.

Security & Reliability Guarantees:
  1. Allowlisted API host ONLY (`https://api.themoviedb.org/3`). User input can
     never control the scheme, host, or arbitrary URL paths.
  2. Live external requests require explicit opt-in (`TMDB_ENABLE_LIVE_REQUESTS=true`
     or `enable_live_requests=True`) unless a mocked `httpx.BaseTransport` is injected.
  3. Explicit connect/read/write/pool timeouts and connection pooling via `httpx.Client`.
  4. Configurable request rate limiter, bounded retries, exponential backoff, and
     HTTP 429 `Retry-After` support.
  5. Strict pagination limits (`1 <= page <= max_pages`) to prevent unbounded queries.
  6. Automatic secret redaction in logs, error messages, and object representations.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import httpx

from ..core.api_errors import (
    TMDB_DISALLOWED_HOST,
    TMDB_FORBIDDEN,
    TMDB_INVALID_INPUT,
    TMDB_INVALID_RESPONSE,
    TMDB_LIVE_REQUESTS_DISABLED,
    TMDB_NETWORK_ERROR,
    TMDB_NOT_CONFIGURED,
    TMDB_NOT_FOUND,
    TMDB_PAGINATION_LIMIT_EXCEEDED,
    TMDB_RATE_LIMITED,
    TMDB_TIMEOUT,
    TMDB_UNAUTHORIZED,
    TMDB_UPSTREAM_ERROR,
)

# ─── Allowlisted Hosts & Constants ───────────────────────────────────────────

ALLOWLISTED_API_HOSTS: frozenset[str] = frozenset({"api.themoviedb.org"})
ALLOWLISTED_IMAGE_HOSTS: frozenset[str] = frozenset({"image.tmdb.org"})
DEFAULT_TMDB_BASE_URL = "https://api.themoviedb.org/3"
DEFAULT_TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
ALLOWED_IMAGE_SIZES: frozenset[str] = frozenset({"w300", "w500", "w780", "w1280", "original"})
ALLOWED_EXTERNAL_SOURCES: frozenset[str] = frozenset({"imdb_id", "wikidata_id"})
ALLOWED_APPEND_TO_RESPONSE: frozenset[str] = frozenset({
    "credits",
    "keywords",
    "alternative_titles",
    "release_dates",
    "external_ids",
    "translations",
})

_EXTERNAL_ID_PATTERN = re.compile(r"^(tt\d{5,12}|Q\d{1,15})$")
_IMAGE_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9_\-]+\.(jpg|jpeg|png|webp|svg)$", re.IGNORECASE)
_BEARER_TOKEN_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
_API_KEY_PARAM_PATTERN = re.compile(r"(api_key=)[^&\s\"']+", re.IGNORECASE)


def redact_secrets(text: str, token: Optional[str] = None) -> str:
    """Redact Bearer tokens, api_key query parameters, and explicit secret values."""
    if not text:
        return text
    redacted = _BEARER_TOKEN_PATTERN.sub(r"\1[REDACTED]", text)
    redacted = _API_KEY_PARAM_PATTERN.sub(r"\1[REDACTED]", redacted)
    if token and len(token.strip()) >= 4:
        redacted = redacted.replace(token.strip(), "[REDACTED]")
    return redacted


class SecretRedactionFilter(logging.Filter):
    """Logging filter that strips any TMDB credentials from log records."""

    def __init__(self, token_provider: Optional[Callable[[], Optional[str]]] = None) -> None:
        super().__init__()
        self._token_provider = token_provider

    def filter(self, record: logging.LogRecord) -> bool:
        token = self._token_provider() if self._token_provider else None
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg, token)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_secrets(v, token) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_secrets(a, token) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


logger = logging.getLogger(__name__)
logger.addFilter(SecretRedactionFilter(lambda: os.getenv("TMDB_API_READ_ACCESS_TOKEN")))


# ─── Exceptions & Telemetry ──────────────────────────────────────────────────

class TMDBClientError(Exception):
    """Structured exception raised by TMDBClient with a stable machine-readable code."""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: Optional[int] = None,
        retryable: bool = False,
    ) -> None:
        clean_msg = redact_secrets(message, os.getenv("TMDB_API_READ_ACCESS_TOKEN"))
        super().__init__(clean_msg)
        self.message = clean_msg
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


@dataclass
class TMDBClientStats:
    """Runtime telemetry for MovSug TEC and operational monitoring."""

    requests_total: int = 0
    api_failures: int = 0
    http_429_count: int = 0
    retry_count: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requests_total": self.requests_total,
            "api_failures": self.api_failures,
            "http_429_count": self.http_429_count,
            "retry_count": self.retry_count,
            "latencies_ms": list(self.latencies_ms),
        }


@dataclass
class TMDBConfig:
    """Configuration for TMDBClient."""

    read_access_token: str = ""
    base_url: str = DEFAULT_TMDB_BASE_URL
    enable_live_requests: bool = False
    timeout_seconds: float = 10.0
    max_retries: int = 3
    backoff_base_seconds: float = 0.5
    max_retry_after_seconds: float = 15.0
    rate_limit_rps: float = 4.0
    max_pages: int = 5
    max_connections: int = 10
    max_keepalive_connections: int = 5

    def __repr__(self) -> str:
        masked = "***REDACTED***" if self.read_access_token else "<empty>"
        return (
            f"TMDBConfig(base_url={self.base_url!r}, "
            f"read_access_token={masked!r}, "
            f"enable_live_requests={self.enable_live_requests!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, "
            f"max_retries={self.max_retries!r}, "
            f"rate_limit_rps={self.rate_limit_rps!r}, "
            f"max_pages={self.max_pages!r})"
        )

    @classmethod
    def from_env(cls) -> TMDBConfig:
        """Load configuration from environment variables with safe defaults."""
        token = (os.getenv("TMDB_API_READ_ACCESS_TOKEN") or "").strip()
        live_raw = (os.getenv("TMDB_ENABLE_LIVE_REQUESTS") or "false").strip().lower()
        enable_live = live_raw in ("1", "true", "yes")

        try:
            timeout = max(0.5, min(60.0, float(os.getenv("TMDB_TIMEOUT_SECONDS", "10.0"))))
        except ValueError:
            timeout = 10.0

        try:
            max_retries = max(0, min(10, int(os.getenv("TMDB_MAX_RETRIES", "3"))))
        except ValueError:
            max_retries = 3

        try:
            rps = max(0.1, min(50.0, float(os.getenv("TMDB_RATE_LIMIT_RPS", "4.0"))))
        except ValueError:
            rps = 4.0

        try:
            max_pages = max(1, min(20, int(os.getenv("TMDB_MAX_PAGES", "5"))))
        except ValueError:
            max_pages = 5

        base_url = (os.getenv("TMDB_BASE_URL") or DEFAULT_TMDB_BASE_URL).strip()
        return cls(
            read_access_token=token,
            base_url=base_url,
            enable_live_requests=enable_live,
            timeout_seconds=timeout,
            max_retries=max_retries,
            rate_limit_rps=rps,
            max_pages=max_pages,
        )


def validate_allowlisted_base_url(base_url: str) -> str:
    """Ensure the base URL uses HTTPS and points strictly to the official TMDB API host."""
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWLISTED_API_HOSTS:
        raise TMDBClientError(
            f"Disallowed TMDB API base URL host: {parsed.hostname!r}. "
            f"Only {sorted(ALLOWLISTED_API_HOSTS)} over HTTPS is permitted.",
            code=TMDB_DISALLOWED_HOST,
        )
    if not parsed.path.rstrip("/").endswith("/3"):
        raise TMDBClientError(
            "TMDB API base URL path must target '/3'.",
            code=TMDB_DISALLOWED_HOST,
        )
    return f"https://{parsed.hostname}/3"


def build_tmdb_image_url(file_path: Optional[str], size: str = "w500") -> Optional[str]:
    """Safely construct an allowlisted TMDB image URL from a relative path."""
    if not file_path or not isinstance(file_path, str):
        return None
    cleaned = file_path.strip()
    if not cleaned:
        return None
    if not cleaned.startswith("/"):
        cleaned = "/" + cleaned
    if ".." in cleaned or not _IMAGE_PATH_PATTERN.match(cleaned):
        return None
    safe_size = size if size in ALLOWED_IMAGE_SIZES else "w500"
    return f"{DEFAULT_TMDB_IMAGE_BASE_URL}/{safe_size}{cleaned}"


# ─── TMDB HTTP Client ────────────────────────────────────────────────────────

class TMDBClient:
    """Reusable, rate-limited, retry-capable TMDB API v3 client."""

    def __init__(
        self,
        config: Optional[TMDBConfig] = None,
        transport: Optional[httpx.BaseTransport] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or TMDBConfig.from_env()
        self._validated_base_url = validate_allowlisted_base_url(self.config.base_url)
        self._transport = transport
        self._sleep = sleep_fn
        self._clock = clock_fn
        self._last_request_ts: Optional[float] = None
        self.stats = TMDBClientStats()

        timeout = httpx.Timeout(
            connect=min(5.0, self.config.timeout_seconds),
            read=self.config.timeout_seconds,
            write=min(5.0, self.config.timeout_seconds),
            pool=min(5.0, self.config.timeout_seconds),
        )
        limits = httpx.Limits(
            max_connections=self.config.max_connections,
            max_keepalive_connections=self.config.max_keepalive_connections,
        )
        self._client = httpx.Client(
            base_url=self._validated_base_url,
            timeout=timeout,
            limits=limits,
            transport=transport,
            follow_redirects=False,  # Never follow redirects to untrusted external hosts
        )

    def __repr__(self) -> str:
        return f"TMDBClient(config={self.config!r})"

    def close(self) -> None:
        """Close the underlying connection pool."""
        self._client.close()

    def __enter__(self) -> TMDBClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    # ── Internal Guards & Rate Limiting ──────────────────────────────────────

    def _ensure_ready(self) -> None:
        """Verify live-request authorization and API token presence."""
        # If no mock transport is injected, live requests must be explicitly enabled.
        if self._transport is None and not self.config.enable_live_requests:
            raise TMDBClientError(
                "Live TMDB API requests are disabled. Set TMDB_ENABLE_LIVE_REQUESTS=true "
                "to allow live network access.",
                code=TMDB_LIVE_REQUESTS_DISABLED,
            )
        if not self.config.read_access_token or not self.config.read_access_token.strip():
            raise TMDBClientError(
                "TMDB API read-access token is not configured.",
                code=TMDB_NOT_CONFIGURED,
            )

    def _validate_endpoint_path(self, endpoint: str) -> str:
        """Ensure endpoint is a safe relative path without URL injection or traversal."""
        if not endpoint or not isinstance(endpoint, str):
            raise TMDBClientError("Endpoint path must be a non-empty string.", code=TMDB_INVALID_INPUT)
        if "://" in endpoint or endpoint.startswith("//") or ".." in endpoint or "\\" in endpoint:
            raise TMDBClientError(
                f"Unsafe endpoint path rejected: {endpoint!r}",
                code=TMDB_DISALLOWED_HOST,
            )
        if any(ord(ch) < 32 for ch in endpoint):
            raise TMDBClientError("Control characters are not allowed in endpoint path.", code=TMDB_INVALID_INPUT)
        return "/" + endpoint.lstrip("/")

    def _enforce_rate_limit(self) -> None:
        """Throttle requests according to `config.rate_limit_rps`."""
        if self.config.rate_limit_rps <= 0:
            return
        min_interval = 1.0 / self.config.rate_limit_rps
        now = self._clock()
        if self._last_request_ts is not None:
            elapsed = now - self._last_request_ts
            if elapsed < min_interval:
                self._sleep(min_interval - elapsed)
        self._last_request_ts = self._clock()

    def _compute_backoff(self, attempt: int, retry_after_header: Optional[str] = None) -> float:
        """Compute bounded sleep time for retry attempt, honoring Retry-After if present."""
        if retry_after_header is not None:
            try:
                parsed = float(retry_after_header.strip())
                if parsed >= 0:
                    return min(parsed, self.config.max_retry_after_seconds)
            except ValueError:
                pass
        backoff = self.config.backoff_base_seconds * (2 ** attempt)
        return min(backoff, self.config.max_retry_after_seconds)

    def _request_json(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute a GET request with bounded retries, rate limiting, and structured error handling."""
        self._ensure_ready()
        safe_path = self._validate_endpoint_path(endpoint)

        headers = {
            "Authorization": f"Bearer {self.config.read_access_token.strip()}",
            "Accept": "application/json",
        }

        max_attempts = 1 + max(0, self.config.max_retries)
        last_error: Optional[TMDBClientError] = None

        for attempt in range(max_attempts):
            if attempt > 0:
                self.stats.retry_count += 1

            self._enforce_rate_limit()
            self.stats.requests_total += 1
            start_ts = self._clock()

            try:
                response = self._client.get(safe_path, params=params, headers=headers)
                elapsed_ms = max(0.0, (self._clock() - start_ts) * 1000.0)
                self.stats.latencies_ms.append(round(elapsed_ms, 2))
            except httpx.TimeoutException as exc:
                elapsed_ms = max(0.0, (self._clock() - start_ts) * 1000.0)
                self.stats.latencies_ms.append(round(elapsed_ms, 2))
                last_error = TMDBClientError(
                    f"TMDB request timed out on {safe_path}: {redact_secrets(str(exc), self.config.read_access_token)}",
                    code=TMDB_TIMEOUT,
                    retryable=True,
                )
                logger.warning(
                    "TMDB timeout on %s (attempt %d/%d)",
                    safe_path, attempt + 1, max_attempts,
                )
                if attempt + 1 < max_attempts:
                    self._sleep(self._compute_backoff(attempt))
                    continue
                self.stats.api_failures += 1
                raise last_error from None
            except httpx.RequestError as exc:
                elapsed_ms = max(0.0, (self._clock() - start_ts) * 1000.0)
                self.stats.latencies_ms.append(round(elapsed_ms, 2))
                last_error = TMDBClientError(
                    f"TMDB network error on {safe_path}: {redact_secrets(str(exc), self.config.read_access_token)}",
                    code=TMDB_NETWORK_ERROR,
                    retryable=True,
                )
                logger.warning(
                    "TMDB network error on %s (attempt %d/%d)",
                    safe_path, attempt + 1, max_attempts,
                )
                if attempt + 1 < max_attempts:
                    self._sleep(self._compute_backoff(attempt))
                    continue
                self.stats.api_failures += 1
                raise last_error from None

            status = response.status_code

            if status == 200:
                try:
                    payload = response.json()
                except ValueError:
                    self.stats.api_failures += 1
                    raise TMDBClientError(
                        f"TMDB returned malformed JSON on {safe_path}.",
                        code=TMDB_INVALID_RESPONSE,
                        status_code=status,
                    ) from None
                if not isinstance(payload, dict):
                    self.stats.api_failures += 1
                    raise TMDBClientError(
                        f"TMDB returned non-object JSON payload on {safe_path}.",
                        code=TMDB_INVALID_RESPONSE,
                        status_code=status,
                    )
                return payload

            if status == 401:
                self.stats.api_failures += 1
                logger.error("TMDB authentication failed (HTTP 401) on %s", safe_path)
                raise TMDBClientError(
                    "TMDB authentication failed (HTTP 401).",
                    code=TMDB_UNAUTHORIZED,
                    status_code=401,
                    retryable=False,
                )

            if status == 403:
                self.stats.api_failures += 1
                logger.error("TMDB access forbidden (HTTP 403) on %s", safe_path)
                raise TMDBClientError(
                    "TMDB access forbidden (HTTP 403).",
                    code=TMDB_FORBIDDEN,
                    status_code=403,
                    retryable=False,
                )

            if status == 404:
                self.stats.api_failures += 1
                logger.info("TMDB resource not found (HTTP 404) on %s", safe_path)
                raise TMDBClientError(
                    f"TMDB resource not found on {safe_path} (HTTP 404).",
                    code=TMDB_NOT_FOUND,
                    status_code=404,
                    retryable=False,
                )

            if status == 429:
                self.stats.http_429_count += 1
                retry_after = response.headers.get("Retry-After")
                last_error = TMDBClientError(
                    "TMDB rate limit exceeded (HTTP 429).",
                    code=TMDB_RATE_LIMITED,
                    status_code=429,
                    retryable=True,
                )
                logger.warning(
                    "TMDB rate limited (HTTP 429) on %s (attempt %d/%d, Retry-After=%s)",
                    safe_path, attempt + 1, max_attempts, retry_after,
                )
                if attempt + 1 < max_attempts:
                    self._sleep(self._compute_backoff(attempt, retry_after))
                    continue
                self.stats.api_failures += 1
                raise last_error

            if 500 <= status <= 599:
                last_error = TMDBClientError(
                    f"TMDB upstream server error (HTTP {status}) on {safe_path}.",
                    code=TMDB_UPSTREAM_ERROR,
                    status_code=status,
                    retryable=True,
                )
                logger.warning(
                    "TMDB upstream error HTTP %d on %s (attempt %d/%d)",
                    status, safe_path, attempt + 1, max_attempts,
                )
                if attempt + 1 < max_attempts:
                    self._sleep(self._compute_backoff(attempt))
                    continue
                self.stats.api_failures += 1
                raise last_error

            # Any other unexpected status code (non-retryable)
            self.stats.api_failures += 1
            raise TMDBClientError(
                f"Unexpected HTTP status {status} from TMDB on {safe_path}.",
                code=TMDB_INVALID_RESPONSE,
                status_code=status,
                retryable=False,
            )

        self.stats.api_failures += 1
        raise last_error or TMDBClientError("TMDB request failed.", code=TMDB_UPSTREAM_ERROR)

    # ── Public TMDB Operations ───────────────────────────────────────────────

    def search_movies(
        self,
        query: str,
        year: Optional[int] = None,
        language: str = "en-US",
        page: int = 1,
        include_adult: bool = False,
    ) -> dict[str, Any]:
        """Search movies by title via `GET /search/movie` with strict pagination bounds."""
        if not query or not isinstance(query, str) or not query.strip():
            raise TMDBClientError("Search query must be a non-empty string.", code=TMDB_INVALID_INPUT)
        clean_query = query.strip()[:200]

        if not isinstance(page, int) or page < 1 or page > self.config.max_pages:
            raise TMDBClientError(
                f"Requested page {page} exceeds allowed range 1..{self.config.max_pages}.",
                code=TMDB_PAGINATION_LIMIT_EXCEEDED,
            )

        params: dict[str, Any] = {
            "query": clean_query,
            "language": language,
            "page": page,
            "include_adult": "true" if include_adult else "false",
        }
        if year is not None:
            if not isinstance(year, int) or year < 1870 or year > 2100:
                raise TMDBClientError(f"Invalid release year filter: {year}", code=TMDB_INVALID_INPUT)
            params["year"] = year

        payload = self._request_json("/search/movie", params=params)
        results = payload.get("results")
        if not isinstance(results, list):
            raise TMDBClientError(
                "TMDB search response missing 'results' list.",
                code=TMDB_INVALID_RESPONSE,
            )
        return {
            "page": int(payload.get("page", page)),
            "total_results": int(payload.get("total_results", len(results))),
            "total_pages": min(int(payload.get("total_pages", 1)), self.config.max_pages),
            "results": results,
        }

    def find_by_external_id(
        self,
        external_id: str,
        external_source: str = "imdb_id",
        language: str = "en-US",
    ) -> list[dict[str, Any]]:
        """Look up movie by verified external ID (`imdb_id` or `wikidata_id`) via `GET /find/{external_id}`."""
        if external_source not in ALLOWED_EXTERNAL_SOURCES:
            raise TMDBClientError(
                f"Unsupported external_source: {external_source!r}.",
                code=TMDB_INVALID_INPUT,
            )
        if not external_id or not isinstance(external_id, str):
            raise TMDBClientError("external_id must be a non-empty string.", code=TMDB_INVALID_INPUT)
        clean_id = external_id.strip()
        if not _EXTERNAL_ID_PATTERN.match(clean_id):
            raise TMDBClientError(
                f"Malformed external identifier: {clean_id!r}.",
                code=TMDB_INVALID_INPUT,
            )

        payload = self._request_json(
            f"/find/{clean_id}",
            params={"external_source": external_source, "language": language},
        )
        movie_results = payload.get("movie_results", [])
        if not isinstance(movie_results, list):
            raise TMDBClientError(
                "TMDB find response 'movie_results' must be a list.",
                code=TMDB_INVALID_RESPONSE,
            )
        return movie_results

    def get_movie_details(
        self,
        tmdb_id: int,
        language: str = "en-US",
        append_to_response: tuple[str, ...] = (
            "credits",
            "keywords",
            "alternative_titles",
            "external_ids",
        ),
    ) -> dict[str, Any]:
        """Fetch comprehensive movie details by TMDB ID via `GET /movie/{tmdb_id}`."""
        if not isinstance(tmdb_id, int) or isinstance(tmdb_id, bool) or tmdb_id <= 0:
            raise TMDBClientError(f"Invalid tmdb_id: {tmdb_id!r}", code=TMDB_INVALID_INPUT)

        safe_append = [a for a in append_to_response if a in ALLOWED_APPEND_TO_RESPONSE]
        params: dict[str, Any] = {"language": language}
        if safe_append:
            params["append_to_response"] = ",".join(safe_append)

        payload = self._request_json(f"/movie/{tmdb_id}", params=params)
        if "id" not in payload or not isinstance(payload.get("title"), str):
            raise TMDBClientError(
                f"TMDB movie detail response for {tmdb_id} is missing required 'id' or 'title'.",
                code=TMDB_INVALID_RESPONSE,
            )
        return payload

    def get_movie_localized_details(
        self,
        tmdb_id: int,
        language: str = "vi-VN",
    ) -> dict[str, Any]:
        """Fetch localized title and overview (e.g. `vi-VN`) separately from primary English metadata."""
        if not isinstance(tmdb_id, int) or isinstance(tmdb_id, bool) or tmdb_id <= 0:
            raise TMDBClientError(f"Invalid tmdb_id: {tmdb_id!r}", code=TMDB_INVALID_INPUT)
        payload = self._request_json(f"/movie/{tmdb_id}", params={"language": language})
        return {
            "id": payload.get("id", tmdb_id),
            "language": language,
            "title": payload.get("title"),
            "overview": payload.get("overview"),
        }
