# Phase 8D — Pilot Selection Manifest (Bảng chọn mẫu pilot)

**Date**: 2026-11-06  
**Phase**: Phase 8D — Controlled Live TMDB Pilot  
**Selection Algorithm**: Deterministic Stratified Sampling  
**Random Seed**: 8042  
**Pilot Size**: 40 movies

---

## 1. Mục đích / Purpose

Tài liệu này mô tả thuật toán chọn mẫu 40 phim cho pilot Phase 8D, đảm bảo
đại diện đầy đủ các phân tầng quan trọng trong danh mục MovieLens ml-latest-small.

This document describes the 40-movie pilot selection algorithm, ensuring
representative coverage across critical strata of the MovieLens ml-latest-small
catalog.

---

## 2. Selection Algorithm / Thuật toán chọn mẫu

### 2.1 Algorithm Type

**Deterministic stratified sampling** with fixed seed for full reproducibility.

```python
import random
random.seed(8042)  # Fixed seed for deterministic selection
```

### 2.2 Algorithm Steps

1. Load full catalog (9,742 movies from `movies.csv`)
2. Load identity mapping (9,734 with TMDB IDs, 8 without)
3. Classify each movie into strata (see §3)
4. Allocate quota per stratum proportionally, with minimums for rare strata
5. Random sample within each stratum using `random.seed(8042)`
6. Verify no duplicates across strata (movies may qualify for multiple strata;
   assign to highest-priority stratum first)
7. Output manifest with movieId, title, year, tmdbId, strata tags

### 2.3 Priority Order for Multi-Strata Movies

When a movie qualifies for multiple strata, it is assigned to the first matching
stratum in this priority order:

1. Without-TMDB-ID (highest priority — must be included for error-path testing)
2. Non-English
3. Popularity (top 20% / bottom 40%)
4. Decade
5. Tags/No-tags

---

## 3. Strata Definitions / Định nghĩa phân tầng

### 3.1 Popularity Strata

| Stratum | Definition | Catalog Size (approx.) |
|---------|------------|----------------------|
| Popular (Top 20%) | Movies in top 20% by rating count | ~1,948 |
| Longtail (Bottom 40%) | Movies in bottom 40% by rating count | ~3,897 |
| Mid-range (Middle 40%) | Remaining movies | ~3,897 |

### 3.2 Decade Strata

| Stratum | Year Range | Catalog Size (approx.) |
|---------|-----------|----------------------|
| Pre-1980 | ≤ 1979 | ~800 |
| 1980s | 1980–1989 | ~700 |
| 1990s | 1990–1999 | ~1,800 |
| 2000s | 2000–2009 | ~2,800 |
| 2010s+ | 2010–present | ~3,600 |

### 3.3 Tag Strata

| Stratum | Definition |
|---------|------------|
| Has Tags | Movie has ≥1 user tag in `tags.csv` |
| No Tags | Movie has 0 user tags |

### 3.4 Special Strata

| Stratum | Definition | Count |
|---------|------------|-------|
| Non-English | Title contains non-ASCII characters or known non-English indicators | Variable |
| Without-TMDB-ID | movieIds with no TMDB ID in `links.csv` | 8 |

---

## 4. Expected Strata Allocation / Phân bổ dự kiến

| Stratum | Quota | Rationale |
|---------|-------|-----------|
| Without-TMDB-ID | 3–4 | Error-path testing (API lookup failure, fallback behavior) |
| Non-English | 3–4 | Vietnamese localization testing, Unicode handling |
| Popular (Top 20%) | 5–6 | High-confidence matches, rich TMDB metadata expected |
| Longtail (Bottom 40%) | 5–6 | Sparse metadata, possible TMDB mismatches |
| Pre-1980 | 3–4 | Temporal mismatch testing (old movies, possibly updated TMDB data) |
| 1980s | 3–4 | Mid-era coverage |
| 1990s | 4–5 | Core MovieLens era |
| 2000s | 4–5 | Modern era |
| 2010s+ | 4–5 | Recent releases, rich TMDB metadata |
| Has Tags | included above | Tag-based metadata comparison |
| No Tags | 2–3 | Movies where TMDB metadata is the only enrichment source |
| **Total** | **40** | |

> **Note**: Exact counts depend on stratum assignment priority and the
> deterministic random selection within each stratum. The algorithm guarantees
> exactly 40 unique movies.

---

## 5. Rationale for 40-Movie Size / Lý do chọn 40 phim

| Factor | Consideration |
|--------|--------------|
| **API budget** | 40 movies × 2 requests (EN + VI) = ~80 base requests + ~20 retries = ≤120 total |
| **Rate limiting** | At 4 RPS, 120 requests complete in ~30 seconds |
| **Review burden** | 40 movies can be manually reviewed in ~1 hour |
| **Statistical power** | Sufficient for per-stratum quality metrics, not for significance testing |
| **Error coverage** | Large enough to encounter edge cases (missing IDs, non-English, temporal mismatches) |
| **Risk mitigation** | Small enough that a complete rollback is trivial (`rm -rf reports/phase8d_pilot/`) |
| **Precedent** | Phase 8A used 16 movies for mock benchmark; 40 is a natural 2.5× expansion |

---

## 6. Reproducibility / Khả năng tái tạo

### 6.1 Exact Regeneration Command

```powershell
cd d:\TLTN\movie-recommendation-system\backend
.\.venv\Scripts\python.exe -m app.recommendation_evaluation.cli --phase8d
```

This runs in **dry-run mode** (no live API calls) and produces the pilot
manifest at `backend/reports/phase8d_pilot/manifest.json`.

### 6.2 Determinism Guarantee

The selection is fully deterministic given:

1. **Dataset**: MovieLens ml-latest-small with checksum `d830d1e5...aa86`
2. **Seed**: `8042`
3. **Algorithm**: Stratified sampling with priority-based stratum assignment

Any execution with the same dataset and seed produces the identical 40-movie
manifest.

### 6.3 Manifest Verification

After regeneration, the manifest can be compared byte-for-byte:

```powershell
# Generate SHA-256 of manifest
Get-FileHash -Algorithm SHA256 backend/reports/phase8d_pilot/manifest.json
```

---

## 7. Included Edge Cases / Các trường hợp biên

The pilot deliberately includes movies that exercise error and edge-case paths:

| Edge Case | How Tested | Expected Count |
|-----------|-----------|---------------|
| No TMDB ID | API lookup returns 404, system logs gracefully | 3–4 movies |
| Non-English title | Vietnamese localization endpoint tested | 3–4 movies |
| Very old movie (pre-1970) | Temporal mismatch between MovieLens and TMDB | 1–2 movies |
| Very popular movie | High match confidence, rich metadata | 3–4 movies |
| Obscure/longtail movie | Possible sparse TMDB metadata | 3–4 movies |
| No user tags | TMDB metadata is the only enrichment source | 2–3 movies |
| Sequel/remake | Title disambiguation testing | Incidental |

---

## 8. Output Format / Định dạng kết quả

The pilot manifest is saved as JSON:

```json
{
  "phase": "8D",
  "pilot_size": 40,
  "seed": 8042,
  "dataset_checksum": "d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86",
  "generated_at": "<ISO 8601 timestamp>",
  "movies": [
    {
      "movieId": 1,
      "title": "Toy Story (1995)",
      "year": 1995,
      "tmdbId": 862,
      "strata": ["popular", "1990s", "has_tags"]
    }
  ]
}
```
