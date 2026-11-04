# MovSug Phase 8A — Architecture, Gap Analysis, and Compliance Audit

## 1. Executive Summary

Phase 8A establishes a safe, auditable, human-in-the-loop **Movie Metadata Enrichment Foundation** for MovSug using the official **The Movie Database (TMDB) v3 API** as the primary structured metadata provider.

The pipeline follows a strict eight-stage lifecycle:

```
Existing MovSug Movie
  → TMDB Identity Matching (Exact ID / External ID / Normalized Title + Year + Director)
  → Structured Metadata Retrieval (en-US primary + optional vi-VN display localization)
  → Field-Level Validation & Normalization (Untrusted External Input Sanitization)
  → Staging & Provenance Persistence (No Direct Overwrites)
  → Admin Review & Field-Level Approval / Rejection
  → Transactional PostgreSQL Application (Optimistic Concurrency & Idempotency)
  → Recommendation TF-IDF Cache Synchronization & MovSug TEC Measurement
```

---

## 2. Repository Audit Findings

### 2.1 Existing Database Schema & Field Ownership (`backend/app/models/movie.py`)

| Column | Type | Current Purpose / Ownership | Missing-Data Pattern in Local Catalog (`test.db`, 17 movies) |
|---|---|---|---|
| `id` | `UUID` | Primary key | Present on all rows (100%) |
| `title` | `String(255)` | Primary English/canonical title (×2 TF-IDF weight) | Present on 100%, but 12/17 contain bilingual concatenations or trailing years (e.g., `"The Shawshank Redemption 1994 - Nhà tù Shawshank 1994"`) |
| `overview` | `Text` | English plot summary (×1 TF-IDF weight) | Present on 17/17 (100%), though several contain mixed-language text |
| `release_date` | `Date` | Release date (used for year filter & cold-start sorting) | 17/17 use `YYYY-01-01` synthetic Jan 1 dates from year-only entry |
| `genres` | `JSON` (`list[str]`) | Canonical genre labels (×1 TF-IDF weight) | Missing (`NULL`) on 3/17 movies (17.6%); inconsistent casing (`"Science Fiction"`, `"Science fiction"`, `"sci-fi"`, `"Romantic"`) |
| `cast` | `JSON` (`list[str]`) | Top-billed actor names (×1 TF-IDF weight, prefixed `actor`) | Missing (`NULL`) on 12/17 movies (70.6%) |
| `keywords` | `JSON` (`list[str]`) | Thematic English tags (×2 TF-IDF weight) | Missing (`NULL`) on 12/17 movies (70.6%); mixed Vietnamese/English tags on 5/17 |
| `director` | `String(100)` | Director name(s) (×1 TF-IDF weight, prefixed `director`) | Present on 17/17 (100%) |
| `poster_path` | `String(255)` | Poster path or HTTPS URL | Missing on 1/17 (5.9%) |
| `backdrop_path` | `String(255)` | Backdrop path or HTTPS URL | Missing on 1/17 (5.9%) |
| `title_vi` | `String(255)` | Display-only Vietnamese title (excluded from TF-IDF) | Missing (`NULL`) on 17/17 movies (100%) |
| `overview_vi` | `Text` | Display-only Vietnamese overview (excluded from TF-IDF) | Missing (`NULL`) on 17/17 movies (100%) |
| `keyword_labels_vi` | `JSON` (`dict[str,str]`) | Display-only Vietnamese keyword translations | Missing (`NULL`) on 17/17 movies (100%) |
| `source_name` / `source_url` / `license_type` / `attribution` / `media_rights_status` | Various | Provenance and rights metadata | `source_name` is `NULL` on 17/17 rows in `test.db` |
| `video_source_path` / `source_storage` / `source_object_key` / `hls_playlist_path` / `processing_status` | Various | Protected video streaming & R2 upload fields | Must **never** be modified by metadata enrichment |

### 2.2 Existing Importers & Utilities (`backend/scripts/importers/`)

- `import_movielens.py`: Bulk CSV importer for MovieLens `movies.csv` and `tags.csv` (`source_name="MovieLens"`, `media_rights_status="non_commercial_only"`).
- `import_wikidata.py`: Imports Wikidata SPARQL JSON exports (`keywords=["wikidata:Q..."]`, `source_name="Wikidata"`, `license_type="CC0 1.0"`).
- `import_loc_public_domain.py`: Imports Library of Congress public domain seed JSON (`public_domain_movies.json`).
- `import_wikimedia_commons.py` & `import_stock_assets.py`: Per-asset importers into `movie_assets`.
- **Gap**: No TMDB client, identity matcher, staging workflow, or enrichment service exists.

