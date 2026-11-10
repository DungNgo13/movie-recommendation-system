"""
Unit tests for the secure TMDB HTTP client (`app.services.tmdb_client`).

Covers:
  - Live-request safety guard (`tmdb_live_requests_disabled`)
  - Missing credentials (`tmdb_not_configured`)
  - Allowlisted host & path traversal protection (`tmdb_disallowed_host`)
  - HTTP 401, 403, 404 non-retryable handling
  - HTTP 429 rate-limit handling with `Retry-After` header support
  - HTTP 5xx exponential backoff and retry exhaustion
  - Request timeouts and network errors
  - Malformed JSON and schema validation (`tmdb_invalid_response`)
  - Search pagination limits (`tmdb_pagination_limit_exceeded`)
  - Configurable client-side rate limiting
  - Secret redaction in logs, exceptions, and object reprs
"""

from __future__ import annotations

import logging
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.api_errors import (
    TMDB_BUDGET_EXHAUSTED,
    TMDB_CIRCUIT_OPEN,
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
    TMDB_TLS_HANDSHAKE_FAILED,
    TMDB_UNAUTHORIZED,
    TMDB_UPSTREAM_ERROR,
)
from app.services.tmdb_client import (
    SecretRedactionFilter,
    TMDBClient,
    TMDBClientError,
    TMDBConfig,
    _is_transport_failure,
    build_tmdb_image_url,
    redact_secrets,
)


def _make_config(**overrides) -> TMDBConfig:
    defaults = {
        "read_access_token": "super_secret_tmdb_token_123456",
        "enable_live_requests": False,
        "timeout_seconds": 5.0,
        "max_retries": 2,
        "backoff_base_seconds": 0.25,
        "max_retry_after_seconds": 5.0,
        "rate_limit_rps": 100.0,
        "max_pages": 3,
    }
    defaults.update(overrides)
    return TMDBConfig(**defaults)


def test_live_requests_disabled_without_mock_transport():
    """Real network requests must be blocked unless explicitly enabled."""
    cfg = _make_config(enable_live_requests=False)
    with TMDBClient(config=cfg, transport=None) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.search_movies("Inception")
        assert exc_info.value.code == TMDB_LIVE_REQUESTS_DISABLED


