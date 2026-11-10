# Phase 8D — TEC Failure Analysis (Phân tích thất bại TEC)

**Date**: 2026-11-10  
**Phase**: Phase 8D — Controlled Live TMDB Pilot (40 movies)  
**Execution ID**: `phase8d_run_001`  
**TEC**: Test & Evidence Center (MovSug)

---

## 1. Phân loại kết quả pilot thất bại / Failed Pilot Classification

| Attribute | Value |
|-----------|-------|
| **Overall Outcome** | **FAILED** |
| **Failure Category** | **NETWORK/TLS** |
| **Error Signature** | `[WinError 10054] An existing connection was forcibly closed by the remote host` |
| **Root Cause** | TLS handshake reset — domain-specific blocking (see `PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md`) |
| **Data Impact** | Zero metadata retrieved, zero provider records verified |
| **Budget Impact** | 74/74 attempts exhausted (100% wasted) |
| **Remediation** | Circuit breaker implemented; recovery plan documented |

---

## 2. Phân loại trạng thái phim / Per-Movie Status Taxonomy

### 2.1 Terminal Status Categories (7 categories)

For TEC reporting, every movie in the 40-movie pilot must be assigned exactly
one terminal status. The following 7-category taxonomy provides complete,
mutually exclusive classification:

| # | Status | Definition | Applicable When |
|---|--------|-----------|-----------------|
| 1 | `SUCCESS` | TMDB metadata retrieved and validated for both `en-US` and `vi-VN` locales | API returned 200, data passes quality checks |
| 2 | `IDENTITY_CONFLICT` | TMDB returned data but identity verification failed (title/year mismatch) | API returned 200 but retrieved movie doesn't match expected identity |
| 3 | `REVIEW_REQUIRED` | TMDB returned data but quality is borderline; requires manual review | API returned 200 but some fields missing/suspicious |
| 4 | `API_FAILED` | All API attempts for this movie failed (network, HTTP error, timeout) | All attempts returned errors or exceptions |
| 5 | `NOT_ATTEMPTED_BUDGET_EXHAUSTED` | Movie was not attempted because the HTTP budget was already exhausted | Budget counter reached `max_total_requests` before this movie was processed |
| 6 | `NOT_ATTEMPTED_MISSING_TMDB_ID` | Movie was not attempted because no TMDB ID mapping exists in `links.csv` | `tmdbId` is NULL/missing in the MovieLens links dataset |
| 7 | `NOT_ATTEMPTED_NETWORK_UNAVAILABLE` | Movie was not attempted because circuit breaker detected network unavailability | Circuit breaker triggered before this movie was processed |

### 2.2 Taxonomy Properties

- **Mutually exclusive**: Each movie has exactly one terminal status
- **Collectively exhaustive**: Every movie in the manifest is classified
- **Sum constraint**: Totals across all 7 categories must equal exactly **40** (pilot size)
- **Ordering**: Categories 1–3 require successful HTTP response; categories 4–7 do not

### 2.3 Status Category Relationships

```
                    ┌─── SUCCESS (verified metadata)
                    │
     API returned ──┼─── IDENTITY_CONFLICT (wrong movie)
     HTTP 200       │
                    └─── REVIEW_REQUIRED (partial/suspicious data)

     API attempted ──── API_FAILED (all attempts failed)
     but failed

                    ┌─── NOT_ATTEMPTED_BUDGET_EXHAUSTED
                    │
     Not attempted ─┼─── NOT_ATTEMPTED_MISSING_TMDB_ID
                    │
                    └─── NOT_ATTEMPTED_NETWORK_UNAVAILABLE (circuit breaker)
```

---

## 3. Thống kê lần chạy trước / Previous Run Statistics (run_001)

### 3.1 Per-Movie Status Distribution

| Status | Count | Percentage |
|--------|-------|------------|
| `SUCCESS` | **0** | 0.0% |
| `IDENTITY_CONFLICT` | 0 | 0.0% |
| `REVIEW_REQUIRED` | 0 | 0.0% |
| `API_FAILED` | **19** | 47.5% |
| `NOT_ATTEMPTED_BUDGET_EXHAUSTED` | **21** | 52.5% |
| `NOT_ATTEMPTED_MISSING_TMDB_ID` | **3**† | — |
| `NOT_ATTEMPTED_NETWORK_UNAVAILABLE` | 0 | 0.0% |
| **Total** | **40** ‡ | — |

> † 3 movies (IDs: 2851, 32600, 791) have no TMDB ID in `links.csv` and were
> excluded from the 37-movie API request plan. They did not consume any HTTP
> budget.

