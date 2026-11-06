# Phase 8D — Live Execution Plan (Kế hoạch thực thi trực tiếp)

**Date**: 2026-11-06  
**Phase**: Phase 8D — Controlled Live TMDB Pilot  
**Status**: AWAITING AUTHORIZATION

---

## 1. Mục đích / Purpose

Tài liệu này mô tả chính xác lệnh thực thi, khối lượng yêu cầu API, và các
điều khoản kiểm soát cho pilot TMDB trực tiếp Phase 8D trên 40 phim.

This document specifies the exact execution command, API request volume, and
control terms for the Phase 8D live TMDB pilot on 40 movies.

---

## 2. Exact Execution Command / Lệnh thực thi chính xác

### 2.1 Dry-Run (Default — No API Calls)

```powershell
cd d:\TLTN\movie-recommendation-system\backend
.\.venv\Scripts\python.exe -m app.recommendation_evaluation.cli --phase8d
```

### 2.2 Live Execution (Requires Authorization)

```powershell
cd d:\TLTN\movie-recommendation-system\backend

# Set required environment variables
$env:PHASE8D_LIVE_AUTHORIZED = "true"
$env:TMDB_ENABLE_LIVE_REQUESTS = "true"
$env:TMDB_API_READ_ACCESS_TOKEN = "<your-tmdb-api-read-access-token>"

# Execute live pilot
.\.venv\Scripts\python.exe -m app.recommendation_evaluation.cli --phase8d --phase8d-live
```

### 2.3 Authorization Gate (Dual-Gate)

Live execution requires **ALL** of the following:

| Requirement | Type | Value |
|-------------|------|-------|
| `--phase8d-live` | CLI flag | Present on command line |
| `PHASE8D_LIVE_AUTHORIZED` | Environment variable | `true` |
| `TMDB_ENABLE_LIVE_REQUESTS` | Environment variable | `true` |
| `TMDB_API_READ_ACCESS_TOKEN` | Environment variable | Valid TMDB v3 read access token |

If **any** of these is missing, the system falls back to dry-run mode with mock
data. No partial authorization is possible.

---

## 3. Request Volume / Khối lượng yêu cầu

### 3.1 Per-Movie Requests

Each movie requires **2 TMDB API requests**:

| # | Endpoint | Purpose | Language |
|---|----------|---------|----------|
| 1 | `GET /3/movie/{tmdb_id}?append_to_response=credits,keywords&language=en-US` | English metadata, credits, keywords | EN |
| 2 | `GET /3/movie/{tmdb_id}?language=vi-VN` | Vietnamese localized title and overview | VI |

### 3.2 Volume Calculation

| Component | Count |
|-----------|-------|
| Pilot movies with TMDB IDs | ~36–37 (40 total minus 3–4 without TMDB IDs) |
| Requests per movie | 2 (EN + VI) |
| Base requests | ~72–74 |
| Movies without TMDB IDs (no API call) | 3–4 (logged as skipped) |
| Estimated retries (5% retry rate) | ~4–5 |
| **Maximum total requests** | **≤120** |

### 3.3 Operations That Contact TMDB

| Operation | Contacts TMDB? | Request Count |
|-----------|---------------|---------------|
| Pilot selection (stratified sampling) | ❌ No | 0 |
| Identity mapping (links.csv lookup) | ❌ No | 0 |
| Metadata retrieval (EN) | ✅ Yes | 1 per movie |
| Metadata retrieval (VI localization) | ✅ Yes | 1 per movie |
| Manifest generation | ❌ No | 0 |
| Quality report generation | ❌ No | 0 |
| TEC report generation | ❌ No | 0 |

---

## 4. Rate Limiting / Giới hạn tốc độ

| Parameter | Value |
|-----------|-------|
| Configured rate limit | 4 requests per second |
| TMDB official limit | ~40 RPS |
| Safety margin | 10× |
| HTTP 429 handling | Respect `Retry-After` header, exponential backoff |
| Maximum retries per request | 3 |
| Inter-request delay | 250ms minimum |

### 4.1 Estimated Execution Time