def test_missing_token_raises_not_configured():
    """Missing read access token must raise tmdb_not_configured."""
    cfg = _make_config(read_access_token="   ")
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"results": []}))
    with TMDBClient(config=cfg, transport=transport) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.search_movies("Inception")
        assert exc_info.value.code == TMDB_NOT_CONFIGURED


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://api.themoviedb.org/3",
        "https://evil.example.com/3",
        "https://api.themoviedb.org.evil.com/3",
        "https://api.themoviedb.org/v2",
        "ftp://api.themoviedb.org/3",
    ],
)
def test_disallowed_base_url_rejected(bad_url: str):
    """Only https://api.themoviedb.org/3 is permitted as the base URL."""
    cfg = _make_config(base_url=bad_url)
    with pytest.raises(TMDBClientError) as exc_info:
        TMDBClient(config=cfg)
    assert exc_info.value.code == TMDB_DISALLOWED_HOST


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "https://evil.com/steal",
        "//evil.com/steal",
        "/movie/../../etc/passwd",
        "/movie\\..\\secret",
    ],
)
def test_endpoint_path_traversal_rejected(unsafe_path: str):
    """User input must never escape the allowlisted host or traverse paths."""
    cfg = _make_config()
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    with TMDBClient(config=cfg, transport=transport) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client._request_json(unsafe_path)
        assert exc_info.value.code == TMDB_DISALLOWED_HOST


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (401, TMDB_UNAUTHORIZED),
        (403, TMDB_FORBIDDEN),
        (404, TMDB_NOT_FOUND),
    ],
)
def test_non_retryable_status_codes(status_code: int, expected_code: str):
    """401, 403, and 404 responses must fail immediately without retrying."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code, json={"status_message": "error"})

    cfg = _make_config(max_retries=3)
    with TMDBClient(config=cfg, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(550)
        assert exc_info.value.code == expected_code
        assert exc_info.value.status_code == status_code
        assert not exc_info.value.retryable
        assert calls == 1
        assert client.stats.requests_total == 1
        assert client.stats.retry_count == 0
        assert client.stats.api_failures == 1


def test_http_429_respects_retry_after_and_succeeds():
    """HTTP 429 should sleep for Retry-After seconds and succeed on subsequent attempt."""
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "1.5"}, json={"status_message": "rate limit"})
        return httpx.Response(200, json={"id": 27205, "title": "Inception"})

    cfg = _make_config(max_retries=2, rate_limit_rps=0)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda s: sleeps.append(s),
    ) as client:
        data = client.get_movie_details(27205)
        assert data["id"] == 27205
        assert data["title"] == "Inception"
        assert calls == 2
        assert sleeps == [1.5]
        assert client.stats.http_429_count == 1
        assert client.stats.retry_count == 1
        assert client.stats.api_failures == 0


def test_http_429_retry_exhaustion():
    """Exhausting retries on HTTP 429 must raise tmdb_rate_limited and record telemetry."""
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "999"}, json={})

    cfg = _make_config(max_retries=2, max_retry_after_seconds=2.0, rate_limit_rps=0)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda s: sleeps.append(s),
    ) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.search_movies("Inception")
        assert exc_info.value.code == TMDB_RATE_LIMITED
        assert exc_info.value.status_code == 429
        assert client.stats.requests_total == 3
        assert client.stats.http_429_count == 3
        assert client.stats.retry_count == 2
        assert client.stats.api_failures == 1
        # Retry-After=999 must be clamped to max_retry_after_seconds=2.0
        assert sleeps == [2.0, 2.0]


def test_5xx_exponential_backoff_and_exhaustion():
    """5xx errors must back off exponentially and raise tmdb_upstream_error when exhausted."""
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    cfg = _make_config(max_retries=2, backoff_base_seconds=0.5, rate_limit_rps=0)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda s: sleeps.append(s),
    ) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(27205)
        assert exc_info.value.code == TMDB_UPSTREAM_ERROR
        assert exc_info.value.status_code == 503
        assert sleeps == [0.5, 1.0]
        assert client.stats.requests_total == 3
        assert client.stats.retry_count == 2
        assert client.stats.api_failures == 1


def test_timeout_handling_and_retry():
    """TimeoutException must retry up to max_retries and raise tmdb_timeout."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("Read timed out", request=request)

    cfg = _make_config(max_retries=1, backoff_base_seconds=0.1, rate_limit_rps=0)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.search_movies("Matrix")
        assert exc_info.value.code == TMDB_TIMEOUT
        assert calls == 2
        assert client.stats.retry_count == 1
        assert client.stats.api_failures == 1


def test_network_error_handling():
    """ConnectError with transport failure pattern must retry and raise
    tmdb_tls_handshake_failed on exhaustion."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    cfg = _make_config(max_retries=1, rate_limit_rps=0)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.search_movies("Matrix")
        # "Connection refused" is classified as a transport failure
        assert exc_info.value.code == TMDB_TLS_HANDSHAKE_FAILED


def test_invalid_json_and_schema_responses():
    """Malformed JSON or missing required fields must raise tmdb_invalid_response."""
    cfg = _make_config(max_retries=0, rate_limit_rps=0)

    # 1. Malformed JSON
    t1 = httpx.MockTransport(lambda req: httpx.Response(200, content=b"<html>not json</html>"))
    with TMDBClient(config=cfg, transport=t1) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.search_movies("Matrix")
        assert exc_info.value.code == TMDB_INVALID_RESPONSE

    # 2. Missing 'results' in search
    t2 = httpx.MockTransport(lambda req: httpx.Response(200, json={"page": 1}))
    with TMDBClient(config=cfg, transport=t2) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.search_movies("Matrix")
        assert exc_info.value.code == TMDB_INVALID_RESPONSE

    # 3. Missing 'title' in movie details
    t3 = httpx.MockTransport(lambda req: httpx.Response(200, json={"id": 123}))
    with TMDBClient(config=cfg, transport=t3) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(123)
        assert exc_info.value.code == TMDB_INVALID_RESPONSE


def test_pagination_limits_enforced():
    """Requesting page < 1 or page > max_pages must raise tmdb_pagination_limit_exceeded."""
    cfg = _make_config(max_pages=3)
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"results": []}))
    with TMDBClient(config=cfg, transport=transport) as client:
        with pytest.raises(TMDBClientError) as exc_low:
            client.search_movies("Inception", page=0)
        assert exc_low.value.code == TMDB_PAGINATION_LIMIT_EXCEEDED

        with pytest.raises(TMDBClientError) as exc_high:
            client.search_movies("Inception", page=4)
        assert exc_high.value.code == TMDB_PAGINATION_LIMIT_EXCEEDED


def test_find_by_external_id_validation():
    """External ID lookup must validate source and ID format."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/3/find/tt1375666"
        assert request.url.params["external_source"] == "imdb_id"
        return httpx.Response(200, json={"movie_results": [{"id": 27205, "title": "Inception"}]})

    cfg = _make_config()
    with TMDBClient(config=cfg, transport=httpx.MockTransport(handler)) as client:
        results = client.find_by_external_id("tt1375666", external_source="imdb_id")
        assert len(results) == 1
        assert results[0]["id"] == 27205

        with pytest.raises(TMDBClientError) as bad_src:
            client.find_by_external_id("tt1375666", external_source="arbitrary_source")
        assert bad_src.value.code == TMDB_INVALID_INPUT

        with pytest.raises(TMDBClientError) as bad_id:
            client.find_by_external_id("tt1375666/../../evil", external_source="imdb_id")
        assert bad_id.value.code == TMDB_INVALID_INPUT


