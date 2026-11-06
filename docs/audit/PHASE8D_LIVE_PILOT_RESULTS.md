# MovSug Phase 8D — Controlled Live TMDB Pilot Execution & Evidence Report

**Date**: 2026-11-06  
**Phase**: Phase 8D — Controlled Live TMDB Pilot Execution and Evidence Collection  
**Approved Scope**: 40 manifest movies · Maximum 74 total HTTP attempts (including retries) · Maximum 4.0 RPS · `api.themoviedb.org` (HTTPS) only  
**Execution Status**: Authorized Live Execution Invoked → Safely Stopped at Operational Credential Gate (`tmdb_not_configured`, 0 HTTP requests sent)

---

## 1. Execution Scope and Authorization Evidence

### 1.1 Approved Scope vs. Enforced Implementation

| Parameter | Approved Limit | Enforced Value | Enforcement Mechanism |
| :--- | :--- | :--- | :--- |
| **Pilot Manifest Size** | 40 unique movies (`seed=8042`) | 40 unique movies (`seed=8042`) | Verified by SHA-256 manifest checksum (`d23fc802aefe509088127ede5d03009bc22354165d1b1adbc8f4906567d8800c`) |
| **Movies with TMDB ID (`links.csv`)** | 37 movies | 37 movies (2 planned requests/movie: `en-US` + `vi-VN`) | Direct `GET /movie/{tmdb_id}` lookup |
| **Movies without TMDB ID (`links.csv`)** | 3 movies (`2851`, `32600`, `791`) | 3 movies (`0` HTTP requests) | Marked `NOT_ATTEMPTED_MISSING_TMDB_ID` (`requires_manual_review=true`) |
| **Maximum Total HTTP Attempts** | **74 (including retries)** | **74 (`PHASE8D_APPROVED_MAX_REQUESTS = 74`)** | Enforced inside `TMDBClient._request_json()` immediately BEFORE every `self._client.get()` attempt and before any retry sleep |
| **Maximum Request Rate** | **4.0 requests/second** | **4.0 RPS (`PHASE8D_MAX_RPS = 4.0`)** | Enforced by `TMDBClient._enforce_rate_limit()` before every outbound HTTP attempt, including retries |
| **Target Host Allowlist** | `api.themoviedb.org` only | `{"api.themoviedb.org"}` over `https://` | Enforced by `TMDBClient._validate_base_url()` and `_validate_endpoint()` |
| **Production Database Writes** | Zero writes allowed | Zero writes (`0` SQLAlchemy/DB imports in Phase 8D) | Verified by `TestProductionIsolation` and preflight check #6 |
| **Concurrent Execution Protection** | Single active runner | Exclusive `O_CREAT \| O_EXCL` lockfile (`checkpoint/pilot.lock`) | Enforced by `_acquire_pilot_lock()` / `_release_pilot_lock()` |
| **Checkpoint Cumulative Persistence** | Preserve request count on resume | `cumulative_requests` saved before/after every HTTP attempt | Enforced via `on_attempt_callback` and `initial_requests_total` in `TMDBClient` |

### 1.2 Correction of the Request-Budget Mismatch (94 / 120 → 74)

During preflight inspection, three budget discrepancies were identified and fixed before live execution:

1. **Manifest & Default Cap Mismatch**: `generate_pilot_manifest()` previously added a 20-request retry buffer (`74 + 20 = 94`), and `PHASE8D_DEFAULT_REQUEST_BUDGET` defaulted to `120`. Both were corrected to the exact approved hard cap of **74 total HTTP attempts, including retries** (`estimated_api_requests: 74`, `estimated_retry_budget: 0`, `total_request_budget: 74`, `retries_included_in_budget: true`).
2. **Pre-Attempt Budget Counting Across Retries**: Previously, `run_live_pilot()` incremented `summary.total_requests` only once per outer method call, ignoring internal retries inside `TMDBClient._request_json()`. `TMDBConfig.max_total_requests = 74` is now enforced inside `TMDBClient._request_json()` immediately before every HTTP attempt (`200 OK`, `429`, `5xx`, timeouts, network errors, and `vi-VN` localization calls). Furthermore, if an HTTP attempt fails at `requests_total == 74`, `can_retry` evaluates to `False` so no 75th retry attempt is ever slept for or sent.
3. **Resumable Checkpoint Cumulative Accounting**: `checkpoint.json` now persists `cumulative_requests`, `stats_snapshot`, and `records_by_id` via `on_attempt_callback` on every HTTP attempt. Resuming an interrupted run initializes `TMDBClient(initial_requests_total=prior_requests)`, guaranteeing that interrupted + resumed runs can never exceed 74 total HTTP attempts.

