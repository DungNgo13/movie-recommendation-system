# Phase 8C — Field-Level Coverage Report

## 1. Overview

This report documents the metadata field-level coverage measurement system
implemented in Phase 8C. The system measures which enriched metadata fields
are present across the movie catalog.

## 2. Evaluated Fields

| # | Field              | Source                    | Time-Invariant |
|---|-------------------|---------------------------|----------------|
| 1 | `title`           | MovieLens + TMDB          | ✅ Yes         |
| 2 | `original_title`  | TMDB                      | ✅ Yes         |
| 3 | `title_vi`        | TMDB (vi-VN localization) | ⚠️ Potentially |
| 4 | `genres`          | MovieLens + TMDB (merged) | ⚠️ Potentially |
| 5 | `overview`        | TMDB                      | ⚠️ Potentially |
| 6 | `overview_vi`     | TMDB (vi-VN localization) | ⚠️ Potentially |
| 7 | `keywords`        | MovieLens tags + TMDB     | ⚠️ Potentially |
| 8 | `cast`            | TMDB (credits)            | ✅ Yes         |
| 9 | `director`        | TMDB (credits)            | ✅ Yes         |

## 3. Coverage Measurement

For each snapshot, the system computes:
- **Count**: Number of movies with a non-empty value for each field
- **Total**: Total number of movies in the enrichment subset
- **Coverage %**: `count / total × 100`

## 4. Output Artifacts

- `phase8c_field_coverage.json` — Full coverage report with nested statistics
- `phase8c_field_coverage.csv` — Tabular export for spreadsheet analysis

## 5. Baseline Coverage (Original MovieLens)

On original MovieLens ml-latest-small metadata (9,742 movies):

| Field           | Coverage |
|-----------------|----------|
| title           | 100%     |
| original_title  | 0%       |
| title_vi        | 0%       |
| genres          | ~99%     |
| overview        | 0%       |
| overview_vi     | 0%       |
| keywords (tags) | ~15%     |
| cast            | 0%       |
| director        | 0%       |

## 6. After Enrichment (Mock Dry-Run)

With the Phase 8A mock TMDB catalog (16 movies, 13 approved):
- Only 11–13 movies receive full TMDB enrichment
- Remaining pilot movies receive simulated enrichment (TMDB ID only)
- Live TMDB API access required for full catalog enrichment

## 7. Evidence Status

Current status: **INSUFFICIENT EVIDENCE** for coverage sensitivity analysis.

The mock TMDB catalog contains only 16 test movies. Meaningful coverage
sensitivity analysis at 1%, 5%, 10%, 25%, 50%, 80%, 100% levels requires
live TMDB API access with explicit user authorization.
