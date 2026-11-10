# MovSug Phase 8D — Controlled Live TMDB Pilot Execution & Evidence Report

**Date**: 2026-11-10  
**Phase**: Phase 8D — Controlled Live TMDB Pilot Execution and Evidence Collection  
**Approved Scope**: 40 manifest movies · Maximum 74 total HTTP attempts (including retries) · Maximum 4.0 RPS · `api.themoviedb.org` (HTTPS) only  
**Execution Status**: Executed Live (`74 / 74` HTTP attempts used, `3.00 RPS` max observed) → **`FAILED` due to Network/ISP TLS Handshake Reset (`WinError 10054`) on `api.themoviedb.org`**

---

## 1. Execution Scope and Authorization Evidence

### 1.1 Approved Scope vs. Enforced Implementation

| Parameter | Approved Limit | Enforced Value | Enforcement Mechanism |
| :--- | :--- | :--- | :--- |
| **Pilot Manifest Size** | 40 unique movies (`seed=8042`) | 40 unique movies (`seed=8042`) | Verified by SHA-256 manifest checksum (`d23fc802aefe509088127ede5d03009bc22354165d1b1adbc8f4906567d8800c`) |
| **Movies with TMDB ID (`links.csv`)** | 37 movies | 37 movies (2 planned requests/movie: `en-US` + `vi-VN`) | Direct `GET /movie/{tmdb_id}` lookup |
| **Movies without TMDB ID (`links.csv`)** | 3 movies (`2851`, `32600`, `791`) | 3 movies (`0` HTTP requests) | Marked `NOT_ATTEMPTED_MISSING_TMDB_ID` (`requires_manual_review=true`) |
| **Maximum Total HTTP Attempts** | **74 (including retries)** | **74 (`PHASE8D_APPROVED_MAX_REQUESTS = 74`)** | Enforced inside `TMDBClient._request_json()` immediately BEFORE every `self._client.get()` attempt and before any retry sleep |
| **Maximum Request Rate** | **4.0 requests/second** | **4.0 RPS (`PHASE8D_MAX_RPS = 4.0`, max observed `3.0 RPS`)** | Enforced by `TMDBClient._enforce_rate_limit()` before every outbound HTTP attempt, including retries |
| **Target Host Allowlist** | `api.themoviedb.org` only | `{"api.themoviedb.org"}` over `https://` | Enforced by `TMDBClient._validate_base_url()` and `_validate_endpoint()` |
| **Production Database Writes** | Zero writes allowed | Zero writes (`0` ORM/DB imports in Phase 8D) | Verified by `TestProductionIsolation` and preflight check #6 |
| **Concurrent Execution Protection** | Single active runner | Exclusive `O_CREAT \| O_EXCL` lockfile (`checkpoint/pilot.lock`) | Enforced by `_acquire_pilot_lock()` / `_release_pilot_lock()` |
| **Checkpoint Cumulative Persistence** | Preserve request count on resume | `cumulative_requests: 74` saved in `checkpoint.json` | Enforced via `on_attempt_callback` and `initial_requests_total` in `TMDBClient` |

### 1.2 Correction of the Request-Budget Mismatch (94 / 120 → 74)

During preflight inspection, three budget discrepancies were identified and fixed before live execution:

1. **Manifest & Default Cap Mismatch**: `generate_pilot_manifest()` previously added a 20-request retry buffer (`74 + 20 = 94`), and `PHASE8D_DEFAULT_REQUEST_BUDGET` defaulted to `120`. Both were corrected to the exact approved hard cap of **74 total HTTP attempts, including retries** (`estimated_api_requests: 74`, `estimated_retry_budget: 0`, `total_request_budget: 74`, `retries_included_in_budget: true`).
2. **Pre-Attempt Budget Counting Across Retries**: Previously, `run_live_pilot()` incremented `summary.total_requests` only once per outer method call, ignoring internal retries inside `TMDBClient._request_json()`. `TMDBConfig.max_total_requests = 74` is now enforced inside `TMDBClient._request_json()` immediately before every HTTP attempt (`200 OK`, `429`, `5xx`, timeouts, network errors, and `vi-VN` localization calls). When an HTTP attempt fails at `requests_total == 74`, `can_retry` evaluates to `False` so no 75th retry attempt is ever slept for or sent.
3. **Resumable Checkpoint Cumulative Accounting**: `checkpoint.json` persists `cumulative_requests`, `stats_snapshot`, and `records_by_id` via `on_attempt_callback` on every HTTP attempt. Resuming an interrupted run initializes `TMDBClient(initial_requests_total=prior_requests)`, guaranteeing that interrupted + resumed runs can never exceed 74 total HTTP attempts.

### 1.3 Preflight Verification Summary (`phase8d_preflight_report.json`)

All 8 mandatory preflight checks passed (`preflight_passed: true` at `2026-11-10T02:47:58.059293+00:00`):

