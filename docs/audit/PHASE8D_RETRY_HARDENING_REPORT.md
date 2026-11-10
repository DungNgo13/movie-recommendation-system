# Phase 8D — Retry Hardening & Circuit Breaker Report (Báo cáo cải tiến cơ chế thử lại và Circuit Breaker)

**Date**: 2026-11-10  
**Phase**: Phase 8D — Controlled Live TMDB Pilot (40 movies)  
**Scope**: Circuit breaker implementation for `TMDBClient` transport failure protection  
**Test Suite**: 28 new tests added, 44/44 TMDB tests pass

---

## 1. Tóm tắt thay đổi / Change Summary

After the Phase 8D pilot failed with 74/74 HTTP attempts exhausted on TLS
handshake errors, a **circuit breaker** mechanism was implemented in
`TMDBClient._request_json()` to detect persistent transport-level failures and
fail-fast, preserving the remaining request budget for future retry attempts.

| Change | Description |
|--------|-------------|
| **New error codes** | `TMDB_TLS_HANDSHAKE_FAILED`, `TMDB_CIRCUIT_OPEN` in `api_errors.py` |
| **Transport failure classifier** | `_is_transport_failure()` function with 12 pattern matchers |
| **Circuit breaker config** | `TMDBConfig.circuit_breaker_threshold` (default: 5) |
| **Circuit breaker telemetry** | 4 new fields in `TMDBClientStats` |
| **Circuit breaker logic** | Integrated into `_request_json()` retry loop |
| **Reset mechanism** | HTTP 200 resets consecutive failure counter |
| **Automated tests** | 28 new tests covering all circuit breaker behaviors |

---

## 2. Vấn đề trước khi cải tiến / Problem Before

### 2.1 Budget Waste in run_001

| Metric | Value |
|--------|-------|
| **Total HTTP attempts** | 74 (100% of budget) |
| **Successful responses** | 0 |
| **Unique error type** | 1 (`[WinError 10054]` TLS handshake reset) |
| **Movies that attempted API calls** | 19 |
| **Movies blocked by budget exhaustion** | 21 |
| **Retries executed** | 55 (all wasted on identical error) |
| **Total execution time** | ~86 seconds (mostly backoff waits) |
| **Budget remaining for retry** | 0 |

### 2.2 Behavior Analysis

Without a circuit breaker, `_request_json()` retried each movie up to
`max_retries=3` times (4 total attempts per movie), even though every failure
was the same transport-level error. The system had no mechanism to detect that
the network path was broken and that retries were futile.

```
Movie 1: attempt 1 → WinError 10054 → wait 1s → attempt 2 → WinError 10054 →
         wait 2s → attempt 3 → WinError 10054 → wait 4s → attempt 4 → FAIL
Movie 2: attempt 5 → WinError 10054 → wait 1s → attempt 6 → WinError 10054 →
         ...same pattern...
...
Movie 19 (partial): attempt 73 → WinError 10054 → wait 1s → attempt 74 →
                     BUDGET EXHAUSTED
Movies 20-40: NOT_ATTEMPTED_BUDGET_EXHAUSTED
```

**Result**: 74 attempts consumed, 55 retries wasted, 0 information gained
after the first few failures.

---

## 3. Phân loại lỗi vận chuyển / Transport Failure Classification

### 3.1 `_is_transport_failure()` Implementation

**File**: `backend/app/services/tmdb_client.py`

The function classifies exceptions as transport-level (network path broken) vs.
HTTP-level (server reachable but returning errors):

```python
_TRANSPORT_FAILURE_PATTERNS: tuple[str, ...] = (
    "WinError 10054",        # Connection reset by remote host (Windows)
    "WinError 10053",        # Connection aborted by software (Windows)
    "ConnectionReset",       # Generic connection reset
    "ConnectionRefused",     # Connection refused
    "ConnectionAborted",     # Connection aborted
    "ConnectError",          # httpx connect error
    "SSL",                   # SSL/TLS errors
    "handshake",             # TLS handshake failures
    "TLS",                   # TLS protocol errors
    "CERTIFICATE",           # Certificate validation errors
    "ProxyError",            # Proxy connection failures
    "SOCKS",                 # SOCKS proxy errors
)
```

