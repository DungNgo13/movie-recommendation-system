# Phase 8D.6 — Recovery Pilot Run 002 Results

| Field | Value |
|---|---|
| **Run ID** | `phase8d_run_002` |
| **Phase** | 8D.6 — Recovery Live TMDB Pilot |
| **Status** | `RECOVERY_PILOT_COMPLETE` |
| **Verdict** | ✅ **36/37 movies LIVE_VERIFIED, 0 API errors, 74/100 budget used** |
| **Date** | 2026-11-20T11:27:58+07:00 |
| **Network** | Router 4G WAN (owner confirmed) |
| **Previous run** | `run_001`: 74/74 exhausted, 0 successes (broadband ISP blocked) |

---

## Tóm tắt

Recovery pilot run_002 đã hoàn thành thành công trên kết nối 4G WAN. Kết quả:

- **36/37 phim** có TMDB ID đã được xác minh thành công (`LIVE_VERIFIED`)
- **1 phim** có xung đột danh tính (`ambiguous_match`) cần xem xét thủ công
- **3 phim** không có TMDB ID trong links.csv (đúng như dự kiến)
- **0 lỗi API**, **0 lần thử lại**, **74/100 ngân sách** đã sử dụng
- Độ trễ: p50 = 535ms, p95 = 693ms
- Tổng thời gian: 42.3 giây
- Dữ liệu run_001 không bị thay đổi (checkpoint 74/74 nguyên vẹn)

> [!IMPORTANT]
> So sánh với run_001: 0/37 thành công (broadband) → 36/37 thành công (4G WAN).
> Mạng 4G WAN đã giải quyết hoàn toàn vấn đề kết nối.

---

## 1. Execution Summary

| Metric | Value |
|---|---|
| Mode | `LIVE` |
| Verification mode | `PARTIALLY_VERIFIED` |
| Pilot size | 40 movies |
| Movies queried (with TMDB ID) | 37 |
| Successful (`LIVE_VERIFIED`) | **36** |
| Partially verified | 0 |
| Identity conflicts | 1 (ambiguous match) |
| API errors | **0** |
| Skipped (no TMDB ID) | 3 |
| Not attempted | 3 |
| Total HTTP attempts | **74 / 100** |
| Retries | **0** |
| HTTP 429 (rate limited) | 0 |
| HTTP 5xx (server error) | 0 |
| Budget exhausted events | 0 |
| Budget remaining | 26 (unused retry margin) |
| Max observed RPS | 3.0 / 4.0 configured |
| Latency p50 | 534.97 ms |
| Latency p95 | 692.93 ms |
| Execution duration | 42.292 seconds |
| Blocker | NONE |
| Circuit breaker | Not tripped |

---

## 2. Field Completeness (After Enrichment)

| Field | Populated | of 40 | % of Pilot | % of Queried (37) |
|---|---|---|---|---|
| has_overview (EN) | 37 | 40 | 92.5% | 100% |
| has_keywords | 35 | 40 | 87.5% | 94.6% |
| has_cast | 37 | 40 | 92.5% | 100% |
| has_director | 37 | 40 | 92.5% | 100% |
| has_vi_title (VN) | 37 | 40 | 92.5% | 100% |
| has_vi_overview (VN) | 12 | 40 | 30.0% | 32.4% |

> [!NOTE]
> `has_vi_overview` at 32.4% is expected — many movies lack Vietnamese overviews
> in TMDB's database. This reflects TMDB's localization coverage, not an API issue.
> `has_keywords` at 94.6% indicates 2 movies have no keywords in TMDB.

---

## 3. Identity Verification

| Category | Count |
|---|---|
| Exact ID verified matches | 36 |
| Live verified complete | 36 |
| Movies with TMDB ID in links | 37 |
| Movies without TMDB ID | 3 |
| Ambiguous matches | 1 |
| Identity conflicts | 1 |
| Manual review required | 4 |

### Records Requiring Manual Review

| MovieLens ID | TMDB ID | Title | Status | Verification |
|---|---|---|---|---|
| 284 | 109560 | New York Cop (Nyû Yôku no koppu) (1993) | `ambiguous_match` | `REVIEW_REQUIRED` |
| 2851 | 0 | Saturn 3 (1980) | `not_attempted_missing_tmdb_id` | `NOT_ATTEMPTED_MISSING_TMDB_ID` |
| 32600 | 0 | Eros (2004) | `not_attempted_missing_tmdb_id` | `NOT_ATTEMPTED_MISSING_TMDB_ID` |
| 791 | 0 | Last Klezmer: Leopold Kozlowski... (1994) | `not_attempted_missing_tmdb_id` | `NOT_ATTEMPTED_MISSING_TMDB_ID` |