- **Check 1 (`1_manifest_40_unique_and_checksum`)**: `passed: true` — 40 unique movies, SHA-256 `d23fc802aefe509088127ede5d03009bc22354165d1b1adbc8f4906567d8800c`.
- **Check 2 (`2_max_http_attempt_budget_74`)**: `passed: true` — `config_request_budget: 74`, `manifest_total_request_budget: 74`, `approved_hard_cap: 74`, `retries_included: true`.
- **Check 3 (`3_global_rate_limiter_4_rps`)**: `passed: true` — `configured_rate_limit_rps: 4.0`, `max_allowed_rps: 4.0`, `covers_retries: true`.
- **Check 4 (`4_all_http_attempts_counted_pre_request`)**: `passed: true` — `TMDBClient._request_json` enforces `max_total_requests` and increments `stats.requests_total` before `client.get()` on every attempt/retry.
- **Check 5 (`5_checkpoint_preserves_cumulative_usage`)**: `passed: true` — `prior_completed_movies: 0`, `prior_cumulative_requests: 0`.
- **Check 6 (`6_zero_production_db_modifications`)**: `passed: true` — `allowlisted_hosts: ["api.themoviedb.org"]`, zero ORM/DB imports.
- **Check 7 (`7_research_output_isolation`)**: `passed: true` — isolated to `backend/reports/phase8d_pilot`.
- **Check 8 (`8_authorization_gates_operational`)**: `passed: true` — `--phase8d-live` (`true`), `PHASE8D_LIVE_AUTHORIZED=true`, `TMDB_ENABLE_LIVE_REQUESTS=true`, `api_token_present: true`, `ready_for_network: true`.

---

## 2. Exact Request Counts and Rate-Limit Measurements

From `backend/reports/phase8d_pilot/phase8d_request_statistics.json`:

| Metric | Measured Value | Approved Limit / Target |
| :--- | :--- | :--- |
| **Approved Request Budget** | `74` | `74` (including retries) |
| **Total Outbound HTTP Attempts Sent** | **`74`** | `≤ 74` (exact hard-cap stop) |
| **Requests Succeeded (`200 OK`)** | `0` | — |
| **Movie-Level Request Failures** | `19` | 18 movies × 4 attempts + 1 movie × 2 attempts = 74 attempts |
| **Retries Executed** | `55` | 18 movies × 3 retries + 1 movie × 1 retry = 55 retries |
| **Remaining Request Budget** | `0` | Budget exhausted at attempt #74; attempt #75 blocked |
| **Budget Exhausted Events** | `1` | Triggered on movie `3825` after 2nd attempt reached 74/74 |
| **HTTP 429 Rate-Limit Responses** | `0` | — |
| **HTTP 5xx Server Errors** | `0` | — |
| **Configured Rate Limit** | `4.0 RPS` | `≤ 4.0 RPS` |
| **Max Observed Rate** | **`3.0 RPS`** | `≤ 4.0 RPS` |
| **Latency `p50` / `p95` (Time-to-Failure)** | `278.82 ms` / `381.84 ms` | Per-attempt TCP/TLS reset latency |
| **Total Execution Duration** | `85.899 s` | Includes exponential backoff (`1s + 2s + 4s`) across 55 retries |

---

## 3. Provider Reliability & Network Root-Cause Analysis

Every outbound HTTPS attempt to `https://api.themoviedb.org/3/movie/{id}` failed at the TLS handshake layer with:
```text
[WinError 10054] An existing connection was forcibly closed by the remote host
```

| Target Host | DNS Resolution | TCP Connect (`:443`) | TLS 1.3 Handshake | Outcome |
| :--- | :---: | :---: | :---: | :--- |
| `api.themoviedb.org` (`3.169.173.x` CloudFront) | ✅ Resolved | ✅ Connected | ❌ TCP `RST` (`WinError 10054`) | **Blocked by local network/ISP/firewall** |
| `google.com` | ✅ Resolved | ✅ Connected | ✅ TLSv1.3 | Reachable |
| `httpbin.org` | ✅ Resolved | ✅ Connected | ✅ TLSv1.3 | Reachable |

