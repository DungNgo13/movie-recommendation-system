# Phase 8D — TEC Integration Report (Báo cáo tích hợp TEC)

**Date**: 2026-11-06  
**Phase**: Phase 8D — Controlled Live TMDB Pilot  
**TEC**: Test & Evidence Center (MovSug)

---

## 1. Mục đích / Purpose

Tài liệu này mô tả cách Phase 8D tích hợp với hệ thống Test & Evidence Center
(TEC) của MovSug, bao gồm collector, phân loại trạng thái xác minh, và cách
tách biệt kết quả mock và live.

This document describes Phase 8D's integration with the MovSug Test & Evidence
Center (TEC), including the collector implementation, verification status
taxonomy, and separation of mock vs. live results.

---

## 2. Phase8DCollector Implementation / Triển khai Phase8DCollector

### 2.1 Module

- **File**: `test_center/collectors/phase8d_collector.py`
- **Class**: `Phase8DCollector`
- **Base class**: Inherits from TEC collector interface

### 2.2 Responsibilities

| Responsibility | Description |
|----------------|-------------|
| Collect pilot manifest | Read and validate the 40-movie manifest |
| Collect quality metrics | Parse quality report for data quality indicators |
| Collect execution log | Parse timestamped execution log for errors/retries |
| Determine verification status | Classify each metric as NOT_RUN, MOCK_VERIFIED, or LIVE_VERIFIED |
| Generate evidence entries | Produce structured evidence for TEC report |

### 2.3 Collected Evidence

```python
class Phase8DEvidence:
    pilot_size: int                    # Expected: 40
    movies_with_tmdb_id: int           # Expected: ~36-37
    movies_without_tmdb_id: int        # Expected: 3-4
    total_api_requests: int            # Expected: ≤120
    api_error_count: int               # From execution log
    title_match_rate: float | None     # None if NOT_RUN
    year_match_rate: float | None      # None if NOT_RUN
    field_completeness: float | None   # None if NOT_RUN
    overview_coverage: float | None    # None if NOT_RUN
    keywords_coverage: float | None    # None if NOT_RUN
    cast_director_coverage: float | None  # None if NOT_RUN
    vi_localization_coverage: float | None  # None if NOT_RUN
    identity_conflict_rate: float | None   # None if NOT_RUN
    execution_mode: str                # "dry_run" or "live"
    verification_status: str           # See taxonomy in §3
```

---

## 3. Verification Status Taxonomy / Phân loại trạng thái xác minh

### 3.1 Status Definitions

| Status | Definition | When Used |
|--------|-----------|-----------|
| `NOT_RUN` | Metric has not been computed; no data available | Before any execution |
| `MOCK_VERIFIED` | Metric computed using mock/simulated TMDB data | After dry-run execution |
| `LIVE_VERIFIED` | Metric computed using real TMDB API responses | After live execution with valid data |
| `PARTIALLY_VERIFIED` | Some movies have live data, others have mock data | During incremental execution (not expected in Phase 8D) |
| `FAILED` | Metric computation attempted but produced errors | API failures, parsing errors |
| `INSUFFICIENT_EVIDENCE` | Metric computed but sample size too small for conclusions | Edge case with very few successful retrievals |

### 3.2 Status Transitions

```
NOT_RUN ──(dry-run)──→ MOCK_VERIFIED
NOT_RUN ──(live)────→ LIVE_VERIFIED
NOT_RUN ──(error)───→ FAILED
MOCK_VERIFIED ──(live)──→ LIVE_VERIFIED  (never reversed)
LIVE_VERIFIED ──(never)──→ MOCK_VERIFIED (prohibited)
```

### 3.3 Current Phase 8D Status

All metrics are currently `NOT_RUN` pending live pilot authorization.

---

## 4. Mock and Live Result Separation / Tách biệt kết quả mock và live

### 4.1 Principle

Mock and live results are **never merged**. They are stored in separate data
structures and reported independently.

### 4.2 Implementation

| Aspect | Mock Results | Live Results |
|--------|-------------|-------------|
| Output directory | `reports/phase8d_pilot/dry_run/` | `reports/phase8d_pilot/live/` |
| Manifest tag | `"execution_mode": "dry_run"` | `"execution_mode": "live"` |
| TEC evidence tag | `verification_status: MOCK_VERIFIED` | `verification_status: LIVE_VERIFIED` |
| Report section | "Mock Dry-Run Results" | "Live Pilot Results" |
| Quality metrics | Computed from mock data | Computed from real API responses |

### 4.3 Why Separate?

