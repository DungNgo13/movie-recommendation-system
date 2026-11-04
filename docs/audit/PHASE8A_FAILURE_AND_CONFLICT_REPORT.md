# MovSug — Phase 8A: Failure, Conflict, and Ambiguity Analysis Report

**Date**: 2026-11-04  
**Phase**: Phase 8A — Movie Metadata Enrichment Foundation  
**Evidence Classification**: `mocked_controlled_verification` (unit, API, rollback, and 16-movie controlled benchmark tests).

---

## 1. Overview of Failure & Conflict Handling

Movie metadata enrichment from external providers is vulnerable to five classes of failure if left automated or unvalidated:
1. **Identity Mismatches** (confusing remakes, sequels, documentaries, or identically titled films).
2. **Silent Data Corruption** (overwriting curated catalog fields or mixing Vietnamese text into English TF-IDF columns).
3. **Untrusted External Input** (HTML/script injection, control characters, oversized payloads, or prompt-injection strings in synopses/keywords).
4. **Upstream API Instability** (HTTP 429 rate limits, 5xx errors, network timeouts, or credential misconfiguration).
5. **Concurrent Review & Transaction Failures** (race conditions between admins or partial database writes).

Phase 8A prevents all five classes through deterministic candidate scoring (`metadata_matcher.py`), strict field validation (`metadata_validator.py`), database-level active job locking (`active_lock` unique constraint), optimistic concurrency (`expected_metadata_version`), and atomic database transactions (`metadata_application_service.py`).

---

## 2. Identity Ambiguity & Conflict Scenarios Verified