**ML#284 (New York Cop):** The only identity conflict among queried movies. The
MovieLens title "New York Cop (Nyû Yôku no koppu) (1993)" mapped to TMDB ID 109560,
but the match was classified as ambiguous. This record was **not** automatically
approved — it requires manual identity review as specified.

---

## 4. Run Comparison: run_001 vs. run_002

| Metric | run_001 (Broadband) | run_002 (4G WAN) |
|---|---|---|
| Successful | **0** | **36** |
| API errors | 19 | **0** |
| Retries | 55 | **0** |
| Total requests | 74/74 | 74/100 |
| Budget exhausted | Yes | No |
| Circuit breaker | Tripped | Not tripped |
| All errors | WinError 10054 | None |
| Duration | ~20s (all failures) | 42.3s (all successes) |
| Network | Broadband ISP | Router 4G WAN |

---

## 5. Data Isolation Verification

| Check | Status |
|---|---|
| run_001 checkpoint: 74/74 | ✅ **Unchanged** (last modified: 2026-11-10) |
| run_002 checkpoint: 74/100 | ✅ New, independent |
| Manifest checksums match | ✅ `d23fc802aefe5090...` |
| run_001 files modified today | ✅ **No** — all untouched |
| Production database writes | ✅ **Zero** |

---

## 6. Budget Analysis (Actual)

| Budget Component | Planned | Actual |
|---|---|---|
| Base requests (37 × 2) | 74 | 74 |
| Retries consumed | 0–26 margin | **0** |
| Total used | ≤100 | **74** |
| Remaining | ≥0 | **26** |

The Option B budget of 100 provided a 26-attempt retry margin. In practice,
**zero retries were needed** — every request succeeded on the first attempt.
This confirms the 4G WAN network path is reliable for TMDB API access.

---

## 7. Output Files

All files located in `backend/reports/phase8d_pilot_run_002/`:

| File | Size |
|---|---|
| `phase8d_data_quality.json` | 56,312 bytes |
| `phase8d_pilot_manifest.json` | 14,263 bytes |
| `phase8d_pilot_manifest.csv` | 3,222 bytes |
| `phase8d_preflight_report.json` | 2,057 bytes |
| `phase8d_full_catalog_estimate.json` | 1,528 bytes |
| `phase8d_request_statistics.json` | 641 bytes |
| `phase8d_field_completeness.json` | 1,534 bytes |
| `phase8d_identity_matching_report.json` | 2,560 bytes |
| `phase8d_failure_report.json` | 4,721 bytes |
| `phase8d_live_retrieval.log` | 5,941 bytes |
| `phase8d_per_movie_quality.csv` | 6,266 bytes |
| `checkpoint/checkpoint.json` | 57,642 bytes |
| `snapshots/phase8d_pilot_snapshot.json` | 149,035 bytes |
| `snapshots/phase8d_snapshot_manifest.json` | 701 bytes |

---

## 8. Verdict and Status Classification

| Movie Status | Count | Classification |
|---|---|---|
| `LIVE_VERIFIED` | 36 | ✅ Fully enriched and identity-verified |
| `REVIEW_REQUIRED` (ambiguous) | 1 | ⚠️ Needs manual identity review |
| `NOT_ATTEMPTED_MISSING_TMDB_ID` | 3 | ℹ️ Expected — no TMDB ID in links.csv |

**Overall verification mode: `PARTIALLY_VERIFIED`** — because 1 movie requires
manual identity review (ML#284, New York Cop). Without this single ambiguous match,
the pilot would be `FULLY_VERIFIED` for all queried movies.

---

## 9. Network Resolution

The recovery pilot conclusively demonstrates:

1. **The broadband ISP connection** causes `WinError 10054` (connection reset)
   on HTTPS requests to `api.themoviedb.org` — observed in run_001 (74/74 failures)
2. **The router 4G WAN connection** provides reliable access — observed in run_002
   (74/74 successes, 0 retries, 0 errors)
3. **The TMDB API itself** is fully operational and responsive (p50 = 535ms)
4. **The application code** (TMDBClient, circuit breaker, budget enforcement,
   checkpointing) works correctly when network connectivity is available

> [!NOTE]
> This does not constitute a conclusive diagnosis of the broadband ISP's specific
> blocking mechanism (SNI filtering, DPI, or other). It establishes that the
> broadband path is non-functional for TMDB API access while the 4G path works.