### 3.2 Classification Logic

```python
def _is_transport_failure(exc: Exception) -> bool:
    exc_str = str(exc)
    exc_type = type(exc).__name__
    for pattern in _TRANSPORT_FAILURE_PATTERNS:
        if pattern in exc_str or pattern in exc_type:
            return True
    return False
```

The function checks both the exception message (`str(exc)`) and exception type
name (`type(exc).__name__`) against the pattern list. This catches:
- `ConnectionResetError: [WinError 10054] ...` — matches `WinError 10054`, `ConnectionReset`
- `httpx.ConnectError: ...SSL...` — matches `ConnectError`, `SSL`
- `ssl.SSLCertVerificationError` — matches `SSL`, `CERTIFICATE`
- `httpx.ProxyError` — matches `ProxyError`

### 3.3 Why Transport vs. HTTP Distinction Matters

| Failure Type | Example | Network Path | Retry Useful? |
|-------------|---------|--------------|---------------|
| **Transport** | TLS reset, connection refused | Broken | ❌ No — same path, same failure |
| **HTTP 429** | Rate limited | Working | ✅ Yes — wait and retry |
| **HTTP 5xx** | Server error | Working | ✅ Yes — transient server issue |
| **HTTP 401** | Unauthorized | Working | ❌ No — credentials issue |
| **HTTP 404** | Not found | Working | ❌ No — resource doesn't exist |

---

## 4. Thiết kế Circuit Breaker / Circuit Breaker Design

### 4.1 New Error Codes

**File**: `backend/app/core/api_errors.py`

```python
TMDB_TLS_HANDSHAKE_FAILED = "tmdb_tls_handshake_failed"
TMDB_CIRCUIT_OPEN = "tmdb_circuit_open"
```

| Code | Meaning | Retryable |
|------|---------|-----------|
| `tmdb_tls_handshake_failed` | Transport-level failure detected (TLS/connection) | Yes (within retry loop) |
| `tmdb_circuit_open` | Circuit breaker triggered — all subsequent requests rejected | No (immediate rejection) |

### 4.2 Configuration

**File**: `backend/app/services/tmdb_client.py` — `TMDBConfig`

```python
@dataclass
class TMDBConfig:
    ...
    circuit_breaker_threshold: int = 5
```

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `circuit_breaker_threshold` | 5 | 0 = disabled, 1+ = active | Number of consecutive transport failures before circuit opens |

### 4.3 Telemetry Fields

**Class**: `TMDBClientStats`

```python
@dataclass
class TMDBClientStats:
    ...
    consecutive_transport_failures: int = 0
    circuit_breaker_triggered: bool = False
    circuit_breaker_reason: str = ""
    circuit_breaker_rejections: int = 0
```

| Field | Type | Description |
|-------|------|-------------|
| `consecutive_transport_failures` | `int` | Running count of consecutive transport failures; resets to 0 on HTTP 200 |
| `circuit_breaker_triggered` | `bool` | `True` once threshold is reached; remains `True` for the client's lifetime |
| `circuit_breaker_reason` | `str` | Human-readable reason including error class and message |
| `circuit_breaker_rejections` | `int` | Number of requests rejected after circuit opened |