| Conflict / Ambiguity Type | Representative Case | Detection Mechanism | System & Admin Outcome |
|---|---|---|---|
| **Conflicting Release Year (>2 years)** | *His Girl Friday* (MovSug stored `1945-01-01` vs. TMDB `1940-01-18`, 5-year discrepancy) | `score_candidate()` applies `-12.0` year penalty, adds `"release_year_mismatch:1945!=1940"` to `conflicts`, and sets `match_status = "ambiguous"`. | Flagged in Admin UI; rejected by administrator during benchmark (`status = "rejected"`), leaving movie record untouched. |
| **Remake Disambiguation (With Year & Director)** | *Nosferatu* (`1922`, `F. W. Murnau`) vs. TMDB #653 (`1922`), #6404 (`1979`, Herzog), #426063 (`2024`, Eggers) | Title search retrieves all three remakes without year restriction first; `score_candidate()` awards `+25.0` exact year and `+15.0` director match to #653 (`96.5` vs `49.2` / `59.5`). | All 3 candidates staged for transparency; #653 ranked first and approved (`status = "applied"`). |
| **Remake / Adaptation Ambiguity (Missing Year & Director)** | *The Little Shop of Horrors* (stored with `release_date = None`, `director = None`) matching 1960 film (#24420) and 1986 musical (#10776) | `evaluate_and_rank_candidates()` detects multiple candidates within `<8.0` score margin (`71.9` vs `66.1`) and upgrades top candidate to `match_status = "ambiguous"` with conflict `"close_competing_candidates"`. | Held for human review; rejected by administrator (`status = "rejected"`) until catalog curator verifies which video edition is uploaded. |
| **Sequel Disambiguation** | *The Godfather Part II* (`1974`) vs. *The Godfather* (`1972`) | `_extract_sequel_marker()` extracts `"2"` from `"Part II"` and penalizes non-sequel candidate #238 by `-18.0` with conflict `"sequel_mismatch:movsug=2,candidate=none"`. | Sequel #240 ranked first (`96.5`) and approved; original 1972 film penalized to `40.4`. |
| **Common Title Disambiguation** | *The Gift* (`2015`, Dir: Joel Edgerton) vs. *The Gift* (`2000`, Dir: Sam Raimi) | Exact year (`2015`) and director (`Joel Edgerton`) separate #328425 (`96.5`) from #2046 (`44.5`, flagged with `"release_year_mismatch"` and `"director_mismatch"`). | Correct 2015 film selected and applied. |
| **Bilingual Concatenated Titles** | *Điều Ước CUối Cùng Của Tù Nhân 2037 - My Girl 2037 (2022)* & *Thám Tử Lừng Danh Conan 28... - Detective Conan: One-Eyed Flashback (2025)* | `parse_movsug_movie_identity()` splits `" - "` segments, strips trailing years, and generates both English and Vietnamese search queries. | Matched to TMDB #961729 (`My Girl`) and #1397832 (`Detective Conan: One-Eyed Flashback`). |
| **No-Match Case** | *Untitled Student Experimental Reel 9999XYZ* (`2024`) | TMDB search returns 0 results; `start_enrichment_job()` sets `status = "no_match"`, `review_state = "not_applicable"`, and clears `active_lock = None`. | Clean terminal state; movie record untouched; lock released for future attempts. |

---

## 3. Field-Level Conflict & Language Separation Safeguards

1. **Existing Value Overwrite Protection (`requires_explicit_overwrite`)**:
   - `compare_existing_and_proposed()` compares every proposed TMDB field against the current MovSug snapshot.
   - If a movie already has a non-empty value that differs from the TMDB proposal, `requires_explicit_overwrite = True` is set.
   - Attempting to approve that field via `POST /api/v1/admin/enrichment/jobs/{job_id}/approve` with `allow_overwrite_existing = False` is rejected with **HTTP 409 (`enrichment_validation_failed`)** (verified in `test_full_admin_enrichment_approval_and_application_preserves_protected_fields` and `MetadataEnrichmentPanel.test.tsx`).
2. **English vs. Vietnamese Language Separation**:
   - `validate_overview_en()` and `validate_keywords()` inspect character diacritics (`_VIETNAMESE_CHAR_RE`) to ensure Vietnamese text from localized TMDB endpoints never overwrites English `overview` or pollutes English `keywords` (verified in `test_language_separation_prevents_vietnamese_overwriting_english_overview`).
3. **Untrusted Input Sanitization**:
   - `_sanitize_plain_text()` strips HTML/script tags, removes zero-width and control characters, normalizes Unicode NFC, and neutralizes prompt-injection patterns (`ignore previous instructions`, `system prompt:`, `<|...|>`), verified in `test_untrusted_html_and_prompt_injection_sanitization`.

---

## 4. Operational Failure Recovery & Concurrency Verification

| Failure Mode | Test / Verification | Observed Behavior |
|---|---|---|
| **HTTP 429 Rate Limiting** | `test_tmdb_client.py::test_429_rate_limit_respects_retry_after` & Benchmark Movie #13 (`Charade`, TMDB #4808) | `TMDBClient` catches HTTP 429, parses `Retry-After` header, increments `http_429_count` (`1`) and `retry_count` (`1`), retries automatically, and succeeds on attempt 2 (`0` unrecovered API failures). |
| **Upstream 5xx / Timeout** | `test_tmdb_client.py::test_5xx_retries_and_exhaustion` & `test_timeout_retries_and_raises_structured_error` | Retries bounded by `TMDB_MAX_RETRIES`, then marks job `failed`, clears `active_lock`, and returns structured code `tmdb_upstream_error` / `tmdb_timeout`. |
| **Duplicate Active Enrichment Jobs** | `test_staging_does_not_mutate_movie_and_blocks_duplicate_active_jobs` | `UniqueConstraint("active_lock")` blocks concurrent active jobs for the same `(movie_id, provider)` with **HTTP 409 (`enrichment_duplicate_active_job`)**. |
| **Optimistic Concurrency Mismatch** | `test_concurrent_review_conflict_and_rejection_workflow` | Passing stale `expected_metadata_version` returns **HTTP 409 (`enrichment_concurrent_modification`)** without modifying `Movie` or applying stale fields. |
| **Database Transaction Failure During Apply** | `test_transaction_rollback_on_database_failure_during_application` | Simulated `SQLAlchemyError` mid-transaction triggers `db.rollback()`, keeps `movie.metadata_version == 1`, writes `0` provenance rows, marks `application_status = "rolled_back"`, and does not invalidate the recommendation cache. |