def test_rate_limiter_throttles_consecutive_requests():
    """Client rate limiter must sleep when consecutive calls exceed rate_limit_rps."""
    clock_now = 100.0
    sleeps: list[float] = []

    def fake_clock() -> float:
        return clock_now

    def fake_sleep(seconds: float) -> None:
        nonlocal clock_now
        sleeps.append(round(seconds, 3))
        clock_now += seconds

    cfg = _make_config(rate_limit_rps=2.0)  # min interval = 0.5s
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"page": 1, "total_results": 0, "total_pages": 1, "results": []})
    )
    with TMDBClient(
        config=cfg,
        transport=transport,
        sleep_fn=fake_sleep,
        clock_fn=fake_clock,
    ) as client:
        client.search_movies("First")
        clock_now += 0.1  # only 0.1s elapsed before second call
        client.search_movies("Second")
        assert sleeps == [0.4]


def test_secret_redaction_in_logs_repr_and_errors(caplog):
    """Credentials must never appear in logs, repr(), or exception strings."""
    secret = "eyJhbGciOiJIUzI1NiJ9.TOP_SECRET_TOKEN_VALUE"
    cfg = _make_config(read_access_token=secret)

    # 1. repr() must redact token
    assert secret not in repr(cfg)
    assert "***REDACTED***" in repr(cfg)

    # 2. redact_secrets helper
    raw_msg = f"Failed call with Authorization: Bearer {secret} and api_key={secret}"
    cleaned = redact_secrets(raw_msg, secret)
    assert secret not in cleaned
    assert "[REDACTED]" in cleaned

    # 3. Logging filter redaction
    test_logger = logging.getLogger("test_tmdb_redaction")
    test_logger.addFilter(SecretRedactionFilter(lambda: secret))
    with caplog.at_level(logging.WARNING, logger="test_tmdb_redaction"):
        test_logger.warning("Header Authorization: Bearer %s failed", secret)
    assert secret not in caplog.text
    assert "[REDACTED]" in caplog.text


def test_build_tmdb_image_url_validation():
    """Image URL builder must allow only clean relative image paths and valid sizes."""
    assert (
        build_tmdb_image_url("/9gk7adHYeDvHkWTkvHsgtKA40av.jpg", size="w500")
        == "https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkWTkvHsgtKA40av.jpg"
    )
    assert build_tmdb_image_url("9gk7adHYeDvHkWTkvHsgtKA40av.png", size="w1280") == (
        "https://image.tmdb.org/t/p/w1280/9gk7adHYeDvHkWTkvHsgtKA40av.png"
    )
    assert build_tmdb_image_url("https://evil.com/hack.jpg") is None
    assert build_tmdb_image_url("/../../etc/passwd.jpg") is None
    assert build_tmdb_image_url(None) is None


# ── Transport Failure Classification Tests ────────────────────────────────────