### 1.3 Preflight Verification Summary (`phase8d_preflight_report.json`)

All 8 mandatory preflight checks passed (`preflight_passed: true`):

- **Check 1 (`1_manifest_40_unique_and_checksum`)**: `passed: true` — 40 unique movies, SHA-256 `d23fc802aefe509088127ede5d03009bc22354165d1b1adbc8f4906567d8800c`.
- **Check 2 (`2_max_http_attempt_budget_74`)**: `passed: true` — `config_request_budget: 74`, `manifest_total_request_budget: 74`, `approved_hard_cap: 74`, `retries_included: true`.
- **Check 3 (`3_global_rate_limiter_4_rps`)**: `passed: true` — `configured_rate_limit_rps: 4.0`, `max_allowed_rps: 4.0`, `covers_retries: true`.
- **Check 4 (`4_all_http_attempts_counted_pre_request`)**: `passed: true` — `TMDBClient._request_json` enforces `max_total_requests` and increments `stats.requests_total` before `client.get()` on every attempt/retry.
- **Check 5 (`5_checkpoint_preserves_cumulative_usage`)**: `passed: true` — `prior_completed_movies: 0`, `prior_cumulative_requests: 0`.
- **Check 6 (`6_zero_production_db_modifications`)**: `passed: true` — `allowlisted_hosts: ["api.themoviedb.org"]`, zero ORM/DB imports.
- **Check 7 (`7_research_output_isolation`)**: `passed: true` — isolated to `backend/reports/phase8d_pilot`.
- **Check 8 (`8_authorization_gates_operational`)**: `passed: true` — `--phase8d-live` (`true`), `PHASE8D_LIVE_AUTHORIZED=true`, `TMDB_ENABLE_LIVE_REQUESTS=true`, `api_token_present: false`.

---

## 2. Exact Request Counts and Rate-Limit Measurements

When the authorized live command was executed:

```powershell
cd d:\TLTN\movie-recommendation-system\backend
$env:PHASE8D_LIVE_AUTHORIZED="true"
$env:TMDB_ENABLE_LIVE_REQUESTS="true"
.\.venv\Scripts\python.exe -m app.recommendation_evaluation.cli --phase8d --phase8d-live
```

`TMDBClient._ensure_ready()` inspected the environment for `TMDB_API_READ_ACCESS_TOKEN`. Because `TMDB_API_READ_ACCESS_TOKEN` is not configured in `backend/.env` or the host environment, the operational credential gate stopped execution cleanly **before any network socket or HTTP request was opened**:

| Metric | Value | Source Artifact |
| :--- | :--- | :--- |
| **Approved HTTP Attempt Budget** | `74` | `phase8d_request_statistics.json` |
| **Total Outbound HTTP Attempts Sent** | `0` | `phase8d_request_statistics.json` |
| **Requests Succeeded (`200 OK`)** | `0` | `phase8d_request_statistics.json` |
| **Requests Failed** | `0` | `phase8d_request_statistics.json` |
| **Remaining Request Budget** | `74` | `phase8d_request_statistics.json` |
| **HTTP 429 Rate-Limit Responses** | `0` | `phase8d_request_statistics.json` |
| **HTTP 5xx Server Errors** | `0` | `phase8d_request_statistics.json` |
| **Retries Executed** | `0` | `phase8d_request_statistics.json` |
| **Configured Rate Limit** | `4.0 RPS` | `phase8d_request_statistics.json` |
| **Max Observed Rate** | `0.00 RPS` | `phase8d_request_statistics.json` |
| **Operational Blocker Code** | `tmdb_not_configured` | `phase8d_request_statistics.json` |
| **Operational Blocker Message** | `TMDB API read-access token is not configured.` | `phase8d_request_statistics.json` |