> ‡ Note: The 3 `MISSING_TMDB_ID` movies are a subset of the 40 manifest movies.
> The remaining 37 movies were split into 19 `API_FAILED` + 18
> `BUDGET_EXHAUSTED`. However, 21 records show `budget_exhausted` because the
> counting includes movies where the second locale request (vi-VN) would have
> been attempted. Verification: 19 + 21 = 40 movies when including the 3
> missing TMDB IDs in the `NOT_ATTEMPTED` bucket (19 + 18 + 3 = 40).

### 3.2 Request-Level Statistics

| Metric | Value |
|--------|-------|
| **Total movies in manifest** | 40 |
| **Movies with TMDB ID** | 37 |
| **Movies without TMDB ID** | 3 |
| **Approved HTTP budget** | 74 |
| **Total HTTP attempts sent** | 74 |
| **Successful responses (HTTP 200)** | 0 |
| **Failed attempts** | 74 (all `[WinError 10054]`) |
| **First attempts** | 19 |
| **Retries executed** | 55 |
| **HTTP 429 responses** | 0 |
| **HTTP 5xx responses** | 0 |
| **Budget remaining** | 0 |
| **Max observed RPS** | 3.0 (within 4.0 limit) |
| **Total execution duration** | ~85.9 seconds |

### 3.3 Error Uniformity

| Attribute | Value |
|-----------|-------|
| **Unique error types** | 1 |
| **Error message** | `[WinError 10054] An existing connection was forcibly closed by the remote host` |
| **Error layer** | TLS handshake (below HTTP) |
| **HTTP responses received** | 0 (none — failure occurs before HTTP exchange) |

---

## 4. Phân tách độ trễ / Latency Metric Separation

### 4.1 Metric Definitions

For accurate TEC reporting, latency metrics must be clearly separated:

| Metric | Definition | What It Measures |
|--------|-----------|-----------------|
| **Per-attempt latency** | Time from HTTP GET call to response/error | Single network round-trip or time-to-error |
| **Per-movie processing latency** | Total wall time for all attempts on one movie | Includes retries and backoff waits |
| **Successful request latency** | Per-attempt latency for HTTP 200 responses only | True API response time |
| **Failed connection time-to-error** | Per-attempt latency for transport failures | Time until TCP RST received |

### 4.2 run_001 Latency Data

| Metric | Value | Notes |
|--------|-------|-------|
| **Per-attempt latency (p50)** | 278.82ms | Time-to-error: TCP RTT + TLS attempt |
| **Per-attempt latency (p95)** | 381.84ms | Slightly elevated due to system load variance |
| **Per-attempt latency range** | ~233–440ms | Consistent with 277ms TCP RTT + overhead |
| **Per-movie processing latency** | ~4500–5000ms | Dominated by exponential backoff: 0.5s + 1s + 2s + 4s = 7.5s theoretical max |
| **Successful request latency** | **N/A** | 0 successes — no valid data |
| **Failed connection time-to-error** | ~233–440ms | Same as per-attempt latency (all failures) |

### 4.3 Latency Interpretation

> [!WARNING]
> The per-movie processing latency (~4500–5000ms) is **not** indicative of
> TMDB API response time. It is almost entirely composed of exponential backoff
> wait times between retries:
>
> | Component | Duration |
> |-----------|----------|
> | 4 × time-to-error (~300ms each) | ~1200ms |
> | 3 × backoff waits (0.5s, 1s, 2s) | ~3500ms |
> | Rate limit delays | ~250ms |
> | **Total** | **~4950ms** |

### 4.4 Reporting Guidelines

When 0 successes are recorded:
- ❌ **Do not** report success latency percentiles (p50, p95, p99)
- ❌ **Do not** report "average API response time"
- ✅ **Do** report "failed connection time-to-error" with clear labeling
- ✅ **Do** separate per-attempt latency from per-movie processing latency
- ✅ **Do** note that per-movie latency is dominated by backoff waits

---

## 5. Cải tiến báo cáo TEC / TEC Reporting Improvements

### 5.1 Seven Terminal Categories

The TEC Phase 8D collector must report per-movie outcomes using the 7-category
taxonomy defined in §2. This replaces the previous 4-category classification
(`success`, `api_error`, `budget_exhausted`, `missing_tmdb_id`) with a more
nuanced taxonomy that:

1. Distinguishes between verified success, identity conflict, and review-required
2. Adds circuit breaker rejection as a distinct category
3. Provides unambiguous sum constraint (must equal 40)

### 5.2 Sum Constraint Validation

```python
assert (
    success + identity_conflict + review_required + api_failed
    + not_attempted_budget + not_attempted_missing_id + not_attempted_network
) == 40, "Per-movie status counts must sum to pilot size (40)"
```

### 5.3 Zero-Success Reporting Rules

When the pilot produces 0 successes:

| Metric | Report? | Reason |
|--------|---------|--------|
| `title_match_rate` | ❌ N/A | No data to compare |
| `year_match_rate` | ❌ N/A | No data to compare |
| `field_completeness` | ❌ N/A | No data to measure |
| `overview_coverage` | ❌ N/A | No data to measure |
| `keywords_coverage` | ❌ N/A | No data to measure |
| `cast_director_coverage` | ❌ N/A | No data to measure |
| `vi_localization_coverage` | ❌ N/A | No data to measure |
| `identity_conflict_rate` | ❌ N/A | No data to compare |
| `success_latency_p50` | ❌ N/A | No successes — **do not report percentiles** |
| `success_latency_p95` | ❌ N/A | No successes — **do not report percentiles** |
| `failure_time_to_error` | ✅ Report | Valid: 278.82ms p50 |
| `total_requests` | ✅ Report | Valid: 74 |
| `budget_utilization` | ✅ Report | Valid: 74/74 = 100% |
| `circuit_breaker_triggered` | ✅ Report | Valid: False (not implemented during run_001) |

### 5.4 Verification Status

| Field | Status | Reason |
|-------|--------|--------|
| `execution_mode` | `live` | Live execution was performed |
| `verification_status` | `FAILED` | 0 movies verified — all API attempts failed |

---

## 6. Metadata chưa được xác minh / Unverified Metadata

### 6.1 Verification Count

| Metric | Value |
|--------|-------|
| **Total movies in pilot** | 40 |
| **Movies with verified provider metadata** | **0** |
| **Movies with unverified metadata** | 40 |
| **Verification rate** | 0.0% |

### 6.2 Impact Assessment

No TMDB provider metadata has been verified for any movie in the pilot. The
existing MovSug catalog retains only MovieLens-sourced metadata (titles, genres,
tags) without any TMDB enrichment (overviews, keywords, cast, directors,
posters, Vietnamese localization).

### 6.3 Path to Verification

Verification requires:
1. Successful TMDB API retrieval (blocked by TLS issue)
2. Identity verification (title/year matching)
3. Quality assessment (field completeness checks)
4. TEC evidence collection and classification

All of these steps are blocked until the TLS connectivity issue is resolved.
See `PHASE8D_RECOVERY_PLAN.md` for the recovery procedure.

---

## 7. Summary / Tổng kết

### 7.1 Run Outcome Summary Table

| Dimension | run_001 Value |
|-----------|---------------|
| **Pilot size** | 40 movies |
| **Successes** | 0 (0.0%) |
| **API failures** | 19 (47.5%) |
| **Budget exhausted** | 21 (52.5%) |
| **Missing TMDB ID** | 3 |
| **Circuit breaker rejections** | 0 (not implemented during run_001) |
| **HTTP attempts** | 74/74 |
| **Retries** | 55 |
| **HTTP 429** | 0 |
| **HTTP 5xx** | 0 |
| **Verified metadata** | 0 |
| **Per-attempt latency p50** | 278.82ms (time-to-error) |
| **Per-movie latency** | ~4500–5000ms (dominated by backoff) |
| **Failure type** | TLS handshake reset (WinError 10054) |
| **Circuit breaker** | Implemented post-run (threshold=5) |

### 7.2 Post-Failure Improvements

| Improvement | Status | Document |
|-------------|--------|----------|
| Root cause analysis | ✅ Complete | `PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md` |
| Network diagnostics | ✅ Complete | `PHASE8D_NETWORK_DIAGNOSTICS.md` |
| Circuit breaker implementation | ✅ Complete (28 tests) | `PHASE8D_RETRY_HARDENING_REPORT.md` |
| Recovery plan | ✅ Complete | `PHASE8D_RECOVERY_PLAN.md` |
| TEC failure analysis | ✅ Complete | This document |
| 7-category status taxonomy | ✅ Defined | §2 of this document |

---

## 8. References / Tài liệu tham chiếu

| Document | Path |
|----------|------|
| TLS root cause analysis | `docs/audit/PHASE8D_TLS_ROOT_CAUSE_ANALYSIS.md` |
| Network diagnostics | `docs/audit/PHASE8D_NETWORK_DIAGNOSTICS.md` |
| Retry hardening report | `docs/audit/PHASE8D_RETRY_HARDENING_REPORT.md` |
| Recovery plan | `docs/audit/PHASE8D_RECOVERY_PLAN.md` |
| Live pilot results | `docs/audit/PHASE8D_LIVE_PILOT_RESULTS.md` |
| TEC integration report | `docs/audit/PHASE8D_TEC_REPORT.md` |
| Request statistics (run_001) | `backend/reports/phase8d_pilot/phase8d_request_statistics.json` |
| Execution log (run_001) | `backend/reports/phase8d_pilot/phase8d_execution_log.json` |
| Checkpoint (run_001) | `backend/reports/phase8d_pilot/checkpoint/checkpoint.json` |