- **Empirical Proof of the 74-Attempt Hard Cap**:
  - Movies 1–18 with TMDB IDs each consumed 1 initial attempt + 3 retries = `18 × 4 = 72` HTTP attempts.
  - Movie 19 (`movie_id=3825`, `tmdb_id=6282`, *Coyote Ugly (2000)*) consumed 1 initial attempt + 1 retry = `2` HTTP attempts (`72 + 2 = 74` total attempts).
  - Before sleeping or sending a 2nd retry for Movie 19 (which would have been attempt #75), `TMDBClient._request_json()` detected `requests_total (74) >= max_total_requests (74)`, incremented `budget_exhausted_count = 1`, and terminated the retry loop immediately.
  - The remaining 18 movies with TMDB IDs were preserved in the report as `not_attempted_budget_exhausted` (`NOT_ATTEMPTED`, `request_count=0`).

---

## 4. Identity Accuracy Assessment

All 40 manifest movies are accounted for in `phase8d_identity_matching_report.json`:

| Category | Movie Count | Verification Status | Notes |
| :--- | :---: | :--- | :--- |
| **Queried Movies (Network TLS Reset)** | 19 | `FAILED` (`api_error`) | 18 movies with 4 attempts each + 1 movie (`3825`) with 2 attempts = 74 HTTP attempts |
| **Unattempted Movies (Budget Exhausted at 74/74)** | 18 | `NOT_ATTEMPTED` (`not_attempted_budget_exhausted`) | Preserved with `request_count=0` after attempt #74 reached the approved cap |
| **Movies without TMDB ID in `links.csv`** | 3 | `NOT_ATTEMPTED_MISSING_TMDB_ID` | MovieLens IDs `2851` (*Saturn 3 (1980)*), `32600` (*Eros (2004)*), and `791` (*The Last Klezmer (1994)*). Flagged `requires_manual_review=true` (`REVIEW_REQUIRED`). |
| **Total Manifest Movies** | **40** | **`FAILED`** | 100% of manifest movies preserved in all reports |

---

## 5. Metadata Completeness Before and After

From `phase8d_field_completeness.json` (across all 40 pilot movies):

| Metadata Field | Before Enrichment (MovieLens Baseline) | After Phase 8D Live Execution (`FAILED` — TLS Reset) |
| :--- | :---: | :---: |
| `title` (EN) | 40 / 40 (100.0%) | 40 / 40 (100.0%) |
| `genres` | 40 / 40 (100.0%) | 40 / 40 (100.0%) |
| `overview_en` | 0 / 40 (0.0%) | 0 / 40 (0.0%) |
| `keywords` | 0 / 40 (0.0%) | 0 / 40 (0.0%) |
| `cast` | 0 / 40 (0.0%) | 0 / 40 (0.0%) |
| `director` | 0 / 40 (0.0%) | 0 / 40 (0.0%) |
| `title_vi` | 0 / 40 (0.0%) | 0 / 40 (0.0%) |
| `overview_vi` | 0 / 40 (0.0%) | 0 / 40 (0.0%) |

---

## 6. Failures, Conflicts, Missing-ID Movies, and Unattempted Movies

Recorded in `phase8d_failure_report.json` and `phase8d_live_retrieval.log`:

1. **API Network Errors (`api_errors_count: 19`)**:
   - MovieLens IDs `1029`, `106782`, `110826`, `112788`, `135`, `1493`, `151317`, `152077`, `1891`, `2080`, `2282`, `2342`, `2478`, `2730`, `284`, `3`, `3152`, `3385` (4 HTTP attempts each = 72 attempts) and `3825` (2 HTTP attempts = 2 attempts).
   - All failed with `[WinError 10054] An existing connection was forcibly closed by the remote host` on `api.themoviedb.org`.
2. **Missing-TMDB-ID Movies (`missing_tmdb_id_count: 3`)**:
   - `movieId=2851` (*Saturn 3 (1980)*, `imdb_id=tt0081454`, `tmdb_id=0`, `NOT_ATTEMPTED_MISSING_TMDB_ID`)
   - `movieId=32600` (*Eros (2004)*, `imdb_id=tt0377059`, `tmdb_id=0`, `NOT_ATTEMPTED_MISSING_TMDB_ID`)
   - `movieId=791` (*Last Klezmer: Leopold Kozlowski, His Life and Music, The (1994)*, `imdb_id=tt0113610`, `tmdb_id=0`, `NOT_ATTEMPTED_MISSING_TMDB_ID`)
3. **Unattempted Movies Due to 74-Attempt Cap (`18` movies)**:
   - MovieLens IDs `414`, `4998`, `57147`, `5791`, `58351`, `59220`, `6123`, `6289`, `67534`, `6807`, `6944`, `70301`, `745`, `78142`, `79091`, `79536`, `8712`, `95497`.
   - Marked `status="not_attempted_budget_exhausted"`, `verification_status="NOT_ATTEMPTED"`, `request_count=0`.
   - Per owner instructions, **no second run or budget increase was attempted**.

---

## 7. Snapshot Provenance and Checksums

Recorded in `backend/reports/phase8d_pilot/snapshots/phase8d_snapshot_manifest.json`:

| Artifact | Path | SHA-256 Checksum |
| :--- | :--- | :--- |
| **40-Movie Selection List** | `phase8d_pilot_manifest.json` (`movies` array) | `d23fc802aefe509088127ede5d03009bc22354165d1b1adbc8f4906567d8800c` |
| **Pilot Manifest JSON** | `backend/reports/phase8d_pilot/phase8d_pilot_manifest.json` | `d9e7ab0b536dab976c2dba52bc9e44cc1b3860f2f6de06dc4535850da5f828e0` |
| **Pilot Snapshot JSON** | `backend/reports/phase8d_pilot/snapshots/phase8d_pilot_snapshot.json` | `cf68dfe76e5ee6660f729432ff564f4f79f1000b55b05d20792e4ab3eb803efa` |
| **MovieLens Dataset** | `backend/data/ml-latest-small` | `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86` |
| **Evaluation Split** | Temporal 80/10/10 split | `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67` |

- `production_db_modified`: `false`
- `historical_snapshots_overwritten`: `false`

---

## 8. Recommendation Impact Readiness Assessment

1. **Budget & Safety Controls (`LIVE_VERIFIED_UNDER_FAULT`)**:
   - The live execution empirically proved that `TMDBClient` and `run_live_pilot` enforce the exact **74-attempt hard cap (including retries)**, respect the **4.0 RPS** ceiling (max observed `3.0 RPS`), persist `cumulative_requests: 74` in `checkpoint.json` so re-running cannot make a 75th request, and preserve all 40 manifest movies in the output reports.
2. **Live Metadata Readiness (`FAILED` — Network TLS Block)**:
   - Because the local network/ISP resets TLS connections to `api.themoviedb.org` (`WinError 10054`), `0` movies were enriched (`verification_mode: "FAILED"`).
   - Full-catalog enrichment (9,734 movies) is **not justified** until outbound HTTPS/TLS connectivity to `api.themoviedb.org` is restored.

---

## 9. TEC Evidence Integration

Generated under `test_center/reports/tec-20261110-025343-f84b5ed/report/`:

- **JSON Report**: `test_center/reports/tec-20261110-025343-f84b5ed/report/summary.json`
- **Markdown Report**: `test_center/reports/tec-20261110-025343-f84b5ed/report/report.md`
- **Vietnamese Summary**: `test_center/reports/tec-20261110-025343-f84b5ed/report/bao_cao_tom_tat.md`
- **Self-Contained HTML Report**: `test_center/reports/tec-20261110-025343-f84b5ed/report/report.html`

---

## 10. Tóm Tắt Kết Quả Thực Thi Pilot Phase 8D (Bản Tiếng Việt Phục Vụ Khóa Luận)

### 10.1 Hiệu chỉnh phạm vi ủy quyền và kiểm chứng thực nghiệm giới hạn 74 HTTP Attempts
- Đã khắc phục triệt để sự sai lệch giữa ngân sách được phê duyệt (**74 lượt thử HTTP bao gồm cả retry**) và cấu hình cũ (94 trong manifest / 120 mặc định trong CLI).
- Thực thi trực tuyến (live pilot) đã chứng minh cơ chế giới hạn hoạt động chính xác tuyệt đối: hệ thống gửi đúng **74/74 lượt thử HTTP** (18 phim × 4 lượt thử + 1 phim × 2 lượt thử = 74 lượt thử, bao gồm 19 lượt gọi gốc và 55 lượt retry) với tốc độ tối đa quan sát được là **3,0 RPS** (≤ giới hạn 4,0 RPS). Ngay khi đạt mốc 74/74 ở phim thứ 19 (`movieId=3825`), `TMDBClient` đã chặn ngay lượt retry thứ 75 và đánh dấu 18 phim còn lại là `NOT_ATTEMPTED` (`not_attempted_budget_exhausted`), đồng thời giữ nguyên 3 phim thiếu `tmdbId` ở trạng thái `NOT_ATTEMPTED_MISSING_TMDB_ID`.

### 10.2 Nguyên nhân lỗi mạng (`WinError 10054`) và tính toàn vẹn dữ liệu
- Cả 74 lượt kết nối HTTPS tới `api.themoviedb.org` đều bị đóng cưỡng bức ở tầng bắt tay TLS (`[WinError 10054] An existing connection was forcibly closed by the remote host`), trong khi kết nối DNS/TCP tới IP CloudFront của TMDB và kết nối TLS 1.3 tới `google.com`/`httpbin.org` vẫn hoạt động bình thường. Điều này cho thấy tường lửa hoặc nhà mạng (ISP) tại môi trường chạy đang chặn kết nối TLS tới tên miền `api.themoviedb.org`.
- Tệp `checkpoint.json` đã ghi nhận `cumulative_requests = 74`, đảm bảo mọi lệnh chạy lại tiếp theo không thể vượt quá ngân sách 74 lượt thử nếu chưa được chủ dự án cho phép xóa checkpoint sau khi khắc phục mạng. Cơ sở dữ liệu PostgreSQL/SQLite hoàn toàn không bị thay đổi (`0` lượt ghi).