def test_transport_failure_classification_tls_errors():
    """TLS/connection errors must be classified as transport failures."""
    assert _is_transport_failure(
        ConnectionResetError("[WinError 10054] An existing connection was forcibly closed")
    )
    assert _is_transport_failure(
        httpx.ConnectError("[WinError 10054] An existing connection was forcibly closed")
    )
    assert _is_transport_failure(
        httpx.ConnectError("SSL handshake failed")
    )
    assert _is_transport_failure(
        ConnectionRefusedError("[WinError 10061] Connection refused")
    )
    assert _is_transport_failure(
        httpx.ProxyError("Proxy connection refused")
    )


def test_transport_failure_classification_non_transport():
    """HTTP-level errors must NOT be classified as transport failures."""
    assert not _is_transport_failure(ValueError("Invalid JSON"))
    assert not _is_transport_failure(httpx.DecodingError("UTF-8 decode error"))
    assert not _is_transport_failure(KeyError("missing_field"))


# ── Circuit Breaker Tests ─────────────────────────────────────────────────────


def test_tls_handshake_reset_triggers_circuit_breaker():
    """Repeated TLS handshake resets (WinError 10054) must trigger circuit breaker
    and stop retrying with TMDB_CIRCUIT_OPEN error code."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError(
            "[WinError 10054] An existing connection was forcibly closed by the remote host",
            request=request,
        )

    cfg = _make_config(max_retries=10, rate_limit_rps=0, circuit_breaker_threshold=5)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(550)
        assert exc_info.value.code == TMDB_CIRCUIT_OPEN
        assert not exc_info.value.retryable
        # Circuit breaker should fire after threshold (5) consecutive failures
        assert calls == 5
        assert client.stats.consecutive_transport_failures == 5
        assert client.stats.circuit_breaker_triggered is True
        assert "WinError 10054" in client.stats.circuit_breaker_reason


def test_circuit_breaker_rejects_subsequent_requests():
    """After circuit breaker triggers, subsequent requests must be rejected
    immediately without making any HTTP calls."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError(
            "[WinError 10054] Connection reset",
            request=request,
        )

    cfg = _make_config(max_retries=0, rate_limit_rps=0, circuit_breaker_threshold=3)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        # Trigger circuit breaker across multiple single-attempt calls
        for _ in range(3):
            try:
                client.get_movie_details(550)
            except TMDBClientError:
                pass

        assert client.stats.circuit_breaker_triggered is True
        calls_before = calls

        # Subsequent call should be rejected without any HTTP attempt
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(551)
        assert exc_info.value.code == TMDB_CIRCUIT_OPEN
        assert calls == calls_before  # No additional HTTP calls
        assert client.stats.circuit_breaker_rejections == 1


def test_circuit_breaker_reset_after_success():
    """Consecutive failure counter must reset to 0 after a successful response.
    Circuit breaker must not trigger if failures are interleaved with successes."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        # Fail 3 times, succeed once, fail 3 more times
        if calls in (4,):
            return httpx.Response(200, json={"id": 550, "title": "Fight Club"})
        raise httpx.ConnectError(
            "[WinError 10054] Connection reset",
            request=request,
        )

    cfg = _make_config(max_retries=0, rate_limit_rps=0, circuit_breaker_threshold=5)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        # 3 failures
        for _ in range(3):
            try:
                client.get_movie_details(550)
            except TMDBClientError:
                pass

        assert client.stats.consecutive_transport_failures == 3

        # 1 success — should reset counter
        result = client.get_movie_details(550)
        assert result["title"] == "Fight Club"
        assert client.stats.consecutive_transport_failures == 0
        assert client.stats.circuit_breaker_triggered is False

        # 3 more failures — still below threshold of 5
        for _ in range(3):
            try:
                client.get_movie_details(550)
            except TMDBClientError:
                pass

        assert client.stats.consecutive_transport_failures == 3
        assert client.stats.circuit_breaker_triggered is False


def test_connection_refused_triggers_circuit_breaker():
    """ConnectionRefusedError must be classified as transport failure and
    counted toward circuit breaker threshold."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("ConnectionRefused: Connection refused", request=request)

    cfg = _make_config(max_retries=0, rate_limit_rps=0, circuit_breaker_threshold=3)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        for _ in range(3):
            try:
                client.get_movie_details(550)
            except TMDBClientError:
                pass

        assert client.stats.circuit_breaker_triggered is True
        assert calls == 3