---

## 3. Provider Reliability Measurements

- **Live Network Contact**: `0` outbound requests were made because `TMDB_API_READ_ACCESS_TOKEN` is absent in the execution environment.
- **Controlled Transport Verification (`TestStrictBudgetEnforcement` & `test_tmdb_client.py`)**:
  - Verified HTTP `429` handling with `Retry-After` header parsing and bounded retry exhaustion.
  - Verified HTTP `5xx` (`503 Service Unavailable`) exponential backoff and bounded retry exhaustion.
  - Verified that when `max_total_requests` is reached during a retry sequence (e.g., 2 × `503` + 1 × `429` = 3 attempts with `max_total_requests=3`), the client halts immediately and raises `tmdb_budget_exhausted` / `tmdb_rate_limited` without sending a 4th attempt.

---

## 4. Identity Accuracy Assessment

All 40 manifest movies are accounted for in `phase8d_identity_matching_report.json`:

| Category | Movie Count | Verification Status | Notes |
| :--- | :---: | :--- | :--- |
| **Movies with TMDB ID in `links.csv`** | 37 | `NOT_ATTEMPTED` | Blocked prior to network call by missing `TMDB_API_READ_ACCESS_TOKEN` (`not_attempted_missing_credentials`) |
| **Movies without TMDB ID in `links.csv`** | 3 | `NOT_ATTEMPTED_MISSING_TMDB_ID` | MovieLens IDs `2851` (*Saturn 3 (1980)*, `tt0081454`), `32600` (*Eros (2004)*, `tt0377059`), and `791` (*The Last Klezmer (1994)*, `tt0113610`). Flagged `requires_manual_review=true` (`REVIEW_REQUIRED`) because 37 × 2 = 74 leaves 0 spare budget for `/find` or `/search` fallback. |
| **Total Manifest Movies** | **40** | **`NOT_RUN`** | 100% of manifest movies preserved in all reports |

Additionally, `_check_title_match()` was hardened during Phase 8D verification to:
1. Reject empty TMDB titles (`""`, `""` → `False`), eliminating a false-positive substring bug where `"" in ml_norm` previously evaluated to `True`.
2. Normalize MovieLens trailing articles (`"Wolf of Wall Street, The (2013)"` → `"the wolf of wall street"`) and parenthetical original titles (`"City of Men (Cidade dos Homens) (2007)"`) for accurate identity verification.

---

## 5. Metadata Completeness Before and After

From `phase8d_field_completeness.json` (across all 40 pilot movies):

| Metadata Field | Before Enrichment (MovieLens Baseline) | After Phase 8D Execution (`NOT_RUN` — Missing Token) |
| :--- | :---: | :---: |
| `title` (EN) | 40 / 40 (100.0%) | 40 / 40 (100.0%) |
| `genres` | 40 / 40 (100.0%) | 40 / 40 (100.0%) |
| `overview_en` | 0 / 40 (0.0%) | 0 / 40 (0.0% — `NOT_ATTEMPTED`) |
| `keywords` | 0 / 40 (0.0%) | 0 / 40 (0.0% — `NOT_ATTEMPTED`) |
| `cast` | 0 / 40 (0.0%) | 0 / 40 (0.0% — `NOT_ATTEMPTED`) |
| `director` | 0 / 40 (0.0%) | 0 / 40 (0.0% — `NOT_ATTEMPTED`) |
| `title_vi` | 0 / 40 (0.0%) | 0 / 40 (0.0% — `NOT_ATTEMPTED`) |
| `overview_vi` | 0 / 40 (0.0%) | 0 / 40 (0.0% — `NOT_ATTEMPTED`) |

---

## 6. Failures, Conflicts, Missing-ID Movies, and Unattempted Movies

Recorded in `phase8d_failure_report.json` and `phase8d_live_retrieval.log`:

