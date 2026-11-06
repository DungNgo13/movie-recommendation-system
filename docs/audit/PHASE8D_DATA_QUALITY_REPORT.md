# Phase 8D — Data Quality Report (Báo cáo chất lượng dữ liệu)

**Date**: 2026-11-06  
**Phase**: Phase 8D — Controlled Live TMDB Pilot  
**Status**: NOT_RUN — Awaiting live pilot authorization and execution

---

## 1. Mục đích / Purpose

Tài liệu này trình bày các chỉ số chất lượng dữ liệu cho pilot TMDB Phase 8D.
Tất cả chỉ số hiện ở trạng thái NOT_RUN vì pilot trực tiếp chưa được ủy quyền.

This document presents data quality metrics for the Phase 8D TMDB pilot. All
metrics are currently NOT_RUN as the live pilot has not been authorized.

---

## 2. Quality Metrics / Chỉ số chất lượng

### 2.1 Title Match Rate

| Metric | Value |
|--------|-------|
| **Status** | **NOT_RUN** |
| Definition | Percentage of movies where TMDB title matches MovieLens title (after normalization) |
| Expected range | 90–98% (year suffixes, punctuation, and transliteration may differ) |
| Measurement method | Normalized string comparison with Levenshtein tolerance |

### 2.2 Year Match Rate

| Metric | Value |
|--------|-------|
| **Status** | **NOT_RUN** |
| Definition | Percentage of movies where TMDB release year matches MovieLens year |
| Expected range | 95–99% (±1 year tolerance for December/January releases) |
| Measurement method | Exact match with ±1 year tolerance |

### 2.3 Field Completeness

| Metric | Value |
|--------|-------|
| **Status** | **NOT_RUN** |
| Definition | Percentage of enrichment fields populated with non-empty values |
| Fields measured | title, overview, genres, runtime, vote_average, poster_path, backdrop_path |
| Expected range | 80–95% (depending on movie obscurity) |

### 2.4 Overview Coverage

| Metric | Value |
|--------|-------|
| **Status** | **NOT_RUN** |
| Definition | Percentage of movies with non-empty English overview from TMDB |
| Expected range | 85–95% |
| Measurement method | `len(overview.strip()) > 0` |

### 2.5 Keywords Coverage

| Metric | Value |
|--------|-------|
| **Status** | **NOT_RUN** |
| Definition | Percentage of movies with ≥1 TMDB keyword |
| Expected range | 60–80% (keywords are community-contributed and sparse for older/obscure films) |
| Measurement method | `len(keywords) > 0` |

### 2.6 Cast/Director Coverage

| Metric | Value |
|--------|-------|
| **Status** | **NOT_RUN** |
| Definition | Percentage of movies with ≥1 cast member and ≥1 director from TMDB credits |
| Expected range | 90–98% (credits are well-maintained for most films) |
| Measurement method | `len(cast) > 0 and len(directors) > 0` |

### 2.7 Vietnamese Localization Coverage

| Metric | Value |
|--------|-------|
| **Status** | **NOT_RUN** |
| Definition | Percentage of movies with non-empty Vietnamese title or overview from TMDB `vi-VN` locale |
| Expected range | 30–60% (Vietnamese translations are community-contributed and incomplete) |
| Measurement method | `len(vi_title.strip()) > 0 or len(vi_overview.strip()) > 0` |

### 2.8 Identity Conflict Rate

| Metric | Value |
|--------|-------|
| **Status** | **NOT_RUN** |
| Definition | Percentage of movies where TMDB metadata conflicts with MovieLens data (title mismatch > threshold AND year mismatch > 1) |
| Expected range | 1–5% (primarily remakes, re-releases, or mismatched TMDB IDs) |
| Severity levels | LOW (title only), MEDIUM (year only), HIGH (both title and year) |

### 2.9 API Error Rate

| Metric | Value |
|--------|-------|
| **Status** | **NOT_RUN** |
| Definition | Percentage of API requests that returned non-2xx status codes |
| Expected range | 1–5% (primarily 404 for movies without TMDB IDs) |
| Breakdown | 404 (not found), 429 (rate limited), 500+ (server error) |

### 2.10 Latency Percentiles

| Metric | Value |
|--------|-------|
| **Status** | **NOT_RUN** |
| Definition | Response time distribution for TMDB API requests |
| Percentiles measured | p50, p90, p95, p99, max |
| Expected range | p50 ~200ms, p95 ~500ms, p99 ~1000ms |

---

## 3. Quality Gates / Ngưỡng chất lượng

The following quality gates must be met for the pilot to be considered successful:

| Gate | Threshold | Status |
|------|-----------|--------|
| Title match rate | ≥ 85% | NOT_RUN |
| Year match rate | ≥ 90% | NOT_RUN |
| Field completeness | ≥ 75% | NOT_RUN |
| Overview coverage | ≥ 80% | NOT_RUN |
| Cast/Director coverage | ≥ 85% | NOT_RUN |
| API error rate | ≤ 10% | NOT_RUN |
| Identity conflict rate | ≤ 10% | NOT_RUN |

---

## 4. Population Note / Ghi chú

> **These metrics will be populated after live pilot authorization and execution.**
>
> To populate this report:
> 1. Obtain project owner authorization
> 2. Execute the live pilot (see `PHASE8D_LIVE_EXECUTION_PLAN.md`)
> 3. Review the generated `quality_report.md` at `backend/reports/phase8d_pilot/`
> 4. Update this document with actual metrics
>
> Until then, all metrics remain NOT_RUN and no data quality claims are made.

---

## 5. Methodology Notes / Phương pháp luận

### 5.1 Title Normalization

Before comparing MovieLens and TMDB titles:
1. Remove year suffix: `"Toy Story (1995)"` → `"Toy Story"`
2. Remove articles: `"The Godfather"` → `"Godfather"`
3. Lowercase and strip whitespace
4. Remove punctuation
5. Compare with Levenshtein ratio ≥ 0.85

### 5.2 Temporal Considerations

- MovieLens dataset covers interactions from 1996–2018
- TMDB metadata is current (2026)
- Fields like `vote_average` and `vote_count` may differ significantly
- Structural fields (title, year, director, cast) should be stable

### 5.3 Per-Stratum Analysis

Quality metrics will be broken down by pilot strata:
- Popular vs. longtail
- By decade
- With/without tags
- With/without TMDB IDs
- English vs. non-English