### 4.4 Circuit Breaker Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ _request_json(endpoint, params)                                 │
│                                                                 │
│  ┌──────────────────────────────────────────┐                   │
│  │ 1. Check circuit_breaker_triggered       │                   │
│  │    → If True: reject immediately         │──→ TMDB_CIRCUIT_  │
│  │      (increment rejections counter)      │    OPEN error     │
│  └──────────────┬───────────────────────────┘                   │
│                 │ (circuit closed)                               │
│                 ▼                                                │
│  ┌──────────────────────────────────────────┐                   │
│  │ 2. Check budget (max_total_requests)     │                   │
│  │    → If exhausted: raise BUDGET_EXHAUSTED│                   │
│  └──────────────┬───────────────────────────┘                   │
│                 │ (budget available)                             │
│                 ▼                                                │
│  ┌──────────────────────────────────────────┐                   │
│  │ 3. Execute HTTP GET                      │                   │
│  └────┬────────────┬────────────────────────┘                   │
│       │            │                                            │
│    Success      Exception                                       │
│       │            │                                            │
│       ▼            ▼                                            │
│  ┌─────────┐  ┌──────────────────────────────────┐              │
│  │ HTTP 200 │  │ 4. _is_transport_failure(exc)?   │              │
│  │ → reset  │  │    → Yes: increment consecutive  │              │
│  │   counter│  │      failures counter            │              │
│  │   to 0   │  │    → No: standard retry logic    │              │
│  └─────────┘  └──────────────┬───────────────────┘              │
│                              │                                  │
│                              ▼                                  │
│               ┌──────────────────────────────────┐              │
│               │ 5. consecutive >= threshold?      │              │
│               │    → Yes: SET circuit_breaker_    │              │
│               │      triggered = True             │              │
│               │      RAISE TMDB_CIRCUIT_OPEN      │              │
│               │    → No: retry with backoff       │              │
│               └──────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### 4.5 Integration Points in `_request_json()`

The circuit breaker is integrated at two points in `_request_json()`:

1. **Entry guard** (line ~435): Checks `circuit_breaker_triggered` before any
   HTTP attempt. If triggered, immediately rejects with `TMDB_CIRCUIT_OPEN`.

2. **Exception handlers** (lines ~491–563): After catching `httpx.TimeoutException`
   or `httpx.RequestError`, calls `_is_transport_failure(exc)`. If True,
   increments `consecutive_transport_failures` and checks against threshold.

### 4.6 Reset Mechanism

On HTTP 200 success (line ~601):
```python
self.stats.consecutive_transport_failures = 0
```

This resets the failure counter when the network path is confirmed working,
allowing the circuit breaker to re-arm for future failure detection.

---

## 5. So sánh trước/sau / Before/After Comparison

### 5.1 Scenario: 40-movie pilot with broken TLS (identical to run_001)

| Metric | Before (run_001) | After (with circuit breaker, threshold=5) |
|--------|-------------------|-------------------------------------------|
| **Attempts before detection** | 74 (entire budget) | ~5 (first 5 transport failures) |
| **Budget consumed** | 74/74 (100%) | ~5/74 (6.8%) |
| **Budget preserved** | 0 | ~69 (93.2%) |
| **Movies attempted** | 19 | ~2 (5 failures across ~2 movies) |
| **Movies rejected by circuit breaker** | 0 | ~38 |
| **Error classification** | `tmdb_network_error` (generic) | `tmdb_tls_handshake_failed` → `tmdb_circuit_open` |
| **Time wasted on retries** | ~86 seconds | ~10–15 seconds |
| **Actionable signal** | Post-hoc analysis required | Immediate: "circuit breaker OPEN" in logs |

### 5.2 Scenario: Transient failure (3 consecutive then recovery)

| Metric | Before | After (with circuit breaker, threshold=5) |
|--------|--------|-------------------------------------------|
| **Behavior** | Retry per-movie (3 retries each) | Consecutive counter reaches 3, then resets on success |
| **Circuit triggered** | N/A | No (3 < 5 threshold) |
| **Impact** | Normal retry behavior | Normal retry behavior (no change) |

The threshold of 5 ensures that **transient** failures (1–4 consecutive) do not
trigger the circuit breaker, while **persistent** failures (5+) are detected
and stopped quickly.

---

## 6. Bảo vệ ngân sách / Budget Protection Analysis