```
~80 requests ÷ 4 RPS = ~20 seconds base
+ retry overhead = ~30 seconds total
+ initialization = ~10 seconds
─────────────────────────────
Total estimated: ~40–60 seconds
```

---

## 5. Output Locations / Vị trí kết quả

All Phase 8D outputs are written to a single directory:

```
backend/reports/phase8d_pilot/
├── manifest.json              # 40-movie pilot manifest
├── metadata/                  # Per-movie metadata JSON files
│   ├── movie_{movieId}.json   # One file per movie
│   └── ...
├── quality_report.json        # Aggregated quality metrics
├── quality_report.md          # Human-readable quality report
├── execution_log.json         # Timestamped execution log
└── checksums.json             # SHA-256 of all output files
```

### 5.1 File Descriptions

| File | Purpose |
|------|---------|
| `manifest.json` | Pilot selection manifest with strata tags |
| `metadata/movie_{id}.json` | Raw TMDB metadata (sanitized) per movie |
| `quality_report.json` | Machine-readable quality metrics |
| `quality_report.md` | Human-readable quality metrics for review |
| `execution_log.json` | Request timestamps, status codes, latencies |
| `checksums.json` | Integrity verification for all outputs |

---

## 6. Checkpoint and Resume / Lưu điểm và tiếp tục

### 6.1 Checkpoint Strategy

- After each movie is successfully retrieved, its metadata is saved to
  `metadata/movie_{movieId}.json` immediately
- The execution log records which movies have been completed
- If interrupted, re-running the command will skip already-retrieved movies

### 6.2 Resume Behavior

```
On resume:
  1. Load manifest (40 movies)
  2. Scan metadata/ directory for existing files
  3. Skip movies with valid existing metadata files
  4. Continue from first missing movie
  5. Update execution log and quality report
```

### 6.3 Idempotency

Re-running the live command with the same manifest produces identical results
(same movies, same endpoints). Already-retrieved movies are not re-fetched
unless their metadata files are deleted.

---

## 7. Rollback Plan / Kế hoạch hoàn tác

### 7.1 Complete Rollback

To completely undo a live pilot execution:

```powershell
# Delete all Phase 8D pilot outputs
Remove-Item -Recurse -Force d:\TLTN\movie-recommendation-system\backend\reports\phase8d_pilot\
```

### 7.2 What Rollback Affects

| Component | Affected by Rollback? |
|-----------|----------------------|
| Phase 8D pilot outputs | ✅ Deleted |
| Production database | ❌ Not affected (Phase 8D never writes to DB) |
| MovieLens dataset | ❌ Not affected (read-only) |
| Phase 8A/8B/8C artifacts | ❌ Not affected (separate directories) |
| TEC reports | ❌ Not affected (separate TEC output directory) |
| Git repository | ❌ Not affected (reports/ is in .gitignore) |

### 7.3 Partial Rollback

To re-run specific movies, delete their individual metadata files:

```powershell
# Re-fetch a specific movie
Remove-Item d:\TLTN\movie-recommendation-system\backend\reports\phase8d_pilot\metadata\movie_862.json
# Then re-run the live command (checkpoint/resume will re-fetch only this movie)
```

---

## 8. Safety Checklist / Danh sách kiểm tra an toàn

Before executing the live pilot, verify:

- [ ] All 465 backend tests pass
- [ ] All 40+ TEC tests pass
- [ ] Dataset checksums verified
- [ ] TMDB API read access token is valid (test with a single manual request)
- [ ] `reports/phase8d_pilot/` directory does not contain stale data from previous runs
- [ ] Network connectivity to `api.themoviedb.org` confirmed
- [ ] Sufficient disk space (~1 MB for 40 movies)
- [ ] Project owner has explicitly authorized live execution

---

## 9. Post-Execution Review / Đánh giá sau thực thi

After live execution completes:

1. Review `quality_report.md` for data quality metrics
2. Spot-check 5–10 movies manually against TMDB web interface
3. Verify Vietnamese localization quality for non-English movies
4. Check execution log for any errors or retries
5. Generate TEC report: `python -m test_center.cli --phase8d`
6. Update `PHASE8D_DATA_QUALITY_REPORT.md` with actual metrics
7. Decision: proceed to full-catalog enrichment or iterate on issues