### 2.3 Existing Recommendation Cache Lifecycle (`backend/app/services/recommendation/vectorizer.py`)

- `vectorizer.py` maintains an in-memory `_cache` dictionary containing `vectorizer`, `matrix`, `movie_ids`, `movie_count`, and `filter_flag`.
- `_is_cache_valid(db)` checks whether `_cache["vectorizer"]` is initialized, `_cache["filter_flag"]` matches `RECOMMEND_ONLY_UPLOADED_MOVIES`, and `_candidate_query(db).count() == _cache["movie_count"]`.
- **Gap**: In-place metadata updates do not change `_candidate_query(db).count()`. Therefore, explicit `invalidate_cache()` invocation is mandatory whenever approved metadata is applied. Furthermore, `_cache` lacked generation/invalidation/refresh counters needed to verify and audit cache synchronization in MovSug TEC.

### 2.4 Existing Admin Movie Management (`frontend/src/pages/AdminMoviesPage.tsx`, `MovieForm.tsx`)

- `AdminMoviesPage.tsx` loads full `MovieDetailSchema` records and renders `MovieTable` and `MovieForm`.
- `MovieForm.tsx` supports editing English AI metadata (`title`, `overview`, `release_date`, `director`, `genres`, `cast`, `keywords`), Vietnamese display metadata (`title_vi`, `overview_vi`, `keyword_labels_vi`), poster/backdrop URLs, video encoding, and source/license fields.
- **Gap**: Admins currently have to copy-paste metadata manually. There is no UI to search/match TMDB candidates, inspect match evidence/conflicts, review proposed vs. existing fields side by side, or approve/reject individual fields.

---

## 3. Phase 8A Target Architecture

### 3.1 New Database Columns on `movies` and Staging Models

1. **Additive columns on `movies`**:
   - `tmdb_id` (`Integer`, nullable, indexed, unique when present): Verified TMDB movie identifier.
   - `imdb_id` (`String(20)`, nullable, indexed): Verified IMDb identifier (`tt...`).
   - `original_title` (`String(255)`, nullable): Original release title from provider.
   - `original_language` (`String(16)`, nullable): ISO 639-1 language code (e.g., `"en"`, `"ko"`, `"ja"`).
   - `metadata_version` (`Integer`, non-null, server default `1`): Optimistic concurrency version incremented on every metadata application.

2. **Staging, Provenance, and Audit Entities (`backend/app/models/metadata_enrichment.py`)**:
   - `MetadataEnrichmentJob` (`metadata_enrichment_jobs`):
     - Tracks each enrichment attempt for a `movie_id` (`provider="tmdb"`, `status`: `pending` / `staged` / `awaiting_review` / `approved` / `partially_approved` / `rejected` / `applied` / `failed`, `source_language`, `selected_candidate_id`, `initiated_by_email`, `reviewed_by_email`, `reviewed_at`, `applied_at`, `failure_reason`, `processing_duration_ms`, `retry_count`, `http_429_count`, `created_at`, `updated_at`).
     - Partial/logical active-job guard prevents duplicate concurrent pending jobs for the same `(movie_id, provider)`.
   - `MetadataCandidate` (`metadata_candidates`):
     - Stores candidate matches returned for a job (`job_id`, `movie_id`, `provider`, `provider_movie_id`, `title`, `original_title`, `release_date`, ` release_year`, `original_language`, `director`, `match_score`, `match_status` (`verified_id` / `high_confidence_review_required` / `ambiguous` / `conflict` / `rejected`), `is_verified_id_match`, `match_evidence` JSON, `conflicts` JSON, `review_reason`, `proposed_fields` JSON, `existing_snapshot` JSON, `field_diffs` JSON, `retrieved_at`).
   - `MetadataFieldProvenance` (`metadata_field_provenances`):
     - Tracks field-level provenance (`movie_id`, `job_id`, `candidate_id`, `field_name`, `provider`, `provider_movie_id`, `source_language`, `previous_value` JSON, `applied_value` JSON, `approved_by_email`, `retrieved_at`, `applied_at`).
   - `MetadataReviewEvent` (`metadata_review_events`):
     - Immutable audit trail of admin actions (`job_id`, `movie_id`, `candidate_id`, `admin_email`, `action`: `candidate_selected` / `approved` / `rejected` / `applied` / `rollback`, `approved_fields` JSON, `rejected_fields` JSON, `notes`, `created_at`).