def test_proxy_connection_failure_triggers_circuit_breaker():
    """ProxyError must be classified as transport failure and trigger circuit breaker."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ProxyError("ProxyError: proxy connection refused", request=request)

    cfg = _make_config(max_retries=0, rate_limit_rps=0, circuit_breaker_threshold=2)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        for _ in range(2):
            try:
                client.search_movies("Test")
            except TMDBClientError:
                pass

        assert client.stats.circuit_breaker_triggered is True
        assert "ProxyError" in client.stats.circuit_breaker_reason


def test_http_timeout_retry_bounded_by_budget():
    """Timeout retries must respect the request budget and not exceed it."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("Read timed out", request=request)

    cfg = _make_config(max_retries=10, rate_limit_rps=0, max_total_requests=5)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
        initial_requests_total=0,
    ) as client:
        # First call: uses attempts until budget exhausted
        with pytest.raises(TMDBClientError):
            client.get_movie_details(550)
        assert client.stats.requests_total <= 5

        # Second call: should be immediately budget-exhausted
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(551)
        assert exc_info.value.code == "tmdb_budget_exhausted"


def test_5xx_bounded_retries_preserve_budget():
    """5xx retries must respect max_retries and not inflate budget beyond limits."""
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway")

    cfg = _make_config(max_retries=2, rate_limit_rps=0, max_total_requests=10)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda s: sleeps.append(s),
    ) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(550)
        assert exc_info.value.code == TMDB_UPSTREAM_ERROR
        assert client.stats.requests_total == 3  # 1 initial + 2 retries
        assert client.stats.retry_count == 2


def test_budget_exhaustion_stops_immediately():
    """When budget is at the limit, requests must be rejected before making
    any HTTP call."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"id": 550, "title": "Fight Club"})

    cfg = _make_config(rate_limit_rps=0, max_total_requests=5)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
        initial_requests_total=5,  # Already at budget
    ) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(550)
        assert exc_info.value.code == TMDB_BUDGET_EXHAUSTED
        assert calls == 0  # No HTTP call was made


def test_checkpoint_resume_preserves_budget():
    """initial_requests_total must carry forward cumulative request count so
    resumed runs don't re-use budget already consumed."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"id": 550, "title": "Fight Club"})

    cfg = _make_config(rate_limit_rps=0, max_total_requests=74)
    # Simulate resume from checkpoint with 70 requests already consumed
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
        initial_requests_total=70,
    ) as client:
        assert client.stats.requests_total == 70
        # Should allow 4 more requests (70+4=74 budget)
        for i in range(4):
            client.get_movie_details(550 + i)
        assert client.stats.requests_total == 74

        # 75th should be rejected
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(999)
        assert exc_info.value.code == TMDB_BUDGET_EXHAUSTED


def test_no_repeated_processing_after_circuit_breaker():
    """After circuit breaker triggers, no further HTTP requests should be made
    even if the caller attempts multiple operations."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError(
            "[WinError 10054] Connection reset",
            request=request,
        )

    cfg = _make_config(max_retries=0, rate_limit_rps=0, circuit_breaker_threshold=3)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        # Trigger circuit breaker
        for _ in range(3):
            try:
                client.get_movie_details(550)
            except TMDBClientError:
                pass

        assert client.stats.circuit_breaker_triggered is True
        calls_after_trigger = calls

        # Attempt 10 more operations — none should reach the handler
        for i in range(10):
            with pytest.raises(TMDBClientError) as exc_info:
                client.get_movie_details(1000 + i)
            assert exc_info.value.code == TMDB_CIRCUIT_OPEN

        assert calls == calls_after_trigger  # No new HTTP calls
        assert client.stats.circuit_breaker_rejections == 10


def test_tls_error_uses_correct_error_code():
    """Transport failures should use TMDB_TLS_HANDSHAKE_FAILED error code
    rather than generic TMDB_NETWORK_ERROR."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "[WinError 10054] An existing connection was forcibly closed",
            request=request,
        )

    cfg = _make_config(max_retries=0, rate_limit_rps=0, circuit_breaker_threshold=100)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(550)
        assert exc_info.value.code == TMDB_TLS_HANDSHAKE_FAILED


