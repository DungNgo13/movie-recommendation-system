# Phase 8D — Full Catalog Enrichment Estimate (Ước tính làm giàu toàn bộ danh mục)

**Date**: 2026-11-06  
**Phase**: Phase 8D — Controlled Live TMDB Pilot  
**Scope**: Planning document for post-pilot full catalog enrichment

---

## 1. Mục đích / Purpose

Tài liệu này ước tính chi phí, thời gian, và dung lượng lưu trữ cho việc làm
giàu metadata toàn bộ danh mục MovieLens ml-latest-small từ TMDB API, và đề
xuất chiến lược triển khai theo giai đoạn.

This document estimates the cost, time, and storage for enriching the full
MovieLens ml-latest-small catalog from the TMDB API, and proposes a phased
rollout strategy.

---

## 2. Catalog Summary / Tổng quan danh mục

| Metric | Value |
|--------|-------|
| Total movies in catalog | 9,742 |
| Movies with TMDB IDs | 9,734 |
| Movies without TMDB IDs | 8 |
| Enrichable movies | 9,734 |

---

## 3. Request Volume / Khối lượng yêu cầu

### 3.1 Per-Movie Requests

| Endpoint | Purpose | Requests per Movie |
|----------|---------|-------------------|
| `GET /3/movie/{id}?append_to_response=credits,keywords&language=en-US` | English metadata + credits + keywords | 1 |
| `GET /3/movie/{id}?language=vi-VN` | Vietnamese localization | 1 |
| **Total per movie** | | **2** |

### 3.2 Total Request Estimate

| Component | Calculation | Count |
|-----------|------------|-------|
| Base requests | 9,734 movies × 2 requests | 19,468 |
| Estimated retries (5% rate) | 19,468 × 0.05 | ~973 |
| **Total estimated** | | **~20,441** |
| **Rounded estimate** | | **~19,500–20,500** |

---

## 4. Time Estimate / Ước tính thời gian

### 4.1 At Configured Rate (4 RPS)

| Metric | Value |
|--------|-------|
| Rate limit | 4 requests per second |
| Base requests | 19,468 |
| Base time | 19,468 ÷ 4 = 4,867 seconds |
| Base time (minutes) | ~81.1 minutes |
| Retry overhead (~5%) | ~4 minutes |
| Initialization overhead | ~1 minute |
| **Total estimated** | **~86 minutes (~1.4 hours)** |

### 4.2 With Checkpointing Overhead

| Scenario | Additional Time |
|----------|----------------|
| No interruptions | +0 minutes |
| 1 interruption + resume | +2 minutes (re-scan + skip completed) |
| 5 interruptions + resumes | +10 minutes |

### 4.3 Network Latency Sensitivity

| Network Quality | Estimated p50 Latency | Total Time |
|----------------|----------------------|------------|
| Good (< 200ms) | 150ms | ~81 minutes |
| Average (200-500ms) | 300ms | ~85 minutes |
| Poor (500ms+) | 700ms | ~95 minutes |

---

## 5. Storage Estimate / Ước tính dung lượng

### 5.1 Per-Movie Storage

| Component | Estimated Size |
|-----------|---------------|
| English metadata JSON | ~3 KB |
| Vietnamese metadata JSON | ~1 KB |
| Credits (cast + crew) | ~1 KB (top 10 cast, directors only) |
| Keywords | ~0.5 KB |
| Execution log entry | ~0.2 KB |
| **Total per movie** | **~5 KB** |

### 5.2 Full Catalog Storage

| Component | Calculation | Size |
|-----------|------------|------|
| Metadata files | 9,734 × 5 KB | ~47.4 MB |
| Quality report | 1 file | ~50 KB |
| Execution log | 1 file | ~500 KB |
| Manifest | 1 file | ~200 KB |
| Checksums | 1 file | ~200 KB |
| **Total estimated** | | **~48 MB** |

### 5.3 Disk Space Requirements

| Requirement | Value |
|-------------|-------|
| Minimum free space | 100 MB (2× buffer) |
| Recommended free space | 500 MB |
| Current reports/ size | Varies |

---

## 6. Checkpoint Strategy / Chiến lược lưu điểm