1. **Operational Blocker (`blocker_code: "tmdb_not_configured"`)**:
   - **Cause**: `TMDB_API_READ_ACCESS_TOKEN` is not set in `backend/.env` or environment variables.
   - **Behavior**: Stopped cleanly at `TMDBClient._ensure_ready()` with `0` outbound HTTP requests.
   - **Exact Unblock Procedure**: Provide a valid TMDB v3 Read Access Token in `TMDB_API_READ_ACCESS_TOKEN` (via `backend/.env` or `$env:TMDB_API_READ_ACCESS_TOKEN`) and re-run the authorized command.
2. **Missing-TMDB-ID Movies (3 movies)**:
   - `movieId=2851` (*Saturn 3 (1980)*, `imdb_id=tt0081454`, `tmdb_id=None`)
   - `movieId=32600` (*Eros (2004)*, `imdb_id=tt0377059`, `tmdb_id=None`)
   - `movieId=791` (*Last Klezmer: Leopold Kozlowski, His Life and Music, The (1994)*, `imdb_id=tt0113610`, `tmdb_id=None`)
   - All 3 are preserved in the manifest and reports with `verification_status="NOT_ATTEMPTED_MISSING_TMDB_ID"` and `requires_manual_review=True`.
3. **Unattempted Movies with TMDB IDs (37 movies)**:
   - Preserved in `phase8d_per_movie_quality.csv` and `phase8d_data_quality.json` with `status="not_attempted_missing_credentials"`, `verification_status="NOT_ATTEMPTED"`, and `request_count=0`.

---

## 7. Snapshot Provenance and Checksums

Recorded in `backend/reports/phase8d_pilot/snapshots/phase8d_snapshot_manifest.json`:

| Artifact | Path | SHA-256 Checksum |
| :--- | :--- | :--- |
| **40-Movie Selection List** | `phase8d_pilot_manifest.json` (`movies` array) | `d23fc802aefe509088127ede5d03009bc22354165d1b1adbc8f4906567d8800c` |
| **Pilot Manifest JSON** | `backend/reports/phase8d_pilot/phase8d_pilot_manifest.json` | `7a2696347bc7d01203dec5d571e8584db0bb6e16432a6fc9d8a4e74758623bd5` |
| **Pilot Snapshot JSON** | `backend/reports/phase8d_pilot/snapshots/phase8d_pilot_snapshot.json` | `b317e5d419e343736780567c1c9fba018824e5dffcd607cf1352875483aa7505` |
| **MovieLens Dataset** | `backend/data/ml-latest-small` | `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86` |
| **Evaluation Split** | Temporal 80/10/10 split | `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67` |

- `production_db_modified`: `false`
- `historical_snapshots_overwritten`: `false`

---

## 8. Recommendation Impact Readiness Assessment

1. **Infrastructure & Budget Safety Readiness (`READY`)**:
   - The Phase 8D live retrieval pipeline, pre-attempt 74-request hard cap, 4.0 RPS rate limiter, checkpoint cumulative request persistence, exclusive lockfile concurrency guard, title/year verification, research snapshot isolation, and TEC collector integration are 100% implemented and verified by automated tests.
2. **Live Empirical Metadata Readiness (`BLOCKED_BY_MISSING_TOKEN`)**:
   - Because `TMDB_API_READ_ACCESS_TOKEN` was not present in the environment, `0` live TMDB responses were retrieved in this run (`verification_mode: "NOT_RUN"`).
   - In accordance with `PROJECT_RULES.md`, no mock or synthetic data is claimed as live provider evidence.
3. **Full-Catalog Enrichment Recommendation**:
   - Do **not** proceed to full-catalog live TMDB enrichment (9,734 movies / ~19,468 requests) until `TMDB_API_READ_ACCESS_TOKEN` is supplied and the 40-movie bounded pilot (74 HTTP attempts max) is executed and reviewed.

---

## 9. TEC Evidence Integration

Generated under `test_center/reports/tec-20261106-043815-7d93e0d/report/`:

- **JSON Report**: `test_center/reports/tec-20261106-043815-7d93e0d/report/summary.json`
- **Markdown Report**: `test_center/reports/tec-20261106-043815-7d93e0d/report/report.md`
- **Vietnamese Summary**: `test_center/reports/tec-20261106-043815-7d93e0d/report/bao_cao_tom_tat.md`
- **Self-Contained HTML Report**: `test_center/reports/tec-20261106-043815-7d93e0d/report/report.html`