def test_generic_network_error_uses_network_error_code():
    """Non-transport network errors should still use TMDB_NETWORK_ERROR code."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.DecodingError("UTF-8 decode error", request=request)

    cfg = _make_config(max_retries=0, rate_limit_rps=0, circuit_breaker_threshold=100)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(550)
        assert exc_info.value.code == TMDB_NETWORK_ERROR


def test_no_credentials_in_error_messages():
    """TMDBClientError messages must never contain the API token value."""
    secret = "eyJhbGciOiJIUzI1NiJ9.SUPER_SECRET_VALUE_DO_NOT_LEAK"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"Connection failed with token {secret}",
            request=request,
        )

    cfg = _make_config(read_access_token=secret, max_retries=0, rate_limit_rps=0)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        with pytest.raises(TMDBClientError) as exc_info:
            client.get_movie_details(550)
        assert secret not in str(exc_info.value)
        assert secret not in exc_info.value.message
        assert "[REDACTED]" in exc_info.value.message


def test_circuit_breaker_stats_in_to_dict():
    """Circuit breaker fields must be serialized in to_dict() for checkpoint persistence."""
    from app.services.tmdb_client import TMDBClientStats

    stats = TMDBClientStats()
    stats.consecutive_transport_failures = 5
    stats.circuit_breaker_triggered = True
    stats.circuit_breaker_reason = "NETWORK/ConnectError: WinError 10054"
    stats.circuit_breaker_rejections = 3

    d = stats.to_dict()
    assert d["consecutive_transport_failures"] == 5
    assert d["circuit_breaker_triggered"] is True
    assert d["circuit_breaker_reason"] == "NETWORK/ConnectError: WinError 10054"
    assert d["circuit_breaker_rejections"] == 3


def test_http_429_retry_after_header_respected():
    """HTTP 429 with Retry-After header must respect the specified wait time and
    clamp to max_retry_after_seconds."""
    sleeps: list[float] = []
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls <= 2:
            return httpx.Response(429, headers={"Retry-After": "3.0"}, json={})
        return httpx.Response(200, json={"id": 550, "title": "Fight Club"})

    cfg = _make_config(max_retries=3, max_retry_after_seconds=2.0, rate_limit_rps=0)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda s: sleeps.append(s),
    ) as client:
        result = client.get_movie_details(550)
        assert result["title"] == "Fight Club"
        # Retry-After=3.0 should be clamped to max_retry_after_seconds=2.0
        assert sleeps == [2.0, 2.0]
        assert client.stats.http_429_count == 2


def test_failed_request_latency_recorded():
    """Failed requests must still record latency for separate reporting."""
    clock_now = 100.0

    def fake_clock() -> float:
        return clock_now

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal clock_now, calls
        calls += 1
        clock_now += 0.3  # Simulate 300ms per attempt
        raise httpx.ConnectError(
            "[WinError 10054] Connection reset",
            request=request,
        )

    cfg = _make_config(max_retries=0, rate_limit_rps=0, circuit_breaker_threshold=100)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
        clock_fn=fake_clock,
    ) as client:
        with pytest.raises(TMDBClientError):
            client.get_movie_details(550)
        # Latency should be recorded even for failed requests
        assert len(client.stats.latencies_ms) == 1
        assert client.stats.latencies_ms[0] == 300.0  # 0.3s = 300ms
        # No successful latencies
        assert client.stats.requests_succeeded == 0


def test_circuit_breaker_disabled_with_zero_threshold():
    """Circuit breaker must not fire when threshold is set to 0 (disabled)."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError(
            "[WinError 10054] Connection reset",
            request=request,
        )

    cfg = _make_config(max_retries=0, rate_limit_rps=0, circuit_breaker_threshold=0)
    with TMDBClient(
        config=cfg,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
    ) as client:
        for _ in range(10):
            try:
                client.get_movie_details(550)
            except TMDBClientError:
                pass

        # Circuit breaker should NOT trigger when threshold is 0
        assert client.stats.circuit_breaker_triggered is False
        assert calls == 10
        assert client.stats.consecutive_transport_failures == 10

