# Phase 8D — Provider Compliance (Tuân thủ nhà cung cấp TMDB)

**Date**: 2026-11-06  
**Phase**: Phase 8D — Controlled Live TMDB Pilot  
**Provider**: The Movie Database (TMDB) — https://www.themoviedb.org  
**API Version**: v3

---

## 1. Mục đích / Purpose

Tài liệu này xác nhận rằng việc sử dụng TMDB API trong Phase 8D tuân thủ đầy
đủ Điều khoản Sử dụng API của TMDB, bao gồm quy định ghi nhận nguồn, giới hạn
tốc độ, và chính sách dữ liệu.

This document confirms that Phase 8D's use of the TMDB API fully complies with
TMDB's API Terms of Use, including attribution requirements, rate limiting, and
data policies.

---

## 2. TMDB API Terms of Use Summary / Tóm tắt điều khoản

The TMDB API Terms of Use (https://www.themoviedb.org/documentation/api/terms-of-use)
establish the following key requirements:

| Requirement | Summary |
|-------------|---------|
| **Registration** | API users must register for an API key |
| **Attribution** | Products must attribute TMDB as the data source |
| **Rate Limiting** | API users must not exceed reasonable request rates |
| **Non-Commercial** | Free API access is for non-commercial, educational, or personal use |
| **No Redistribution** | Raw API responses must not be redistributed publicly |
| **Data Freshness** | Cached data should be refreshed periodically |
| **Logo Usage** | TMDB logo must be displayed when showing TMDB data |

---

## 3. Attribution Requirements / Yêu cầu ghi nhận nguồn

### 3.1 Required Attribution Text

The following attribution statement is included in all outputs that display
TMDB-sourced data:

> **"This product uses the TMDB API but is not endorsed or certified by TMDB."**

### 3.2 TMDB Logo

- The TMDB logo must be displayed when presenting TMDB-sourced metadata
- Logo assets: https://www.themoviedb.org/about/logos-attribution
- Implementation: `SourceAttribution.tsx` component in frontend

### 3.3 Source Provenance

Every enriched metadata field records its provenance:

```json
{
  "source_name": "TMDB",
  "source_url": "https://www.themoviedb.org/movie/{tmdb_id}",
  "retrieved_at": "<ISO 8601 timestamp>",
  "api_version": "v3"
}
```

### 3.4 Implementation

| Component | Attribution Mechanism |
|-----------|---------------------|
| `metadata_application_service.py` | Records `source_name="TMDB"` in `metadata_field_provenances` |
| `movie_assets` table | Stores `MovieAsset` records with TMDB attribution |
| `SourceAttribution.tsx` | Displays TMDB logo and attribution text in UI |
| Research snapshots (JSON) | Include `source` and `retrieved_at` fields |
| Phase 8D reports | Include attribution statement in headers |

---

## 4. Rate Limiting Compliance / Tuân thủ giới hạn tốc độ

### 4.1 TMDB Rate Limits

TMDB allows approximately 40 requests per second for registered API users.

### 4.2 MovSug Rate Limiting

| Parameter | Value | TMDB Limit | Compliance |
|-----------|-------|------------|-----------|
| Configured rate | 4 RPS | ~40 RPS | ✅ 10× safety margin |
| HTTP 429 handling | Respect `Retry-After` | Required | ✅ Implemented |
| Max retries | 3 per request | N/A | ✅ Bounded |
| Backoff strategy | Exponential | N/A | ✅ Conservative |

### 4.3 Implementation

```python
# TMDBClient rate limiting (from tmdb_client.py)
MAX_REQUESTS_PER_SECOND = 4   # 10× safety margin vs TMDB's ~40 RPS
MAX_RETRIES = 3                # Bounded retries
RETRY_BACKOFF_FACTOR = 2.0     # Exponential backoff
```

The `TMDBClient` enforces rate limiting at the client level, independent of any
server-side limits. HTTP 429 responses are handled by reading the `Retry-After`
header and waiting the specified duration before retrying.

---

## 5. Academic/Educational Use Classification / Phân loại sử dụng học thuật

### 5.1 Use Case

| Factor | Classification |
|--------|---------------|
| Project type | University graduation thesis (luận văn tốt nghiệp) |
| Institution | Educational institution |
| Commercial intent | None — purely academic research |
| Revenue generation | None |
| Public API access | None — internal research only |
| Data subjects | Movies (not personal data) |

### 5.2 TMDB API Terms Alignment

TMDB's API Terms of Use explicitly permit non-commercial and educational use.
The MovSug project:

- Is a university graduation thesis with no commercial intent
- Does not generate revenue from TMDB data
- Does not expose TMDB data through a public-facing API
- Uses TMDB data only for academic research on recommendation algorithms
- Properly attributes TMDB as the data source

---

## 6. Data Retention Policy / Chính sách lưu giữ dữ liệu

### 6.1 Research Snapshots

| Policy | Details |
|--------|---------|
| Storage location | `backend/reports/phase8d_pilot/metadata/` |
| Format | JSON files (one per movie) |
| Retention period | Duration of thesis research + archival |
| Access control | Local development machine only |
| Version tracking | Git-tracked checksums (not raw data) |

### 6.2 What Is Stored

| Data Type | Stored? | Justification |
|-----------|---------|---------------|
| Movie titles (EN + VI) | ✅ Yes | Required for enrichment evaluation |
| Overviews (EN + VI) | ✅ Yes | Required for semantic embedding experiments |
| Credits (cast/director) | ✅ Yes | Required for content-based recommendation |
| Keywords | ✅ Yes | Required for TF-IDF enrichment |
| Vote statistics | ✅ Yes | Required for popularity stratification |
| Poster/backdrop paths | ✅ Yes (paths only) | No images downloaded |
| Raw HTTP responses | ❌ No | Only parsed/sanitized fields stored |
| API tokens | ❌ No | Environment variables only, redacted from logs |

### 6.3 Data Freshness

Research snapshots are point-in-time captures for reproducibility. They are
not intended to be kept up-to-date with TMDB's live database. Each snapshot
records its `retrieved_at` timestamp for temporal validity analysis.

---

## 7. No Redistribution / Không phân phối lại

### 7.1 Commitment

The MovSug project does **NOT**:

- Publish raw TMDB API responses in any public repository
- Expose TMDB data through any public-facing API or service
- Share TMDB data with third parties
- Include TMDB data in published thesis appendices (only aggregated statistics)

### 7.2 Git Exclusion

```gitignore
# Raw TMDB metadata is excluded from version control
backend/reports/phase8d_pilot/metadata/
```

Only aggregated quality metrics, checksums, and manifest structure (without raw
metadata) are version-controlled.

---

## 8. Programmatic Enforcement / Thực thi qua mã nguồn

The `TMDBClient` class enforces all compliance requirements programmatically:

| Requirement | Enforcement Mechanism |
|-------------|----------------------|
| SSRF protection | Host allowlist (`api.themoviedb.org`) |
| Rate limiting | Client-side 4 RPS limiter |
| 429 handling | `Retry-After` header parsing |
| Secret redaction | `SecretRedactionFilter` on all log handlers |
| Mock default | `TMDB_ENABLE_LIVE_REQUESTS=false` default |
| Attribution | Automatic `source_name="TMDB"` in all provenance records |
| Input sanitization | HTML/script stripping on all API responses |
| Bounded retries | Maximum 3 retries per request |

---

## 9. Compliance Checklist / Danh sách kiểm tra tuân thủ

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Valid API key registration | ✅ Required before live execution |
| 2 | Attribution text included | ✅ Implemented |
| 3 | TMDB logo displayed | ✅ Implemented in frontend |
| 4 | Rate limiting ≤ 40 RPS | ✅ 4 RPS (10× margin) |
| 5 | HTTP 429 respected | ✅ Retry-After handling |
| 6 | Non-commercial use | ✅ Academic thesis |
| 7 | No raw data redistribution | ✅ .gitignore exclusion |
| 8 | Source provenance recorded | ✅ Per-field tracking |
| 9 | Data sanitization | ✅ HTML/script stripping |
| 10 | Secret redaction in logs | ✅ SecretRedactionFilter |