### 6.1 Budget Savings Estimate

For a failure scenario identical to run_001 (all TLS failures):

```
Without circuit breaker:
  Attempts used = min(budget, movies × (1 + max_retries))
                = min(74, 40 × 4) = 74
  Budget remaining = 0

With circuit breaker (threshold=5):
  Attempts used = threshold = 5
  Budget remaining = 74 - 5 = 69
  Savings = 69/74 = 93.2%
```

### 6.2 Budget Protection Matrix

| Failure Pattern | Without CB | With CB (t=5) | Savings |
|----------------|------------|---------------|---------|
| All transport failures (run_001) | 74 attempts | 5 attempts | 93.2% |
| Transport failure after 20 successes | 54 attempts on failures | 5 attempts on failures | 90.7% |
| Intermittent (alternating success/fail) | N/A | CB never triggers | 0% (correct: retries are useful) |
| HTTP 429 rate limiting | N/A | CB never triggers | 0% (correct: not transport failure) |

### 6.3 Preserved Budget Utility

The 69 preserved attempts can be used in `phase8d_run_002` after the network
issue is resolved:
- 37 movies with TMDB IDs × 2 requests each (en-US + vi-VN) = 74 planned
- With 69 preserved + new authorization, sufficient for most movies

---

## 7. Kiểm thử tự động / Automated Tests

### 7.1 Test Coverage

**28 new tests** added to the TMDB test suite, covering:

| Test Category | Count | Description |
|---------------|-------|-------------|
| Transport failure classification | 8 | Verify `_is_transport_failure()` for each pattern |
| Circuit breaker triggering | 5 | Verify trigger at threshold, not before |
| Circuit breaker rejection | 4 | Verify immediate rejection after trigger |
| Reset on success | 3 | Verify counter resets on HTTP 200 |
| Error code assignment | 3 | Verify `TMDB_TLS_HANDSHAKE_FAILED` vs `TMDB_NETWORK_ERROR` |
| Threshold configuration | 3 | Verify threshold=0 (disabled), threshold=1, custom values |
| Telemetry accuracy | 2 | Verify stats fields are correctly populated |

### 7.2 Test Suite Results

```
44/44 TMDB tests pass (16 existing + 28 new)
```

All existing tests continue to pass — the circuit breaker does not affect
normal operation when no transport failures occur.

---

## 8. Cấu hình / Configuration

### 8.1 Default Configuration

```python
TMDBConfig(
    circuit_breaker_threshold=5,   # Trigger after 5 consecutive transport failures
    max_retries=3,                 # Up to 3 retries per request
    backoff_base_seconds=0.5,      # Exponential backoff: 0.5s, 1s, 2s, ...
    max_retry_after_seconds=15.0,  # Cap backoff at 15 seconds
)
```

### 8.2 Disabling Circuit Breaker

Set `circuit_breaker_threshold=0` to disable the circuit breaker entirely:

```python
config = TMDBConfig(circuit_breaker_threshold=0)
client = TMDBClient(config=config)
```

When disabled, behavior is identical to pre-circuit-breaker implementation.

### 8.3 Recommended Threshold Values

| Value | Use Case |
|-------|----------|
| 0 | Disabled (legacy behavior) |
| 3 | Aggressive — fast detection, risk of false positive on transient failures |
| **5** | **Default — balanced detection speed and false positive avoidance** |
| 10 | Conservative — very tolerant of transient failures |

---

## 9. References / Tài liệu tham chiếu

| Document | Path |
|----------|------|
| TMDBClient implementation | `backend/app/services/tmdb_client.py` |
| API error codes | `backend/app/core/api_errors.py` |
| TLS root cause analysis | `docs/audit/PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md` |
| Network diagnostics | `docs/audit/PHASE8D_NETWORK_DIAGNOSTICS.md` |
| Recovery plan | `docs/audit/PHASE8D_RECOVERY_PLAN.md` |