---

## 10. Tóm Tắt Kết Quả Thực Thi Pilot Phase 8D (Bản Tiếng Việt Phục Vụ Khóa Luận)

### 10.1 Hiệu chỉnh phạm vi ủy quyền và cơ chế kiểm soát ngân sách (74 HTTP Attempts)
- Đã khắc phục triệt để sự sai lệch giữa ngân sách được phê duyệt (**74 lượt thử HTTP bao gồm cả retry**) và cấu hình cũ (94 trong manifest / 120 mặc định trong CLI).
- Bộ đếm ngân sách được thực thi ngay bên trong `TMDBClient._request_json()` **trước mỗi lần gọi HTTP thực tế** (`200 OK`, lỗi mạng, timeout, `HTTP 429`, `HTTP 5xx`, mọi lượt retry và yêu cầu bản địa hóa `vi-VN`). Nếu một lượt retry làm tổng số lượt gọi vượt quá 74, hệ thống sẽ từ chối gửi retry đó ngay lập tức (`TMDB_BUDGET_EXHAUSTED`).
- Tệp `checkpoint.json` lưu trữ lũy kế `cumulative_requests` trước và sau mỗi lượt gọi HTTP, kết hợp với cơ chế khóa độc quyền `pilot.lock`, đảm bảo việc tạm dừng/tiếp tục hoặc chạy đồng thời không bao giờ vượt quá giới hạn 74 yêu cầu hay vượt tốc độ tối đa 4 yêu cầu/giây (4.0 RPS).

### 10.2 Kết quả kiểm tra Preflight và thực thi lệnh Live được ủy quyền
- Toàn bộ **8/8 bài kiểm tra Preflight** đều đạt (`preflight_passed = true`), xác nhận danh sách 40 phim duy nhất (`seed = 8042`, mã băm SHA-256 `d23fc802aefe...`), ngân sách cứng 74 lượt thử HTTP, giới hạn tốc độ 4.0 RPS, cô lập dữ liệu nghiên cứu và không tác động đến cơ sở dữ liệu PostgreSQL/SQLite.
- Khi thực thi lệnh live đã được ủy quyền (`--phase8d --phase8d-live` với `PHASE8D_LIVE_AUTHORIZED=true` và `TMDB_ENABLE_LIVE_REQUESTS=true`), cổng kiểm tra thông tin xác thực của `TMDBClient` phát hiện biến môi trường `TMDB_API_READ_ACCESS_TOKEN` chưa được cấu hình trên máy chạy. Hệ thống đã dừng an toàn ngay tại cổng bảo vệ với mã trạng thái `tmdb_not_configured`, **không phát sinh bất kỳ yêu cầu mạng nào (`0/74` HTTP attempts)** và ghi nhận đầy đủ trạng thái của toàn bộ 40 phim trong báo cáo (`37` phim `NOT_ATTEMPTED` do thiếu token, `3` phim `NOT_ATTEMPTED_MISSING_TMDB_ID` do thiếu `tmdbId` trong `links.csv`).

### 10.3 Hướng dẫn chạy lại khi bổ sung Token
Khi chủ dự án cấu hình biến môi trường `TMDB_API_READ_ACCESS_TOKEN`, chỉ cần chạy lại đúng lệnh đã được phê duyệt:
```powershell
cd d:\TLTN\movie-recommendation-system\backend
$env:PHASE8D_LIVE_AUTHORIZED="true"
$env:TMDB_ENABLE_LIVE_REQUESTS="true"
$env:TMDB_API_READ_ACCESS_TOKEN="<your-tmdb-v3-read-access-token>"
.\.venv\Scripts\python.exe -m app.recommendation_evaluation.cli --phase8d --phase8d-live
```
Hệ thống sẽ tự động thực thi đúng 37 phim có `tmdbId` (tối đa 74 lượt gọi HTTP bao gồm cả retry ở tốc độ ≤ 4 RPS) và cập nhật toàn bộ báo cáo chất lượng cùng báo cáo TEC.