### 3.2 Deterministic, Explainable Identity Matching (`backend/app/services/metadata_matcher.py`)

- **Title Normalization**:
  - Extracts MovSug bilingual title patterns (`"English Title YYYY - Vietnamese Title YYYY"` → primary normalized title `"english title"`, secondary localized title `"vietnamese title"`, extracted title year `YYYY`).
  - Strips parenthetical years `(2026)`, punctuation, diacritics (NFD normalization), and collapses whitespace while preserving sequel numerals (`2`, `ii`, `part ii`).
- **Scoring & Evidence Breakdown (0.0 – 100.0)**:
  - **Tier 1 — Verified External ID Match (`score = 100.0`, `match_status = "verified_id"`)**:
    - Exact match on existing `movie.tmdb_id` or `movie.imdb_id` / Wikidata QID via `/find/{external_id}`.
    - Still staged for admin inspection by default unless explicit verified-ID auto-stage is requested; if title or year conflicts with existing MovSug record, flags conflict for mandatory manual review.
  - **Tier 2 — Exact Normalized Title + Exact Year + Director Agreement (`score = 92.0`)**:
    - Exact normalized title (or original/alternative title) + exact release year + matching director.
  - **Tier 3 — Exact Normalized Title + Exact Year (`score = 82.0`)**:
    - Strong candidate, requires manual admin review (`reason_for_review="fuzzy_or_title_match_requires_manual_review"`).
  - **Tier 4 — Ambiguous / Remake / Adjacent Year / Missing Year (`score = 40.0 – 75.0`)**:
    - Multiple plausible candidates (e.g., remakes with identical titles across different years, sequel numbering differences, or ±1 year release window differences) are explicitly flagged `match_status = "ambiguous"` with detailed `conflicts` and `reason_for_review`.
  - **Rule**: No fuzzy or title-based match is ever treated as a verified identity or auto-applied.

---

## 4. Security, Licensing, and TMDB Compliance Notes

### 4.1 TMDB API Terms of Use & Attribution Requirements

1. **Attribution Requirement**:
   - Any page displaying TMDB-sourced metadata or images must display attribution to TMDB and the statutory disclaimer:
     *"This product uses the TMDB API but is not endorsed or certified by TMDB."*
   - When TMDB metadata is applied to a movie that lacks an existing public-domain/CC source attribution, MovSug sets:
     - `source_name = "TMDB"` (or preserves verified video source while recording per-field provenance in `metadata_field_provenances` and `attribution`)
     - `source_url = "https://www.themoviedb.org/movie/{tmdb_id}"`
     - `attribution = "Metadata provided by The Movie Database (TMDB). This product uses the TMDB API but is not endorsed or certified by TMDB."`
     - `SourceAttribution.tsx` and `SiteFooter.tsx` display the TMDB attribution notice.
2. **Storage & Caching**:
   - Raw TMDB API payloads are **not** stored in full. Only normalized, schema-validated candidate fields and provenance records needed for admin review and thesis auditing are persisted.
3. **Displaying Overviews & Language Separation**:
   - English overviews (`en-US`) are stored in `Movie.overview` (used by TF-IDF).
   - Vietnamese overviews (`vi-VN`) are stored strictly in `Movie.overview_vi` (display-only, never mixed into `Movie.overview` or `Movie.keywords`).
4. **Images (Posters & Backdrops)**:
   - TMDB poster/backdrop URLs (`https://image.tmdb.org/t/p/...`) are referenced only when explicitly approved by an administrator, with `media_rights_status = "attribution_required"` and `MovieAsset` provenance tracking.
5. **Streaming Rights vs. Metadata Access**:
   - TMDB provides structured bibliographic metadata only. Metadata enrichment **never** grants video streaming rights, never downloads video content from TMDB, and never alters `video_source_path`, `source_storage`, `source_object_key`, `upload_sessions`, or `hls_playlist_path`.
6. **Research Isolation & Temporal Leakage**:
   - Frozen offline evaluation datasets and reports from Phases 4, 5, 5.5, and 6 (`backend/reports/experiments/...`) are strictly untouched.
   - Externally retrieved TMDB metadata reflects contemporary provider state and may contain post-release keywords or credits; therefore, any offline evaluation using TMDB-enriched metadata must be isolated as a separate experimental condition (`phase8a_enriched_catalog`) and never conflated with algorithmic changes or historical MovieLens interaction splits.