### 6.1 Design

- Save metadata to disk **after each movie** is retrieved
- Write checkpoint state every 50 movies to `checkpoint.json`
- On resume, scan existing metadata files to determine progress

### 6.2 Checkpoint File

```json
{
  "phase": "8D_full",
  "total_movies": 9734,
  "completed": 4521,
  "last_movie_id": 58559,
  "last_checkpoint_at": "2026-11-07T10:30:00Z",
  "errors": 12,
  "retries": 45
}
```

### 6.3 Recovery Scenarios

| Scenario | Recovery Action |
|----------|----------------|
| Clean interruption (Ctrl+C) | Resume from last checkpoint |
| Network failure | Resume after connectivity restored |
| Process crash | Resume; incomplete movie file detected and re-fetched |
| Disk full | Free space, then resume |
| API token expired | Update token in environment, then resume |

---

## 7. Recommended Phased Rollout / Triển khai theo giai đoạn

### 7.1 Phase Schedule

| Phase | Movies | Requests | Time | Purpose |
|-------|--------|----------|------|---------|
| **8D Pilot** | 40 | ~80–120 | ~1 min | Validate pipeline, quality metrics |
| **Confirmatory** | 500 | ~1,050 | ~4.5 min | Confirm quality at moderate scale |
| **Expansion** | 2,000 | ~4,200 | ~18 min | Coverage for meaningful semantic experiments |
| **Full Catalog** | 9,734 | ~20,500 | ~86 min | Complete enrichment |

### 7.2 Phase Gates

Each phase requires review before proceeding:

| Gate | Criteria |
|------|----------|
| Pilot → Confirmatory | Title match ≥ 85%, API error ≤ 10%, manual spot-check OK |
| Confirmatory → Expansion | Quality metrics stable, no new error patterns |
| Expansion → Full | Quality metrics consistent across strata |

### 7.3 Cumulative Progress

```
Phase 8D Pilot:     40/9,734 = 0.4% coverage
+ Confirmatory:    540/9,734 = 5.5% coverage
+ Expansion:     2,540/9,734 = 26.1% coverage
+ Full Catalog:  9,734/9,734 = 100% coverage
```

---

## 8. Cost Analysis / Phân tích chi phí

### 8.1 TMDB API Cost

| Factor | Value |
|--------|-------|
| API pricing | **Free** for non-commercial use |
| Registration | Free |
| Rate limits | ~40 RPS (we use 4 RPS) |
| Monthly quotas | None for registered users |
| Commercial licensing | Not applicable (academic use) |

### 8.2 Compute Cost

| Resource | Cost |
|----------|------|
| Local machine compute | ~86 minutes CPU time |
| Network bandwidth | ~48 MB download |
| Disk storage | ~48 MB |
| Cloud costs | None (runs locally) |

### 8.3 Total Cost

**\$0.00** — TMDB API is free for non-commercial/educational use, and all
computation runs on the local development machine.

---

## 9. Prerequisites / Điều kiện tiên quyết

Before proceeding to full catalog enrichment:

| # | Prerequisite | Status |
|---|-------------|--------|
| 1 | Successful 40-movie pilot review | ⏳ AWAITING |
| 2 | Quality metrics meet all gates | ⏳ AWAITING |
| 3 | Manual spot-check of pilot results | ⏳ AWAITING |
| 4 | Project owner authorization | ⏳ AWAITING |
| 5 | Checkpoint/resume tested with pilot | ⏳ AWAITING |
| 6 | Disk space verified (≥100 MB free) | ✅ VERIFIED |
| 7 | TMDB API token valid | ⏳ AWAITING |

---

## 10. Risk Assessment / Đánh giá rủi ro

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| TMDB API downtime during enrichment | Low | Low | Checkpoint/resume; retry next day |
| Rate limiting (429 errors) | Medium | Low | 4 RPS limit, Retry-After handling |
| Network interruption | Low | Low | Checkpoint/resume |
| TMDB ID mismatches at scale | Medium | Medium | Quality gate review between phases |
| Storage exhaustion | Very Low | Low | ~48 MB is negligible |
| API terms change | Very Low | Medium | Monitor TMDB announcements |