1. **Scientific integrity**: Mock data produces artificially high quality metrics
   (mock responses are perfectly formatted). Merging would inflate real metrics.
2. **Auditability**: Reviewers must be able to verify which results come from
   real API responses vs. simulated data.
3. **Reproducibility**: Mock results are deterministic; live results depend on
   TMDB's current database state and may vary over time.
4. **Transparency**: The thesis must clearly state which evaluations used real
   data and which used simulated data.

---

## 5. CLI Integration / Tích hợp dòng lệnh

### 5.1 Running TEC Phase 8D Collection

```powershell
cd d:\TLTN\movie-recommendation-system
backend\.venv\Scripts\python.exe -m test_center.cli --phase8d
```

### 5.2 CLI Options

| Flag | Description |
|------|-------------|
| `--phase8d` | Run Phase 8D TEC collection |
| `--format markdown` | Output as markdown (default) |
| `--format json` | Output as JSON |
| `--output <path>` | Custom output path |

### 5.3 Combined TEC Run

```powershell
# Run all TEC collectors (including Phase 8D)
backend\.venv\Scripts\python.exe -m test_center.cli
```

---

## 6. Report Rendering / Xuất báo cáo

### 6.1 Markdown Report

The TEC Phase 8D section in the markdown report includes:

```markdown
## Phase 8D: Controlled Live TMDB Pilot

| Metric                      | Value    | Status       |
|-----------------------------|----------|-------------|
| Pilot size                  | 40       | CONFIGURED  |
| Movies with TMDB ID         | —        | NOT_RUN     |
| Title match rate            | —        | NOT_RUN     |
| Year match rate             | —        | NOT_RUN     |
| Field completeness          | —        | NOT_RUN     |
| Overview coverage           | —        | NOT_RUN     |
| Keywords coverage           | —        | NOT_RUN     |
| Cast/Director coverage      | —        | NOT_RUN     |
| Vietnamese localization     | —        | NOT_RUN     |
| Identity conflict rate      | —        | NOT_RUN     |
| API error rate              | —        | NOT_RUN     |
| Latency p50/p95/p99         | —        | NOT_RUN     |
```

### 6.2 JSON Report

```json
{
  "phase": "8D",
  "collector": "Phase8DCollector",
  "execution_mode": "not_run",
  "verification_status": "NOT_RUN",
  "metrics": {
    "title_match_rate": null,
    "year_match_rate": null,
    "field_completeness": null,
    "overview_coverage": null,
    "keywords_coverage": null,
    "cast_director_coverage": null,
    "vi_localization_coverage": null,
    "identity_conflict_rate": null,
    "api_error_rate": null,
    "latency_p50": null,
    "latency_p95": null,
    "latency_p99": null
  }
}
```

---

## 7. Test Coverage / Phủ kiểm thử

### 7.1 Existing Tests

| Test Suite | Tests | Status |
|-----------|-------|--------|
| Backend tests (pre-Phase 8D) | 465 | ✅ ALL PASSING |
| TEC tests (pre-Phase 8D) | 40+ | ✅ ALL PASSING |

### 7.2 Phase 8D TEC Tests

| Test File | Tests | Description |
|-----------|-------|-------------|
| `test_center/tests/test_phase8d_collector.py` | Phase 8D collector unit tests | Manifest parsing, quality metric collection, status classification, mock/live separation |

### 7.3 Test Execution

```powershell
# Run Phase 8D TEC collector tests
cd d:\TLTN\movie-recommendation-system
backend\.venv\Scripts\python.exe -m pytest test_center/tests/test_phase8d_collector.py -v

# Run all TEC tests
backend\.venv\Scripts\python.exe -m pytest test_center/tests/ -v

# Run all backend tests (regression)
cd backend
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

---

## 8. Evidence Chain / Chuỗi bằng chứng

The TEC Phase 8D evidence chain connects:

```
Phase 8D Pilot Execution
  → Execution Log (timestamps, status codes, latencies)
  → Per-Movie Metadata Files (sanitized JSON)
  → Quality Report (aggregated metrics)
  → Phase8DCollector (reads all above)
  → TEC Evidence Entries (structured, classified)
  → TEC Report (markdown + JSON)
  → Audit Documentation (this file + PHASE8D_DATA_QUALITY_REPORT.md)
```

Each link in the chain is:
- **Timestamped**: ISO 8601 timestamps on all records
- **Checksummed**: SHA-256 hashes for integrity verification
- **Classified**: Verification status from the taxonomy in §3
- **Separated**: Mock and live evidence never mixed
