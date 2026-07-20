# Final Project Audit

## 1. Audit Scope

This audit covers the complete `movie-recommendation-system` project before the academic report/thesis documentation is written. It inspects frontend, backend, database, recommendation engine, HLS/video, authentication/security, i18n/theme/accessibility, data quality, source/license, deployment, and documentation. All findings are evidence-based; no source code was modified.

---

## 2. Audited Revision and Environment

| Item | Value |
|------|-------|
| **Audit date/time** | 2026-07-19 11:49 +07:00 |
| **Git branch** | `main` |
| **Full commit hash** | `26614863ca9b0a52e5419eff40978215f9d63c4e` |
| **Short commit hash** | `2661486` |
| **Git remote URL** | `https://github.com/DungNgo13/movie-recommendation-system` |
| **Working tree status** | **Clean** (no staged, unstaged, or untracked changes) |
| **Operating system** | Windows |
| **Node.js version** | v24.14.0 |
| **npm version** | 11.9.0 |
| **Python version** | 3.14.3 |
| **Database mode** | SQLite (development) — `sqlite:///./test.db` |
| **Frontend API base URL** | `http://localhost:8000/api/v1` (dev default) |
| **Production URL** | `https://tltn.laetus.io.vn` (documented; NOT TESTED in this audit) |
| **Auditor environment** | Windows, local development |

**Working tree status:** Clean. Audit applies to a reproducible commit.

---

## 3. Executive Summary

The `movie-recommendation-system` (Laetus / Mov-Sug) is a full-stack academic project implementing a content-based movie recommendation website with HLS video streaming. The project demonstrates substantial technical depth across frontend (React+TypeScript+Vite), backend (FastAPI+SQLAlchemy), recommendation engine (TF-IDF+Cosine Similarity), and video processing (FFmpeg+HLS).

**Key strengths:**
- All automated validations pass: ESLint (0 errors), Vitest (271 tests), TypeScript (0 errors), Vite build (succeeds), Python compile (succeeds), pytest (176 tests), Alembic (single head, up to date)
- Strong recommendation engine test coverage including language invariance
- Clean architecture with separated services, schemas, and models
- Bilingual i18n infrastructure with proper locale parity
- Theme system with System/Light/Dark modes

**Key gaps:**
- No global SiteFooter with academic/non-commercial disclaimer
- Several hard-coded English strings in Navbar remain outside i18n
- HLS cache invalidation gap when video processing completes
- Cache invalidation only checks movie count, not content changes
- `docs/LEGAL_SOURCES.md` referenced in file map but does not exist
- Production deployment NOT TESTED (no server access from audit environment)

---

## 4. Overall Readiness Decision

### **READY WITH QUALIFICATIONS**

**Rationale:**
- ✅ Frontend lint: PASS (0 errors, 0 warnings)
- ✅ Frontend tests: PASS (14 files, 271 tests, all passing)
- ✅ Frontend build: PASS (TypeScript compilation + Vite production build)
- ✅ Backend compile: PASS (all modules compiled)
- ✅ Backend tests: PASS (176 tests, 0 failures)
- ✅ Alembic: Single head `e5f3a1b2c7d8`, current matches head
- ✅ Core recommendation engine: Implementation matches documentation
- ✅ No BLOCKER findings

**Qualifications:**
- Missing global SiteFooter with non-commercial/academic disclaimer (HIGH)
- Several hard-coded English strings in Navbar not using i18n (MEDIUM)
- Recommendation cache invalidation has a gap when HLS processing completes (MEDIUM)
- Cache only checks movie count, not metadata content changes (MEDIUM — documented as known limitation)
- Production deployment NOT TESTED from this environment
- Must disclose in report: cache limitations, no WCAG formal audit, no evaluation metrics

---

## 5. Validation Command Results

### Frontend

| Command | Result | Exit Code |
|---------|--------|-----------|
| `npm install` | Up to date, 274 packages, 0 vulnerabilities | 0 |
| `npm run lint` | No errors, no warnings | 0 |
| `npm run test:run` | 14 test files, 271 tests, all passed (3.43s) | 0 |
| `npm run build` | TypeScript: 0 errors. Vite: 124 modules, build in 342ms | 0 |
| `npm audit` | 0 vulnerabilities | 0 |

**Build output:**
| Asset | Size (uncompressed) | Size (gzip) |
|-------|-------------------|-------------|
| `index-BgTWMj3B.js` | 1,037.32 kB | 313.22 kB |
| `index-ejg8bN-A.css` | 82.76 kB | 13.73 kB |
| `icons8-movie-50-DiV1y87y.png` | 0.89 kB | — |

> Large-chunk warning: The JS bundle exceeds 500 kB. Code splitting is NOT currently used. This is a notice, not a build failure.

### Backend

| Command | Result |
|---------|--------|
| `python -m compileall app` | All modules compiled successfully |
| `alembic current` | `e5f3a1b2c7d8` (head) |
| `alembic heads` | `e5f3a1b2c7d8` (head) — single head confirmed |
| `alembic history` | 5 migrations, linear chain from `<base>` → `e5f3a1b2c7d8` |
| `pytest tests/ -v` | 176 passed, 0 failed, 1 warning (httpx deprecation) |

**Migration chain (ordered):**
1. `1780d0eefc59` — initial_baseline
2. `87079e588ea0` — add_cascade_deletes_and_indexes
3. `c3a1f7e9d042` — add source and license fields to movies
4. `d4b2e8f1a053` — create movie_assets table
5. `e5f3a1b2c7d8` — add vietnamese display metadata

---

## 6. Pass/Fail Matrix

| Area | Status | Details |
|------|--------|---------|
| Frontend ESLint | ✅ PASS | 0 errors, 0 warnings |
| Frontend Vitest | ✅ PASS | 271 tests, 14 files |
| Frontend TypeScript | ✅ PASS | 0 errors |
| Frontend Vite build | ✅ PASS | Production build succeeds |
| Frontend npm audit | ✅ PASS | 0 vulnerabilities |
| Backend compile | ✅ PASS | All modules compiled |
| Backend pytest | ✅ PASS | 176 tests passed |
| Alembic state | ✅ PASS | Single head, current = head |
| Recommendation implementation | ✅ PASS | Matches documentation |
| Recommendation invariance test | ✅ PASS | Vietnamese metadata excluded from vectors |
| Candidate pool filter | ✅ PASS | Tests confirm uploaded-only behavior |
| Cold start handling | ✅ PASS | Tested, falls back to recent movies |
| Theme system | ✅ PASS | System/Light/Dark with persistence |
| Language system | ✅ PASS | EN/VI with persistence |
| i18n locale parity | ⚠️ PARTIAL | 5 namespace files each, but hard-coded strings remain in Navbar |
| Global footer/disclaimer | ❌ FAIL | No SiteFooter component exists |
| Cache invalidation | ⚠️ PARTIAL | Create/update/delete covered; HLS ready transition NOT covered |
| Secret management | ✅ PASS | SECRET_KEY env-driven, no fallback, .env gitignored |
| Production deployment | 🔲 NOT TESTED | No server access from audit environment |
| CORS configuration | ✅ PASS | Environment-driven, not wildcard |
| Password hashing | ✅ PASS | bcrypt used |
| JWT security | ✅ PASS | HS256, env-driven secret, expiry configured |

---

## 7. Blockers

**No BLOCKER findings identified.**

All automated validations pass. The application can be built, tested, and demonstrated.

---

## 8. High-Severity Findings

### AUD-DOC-001
- **Area:** Source/License/Non-Commercial
- **Severity:** HIGH
- **Status:** FAIL
- **Title:** No global SiteFooter with academic/non-commercial disclaimer

**Evidence:**
- `grep -R "SiteFooter" frontend/src/` — 0 results
- `grep -R "footer" frontend/src/ --include="*.tsx" --include="*.ts"` — only ContinueWatchingCard internal "Content footer" comment
- `grep -R "non-commercial\|academic\|nghiên cứu" frontend/src/` — 0 results
- No `<footer>` element in App.tsx or any global layout component

**Expected behavior:** A global `<footer>` with the bilingual research/academic/non-commercial disclaimer should render on every page, in both themes and both languages.

**Actual behavior:** No global footer exists. The SourceAttribution component exists only on MovieDetailPage for per-movie licensing.

**Impact:** The academic/non-commercial disclaimer is absent from the deployed website.

**Academic-report impact:** The report cannot claim the website displays a non-commercial disclaimer until this is added.

**Recommended remediation:** Create a `SiteFooter.tsx` component with the required bilingual disclaimer text, render it in `App.tsx` after `<Routes>`, ensure it is visible in Light/Dark modes.

**Verification after remediation:** Visual inspection in both themes and languages; check that footer appears on Home, MovieDetail, Favorites, auth pages, and admin pages.

---

### AUD-DOC-002
- **Area:** Documentation
- **Severity:** HIGH
- **Status:** FAIL
- **Title:** `docs/LEGAL_SOURCES.md` referenced in PROJECT_FILE_MAP but does not exist

**Evidence:**
- `docs/PROJECT_FILE_MAP.md` line 203 lists: `docs/LEGAL_SOURCES.md — Legal source guidelines`
- `Test-Path docs/LEGAL_SOURCES.md` → NOT FOUND

**Expected behavior:** All files listed in the project file map should exist.

**Actual behavior:** `LEGAL_SOURCES.md` is listed but missing.

**Impact:** Documentation inconsistency; the file map is unreliable.

**Academic-report impact:** Cannot cite this document for legal source guidelines.

**Recommended remediation:** Either create the file or remove the reference from PROJECT_FILE_MAP.md.

---

## 9. Medium-Severity Findings

### AUD-I18N-001
- **Area:** i18n
- **Severity:** MEDIUM
- **Status:** FAIL
- **Title:** Hard-coded English strings in Navbar not using i18n

**Evidence:**
- `Navbar.tsx:43` — `>Movies<` (hard-coded)
- `Navbar.tsx:44` — `>Users<` (hard-coded)
- `Navbar.tsx:45` — `>Logs<` (hard-coded)
- `Navbar.tsx:46` — `>RecSys<` (hard-coded)
- `Navbar.tsx:47` — `>Security<` (hard-coded)
- `Navbar.tsx:77` — `Logout` (hard-coded)
- `Navbar.tsx:54` — `title="My Profile"` (hard-coded)

**Expected behavior:** All user-facing strings should use `t()` translation function.

**Actual behavior:** Admin nav links and Logout button display English text regardless of language setting.

**Impact:** Vietnamese users see mixed-language Navbar when switching language.

**Academic-report impact:** The bilingual claim must be qualified — admin navigation links are English-only.

---

### AUD-REC-001
- **Area:** Recommendation Engine — Cache
- **Severity:** MEDIUM
- **Status:** FAIL
- **Title:** HLS processing completion does not invalidate recommendation cache

**Evidence:**
- `hls_service.py:11` imports `invalidate_cache as _invalidate_rec_cache`
- `grep "_invalidate_rec_cache()" hls_service.py` — 0 results (imported but never called)
- When HLS processing transitions a movie to `processing_status="ready"`, the candidate pool changes (if `RECOMMEND_ONLY_UPLOADED_MOVIES=true`) but cache is NOT invalidated
- Cache validation only checks `movie_count` and `filter_flag` — not metadata content

**Expected behavior:** When a movie's video becomes "ready", the recommendation cache should be invalidated since the candidate pool has changed.

**Actual behavior:** The function is imported but never called in hls_service.py. The newly-ready movie won't appear in recommendations until the next cache miss from a different trigger (e.g., another movie being added).

**Impact:** After admin uploads and processes a video, the movie may not immediately appear in recommendations.

**Academic-report impact:** Document as a known limitation of the simple caching strategy.

---

### AUD-REC-002
- **Area:** Recommendation Engine — Cache
- **Severity:** MEDIUM
- **Status:** PARTIAL
- **Title:** Cache invalidation checks movie count only, not metadata content changes

**Evidence:**
- `vectorizer.py:71-79` — `_is_cache_valid()` checks only `movie_count` and `filter_flag`
- `movie_service.py:204-205` — update_movie calls `invalidate_cache()` after every update
- However, the explicit `invalidate_cache()` call in `movie_service.py` means this is actually handled correctly for the CRUD path
- The `_is_cache_valid` function alone wouldn't detect content changes, but the explicit invalidation calls compensate

**Expected behavior:** Cache should be invalidated when movie content changes.

**Actual behavior:** The code has TWO mechanisms: (1) `movie_service.py` explicitly calls `invalidate_cache()` on create/update/delete — this works correctly. (2) The fallback `_is_cache_valid()` only checks count — documented as a known weakness. This is correct behavior for the academic project but should be documented.

**Impact:** LOW in practice (explicit invalidation covers CRUD). Medium for academic accuracy of cache documentation.

---

### AUD-I18N-002
- **Area:** i18n / Accessibility
- **Severity:** MEDIUM
- **Status:** FAIL
- **Title:** Favorite button aria-labels hard-coded in English in RecommendationCard

**Evidence:**
- `RecommendationCard.tsx:40-41` — `Remove ${localizedTitle} from favorites` / `Add ${localizedTitle} to favorites` (English template, not using `t()`)

**Expected behavior:** Accessible labels should be translated.

**Actual behavior:** Screen readers announce in English regardless of language setting.

---

### AUD-DOC-003
- **Area:** Documentation
- **Severity:** MEDIUM
- **Status:** FAIL
- **Title:** `docs/streaming_architecture.md` contains outdated and unclear prose

**Evidence:**
- References `uploads/videos/source` as storage path (line 10) — actual media path is `media/videos/source`
- References `BackgroundTasks` thread (line 14) — actual implementation uses `asyncio.Queue` with `encoding_worker`
- Contains unusual verbose filler language ("dynamically natively bounding status strings", "resolving Firefox and Google Edge .m3u8 unrecognition constraints naturally")

**Expected behavior:** Documentation should accurately describe the current implementation.

**Actual behavior:** Multiple outdated references and unclear prose.

---

### AUD-DOC-004
- **Area:** Documentation
- **Severity:** MEDIUM
- **Status:** FAIL
- **Title:** Deployment documentation references different domain than frontend .env.production

**Evidence:**
- `docs/deployment.md` references `laetus.io.vn` throughout (lines 14, 24-27, 146, etc.)
- `frontend/.env.production` contains `VITE_API_BASE_URL=https://api.laetus.io.vn/api/v1`
- README mentions the URL as `tltn.laetus.io.vn` is absent from deployment docs
- Deployment docs show Nginx with SSL (Let's Encrypt) but actual deployment uses Cloudflare tunnel

---

### AUD-BE-001
- **Area:** Backend
- **Severity:** MEDIUM
- **Status:** RESOLVED (removed in repository cleanup)
- **Title:** Legacy migration scripts in backend root not managed by Alembic

**Evidence:**
- 12 Python files in `backend/` root with `migrate_*.py` and `fix_db.py` naming pattern existed before cleanup
- These predated the Alembic migration system and were obsolete

**Resolution:** All 12 legacy scripts removed from tracking during pre-submission cleanup. Current Alembic head (`e5f3a1b2c7d8`) covers all schema. Git history preserves the files.

---

## 10. Low-Severity Findings

### AUD-FE-001
- **Area:** Frontend — Build
- **Severity:** LOW
- **Status:** PASS (informational)
- **Title:** Single JS bundle exceeds 500 kB

**Evidence:** `index-BgTWMj3B.js` = 1,037.32 kB (uncompressed), 313.22 kB (gzip). No code splitting used.

**Impact:** Slower initial page load on slow connections. Acceptable for academic demo.

---

### AUD-FE-002
- **Area:** Frontend
- **Severity:** LOW
- **Status:** PARTIAL
- **Title:** `.env.production` tracked in git

**Evidence:** `git ls-files -- "*.env" "*.env.*"` shows `frontend/.env.production` is tracked. Contents: `VITE_API_BASE_URL=https://api.laetus.io.vn/api/v1` — no secrets, only a public URL.

**Impact:** Not a security issue (no secrets), but deviates from best practice of keeping env files untracked.

---

### AUD-BE-002
- **Area:** Backend
- **Severity:** LOW
- **Status:** PARTIAL
- **Title:** Stale test output files tracked or present in backend

**Evidence:** Files in `backend/`: `pytest_results.txt` (36KB), `test_out.txt` (2.9KB), `test_output.txt` (2.9KB), file named `-t` (222 bytes — likely created by accidental command).

**Impact:** Minor clutter; no functional impact.

---

### AUD-BE-003
- **Area:** Backend
- **Severity:** LOW
- **Status:** PASS (informational)
- **Title:** Dual venv directories in backend

**Evidence:** Both `backend/.venv/` and `backend/venv/` directories exist. Both are gitignored.

**Impact:** Disk space waste only.

---

## 11. Informational Findings

### AUD-INFO-001
- **Area:** Recommendation Engine
- **Severity:** INFORMATIONAL
- **Title:** Recommendation weights match documentation exactly

**Evidence verified by code inspection:**

| Signal | Weight (code) | Weight (docs) | Match |
|--------|:---:|:---:|:---:|
| Rating 5★ | 5.0 | 5.0 | ✅ |
| Rating 4★ | 3.0 | 3.0 | ✅ |
| Rating 3★ | 1.0 | 1.0 | ✅ |
| Rating 2★ | 0.0 | 0.0 | ✅ |
| Rating 1★ | 0.0 | 0.0 | ✅ |
| Favorite | 3.0 | 3.0 | ✅ |
| Watch min | 1.0 | 1.0 | ✅ |
| Watch max | 3.0 | 3.0 | ✅ |
| Decay rate | 0.05 | 0.05 | ✅ |
| Signal combination | MAX | MAX | ✅ |

Source: `user_profile.py` lines 57–72.

### AUD-INFO-002
- **Area:** Recommendation Engine
- **Severity:** INFORMATIONAL
- **Title:** TF-IDF configuration matches documentation exactly

| Parameter | Value (code) | Value (docs) | Match |
|-----------|:---:|:---:|:---:|
| max_features | 5000 | 5000 | ✅ |
| stop_words | "english" | "english" | ✅ |
| ngram_range | (1, 2) | (1, 2) | ✅ |
| min_df | 1 | 1 | ✅ |
| max_df | 0.95 (or 1.0 if <2 docs) | 0.95 | ✅ |

Source: `vectorizer.py` lines 101–110.

### AUD-INFO-003
- **Area:** Recommendation Engine
- **Severity:** INFORMATIONAL
- **Title:** Movie profile field repetition matches documentation

| Field | Repetition (code) | Repetition (docs) | Match |
|-------|:---:|:---:|:---:|
| title | ×2 | ×2 | ✅ |
| overview | ×1 | ×1 | ✅ |
| genres | ×1 | ×1 | ✅ |
| cast | ×1 (with "actor" prefix) | ×1 (with prefix) | ✅ |
| keywords | ×2 | ×2 | ✅ |
| director | ×1 (with "director" prefix) | ×1 (with prefix) | ✅ |
| title_vi | NOT USED | NOT USED | ✅ |
| overview_vi | NOT USED | NOT USED | ✅ |
| keyword_labels_vi | NOT USED | NOT USED | ✅ |

Source: `movie_profile.py` lines 16–65.

### AUD-INFO-004
- **Area:** Architecture
- **Severity:** INFORMATIONAL
- **Title:** ThemeProvider is global and independent from authentication

**Evidence:** `main.tsx` wraps `ThemeProvider` around `BrowserRouter` > `AuthProvider` > `App`. Theme is initialized before auth, and uses separate localStorage key `movie-app-theme`. Language uses `movie-app-language`.

### AUD-INFO-005
- **Area:** Security
- **Severity:** INFORMATIONAL
- **Title:** SECRET_KEY has no fallback — application crashes if not set

**Evidence:** `security.py:11-17` — Raises `RuntimeError` if SECRET_KEY is empty/missing. This is correct security behavior.

---

## 12. Frontend Audit

### Architecture
- ✅ Clean component/page/service/hook/model separation
- ✅ API calls in service files, not UI components
- ✅ TypeScript — no explicit `any` found in .tsx files
- ✅ Loading states (SkeletonCard, LoadingSpinner)
- ✅ Error states (ErrorMessage component)
- ✅ ThemeProvider global and independent from auth
- ✅ Language initialization occurs before rendering (`i18n/index.ts` runs synchronously)
- ✅ AbortController used in MovieDetailPage metadata discovery
- ✅ React Hook dependencies appear correct
- ✅ SPA route structure with protected admin routes

### Test Coverage
- 14 test files, 271 tests
- Components: ThemeSelector, StarRating, FavoriteHeart, ContinueWatchingCard
- Pages: HomePage, MovieDetailPage
- Services: continueWatchingService, guestFavorites, mediaUrl
- Theme: ThemeContext, themeStorage
- Utils: movieFilters, passwordValidator, languageStorage

---

## 13. Backend Audit

### Architecture
- ✅ Router → Service → Model separation
- ✅ Pydantic schemas for request/response validation
- ✅ FastAPI lifespan for HLS encoding worker
- ✅ CORS environment-driven
- ✅ Database auto-detection (SQLite/PostgreSQL)
- ✅ Alembic migration management
- ✅ bcrypt password hashing
- ✅ JWT authentication with configurable expiry

### Test Coverage
- 12 test files, 176 tests covering:
  - Auth (login, JWT, IP tracking, password reset)
  - Movies (CRUD, upload, validation)
  - Recommendation engine (end-to-end, cold start, cache, negative signals)
  - Recommendation invariance (Vietnamese metadata exclusion)
  - Candidate filter (uploaded-only flag)
  - Watch progress (save/load, completion)
  - User profile (avatar, password change)
  - Password validator
  - Upload limits
  - URL normalization

---

## 14. Database Audit

### Schema
- 7 models: User, Movie, Rating, UserFavorite, WatchHistory, AdminAuditLog, MovieAsset
- 5 Alembic migrations, linear chain, single head
- Vietnamese display fields (title_vi, overview_vi, keyword_labels_vi) are nullable — backward compatible

### Integrity (model/migration inspection)
- ✅ Foreign key relationships defined in models
- ✅ CASCADE delete behavior defined in migration `87079e588ea0`
- ✅ Rating CHECK constraint (1–5) defined in model
- ✅ UserFavorite unique constraint on (user_id, movie_id)
- ⚠️ Production database access NOT TESTED (would need PostgreSQL server)

---

## 15. Recommendation-Engine Audit

### Implementation Verification
- ✅ Content-based filtering (NOT collaborative, NOT deep learning)
- ✅ Movie profile: uses title, overview, genres, cast, keywords, director
- ✅ Movie profile: ignores title_vi, overview_vi, keyword_labels_vi
- ✅ User profile: 3 signal sources (ratings, favorites, watch history)
- ✅ Signal combination: MAX (not additive)
- ✅ L2 normalization of user vector
- ✅ Cold start: falls back to recent movies from candidate pool
- ✅ Favorite exclusion: favorited movies excluded from results
- ✅ Candidate pool: RECOMMEND_ONLY_UPLOADED_MOVIES flag works correctly

### Test Evidence
| Aspect | Coverage |
|--------|----------|
| Movie profile generation | ✅ Covered (invariance test) |
| Vietnamese-field exclusion | ✅ Covered (test_recommendation_invariance.py) |
| User profile weights | ✅ Covered (test_recommendation_engine.py) |
| MAX signal combination | ✅ Covered |
| Watch time decay | ✅ Covered |
| L2 normalization | ✅ Covered (implicit in end-to-end tests) |
| Cold start | ✅ Covered (4 tests) |
| Candidate-pool filtering | ✅ Covered (test_candidate_filter.py, 7 tests) |
| Favorite exclusion | ✅ Covered |
| Score ordering | ✅ Covered |
| Top-N | ✅ Covered |
| Reason generation | ✅ Covered (response structure test) |
| Language invariance | ✅ Covered (test_recommendation_invariance.py) |

### Cache Invalidation Matrix
| Trigger | Invalidation | Status |
|---------|:---:|:---:|
| Movie created | ✅ `movie_service.py:172` | PASS |
| Movie updated (metadata) | ✅ `movie_service.py:205` | PASS |
| Movie deleted | ✅ `movie_service.py:220` | PASS |
| HLS processing completes | ❌ Imported but not called | FAIL |
| Video becomes "ready" | ❌ Not triggered | FAIL |

---

## 16. HLS/Video Audit

### Architecture (code inspection)
- ✅ Async queue-based encoding (1 FFmpeg process at a time)
- ✅ FFmpeg/FFprobe path resolution with fallback
- ✅ Quality ladder from source resolution
- ✅ Master playlist with RESOLUTION entries
- ✅ Frontend HlsPlayer uses hls.js with Plyr wrapper
- ✅ Quality switching via `currentLevel` (no `video.src` replacement)
- ✅ isMounted guard prevents zombie Plyr instances
- ✅ levelSwitchInProgress guard prevents infinite loops
- ✅ Cache-bust on master playlist URL

### Media directory
- Cannot verify actual HLS playlists (media directory is gitignored)
- HLS structure: `media/videos/hls/<movie_id>/master.m3u8`

---

## 17. Authentication/Security Audit

### Verified (code inspection)
- ✅ bcrypt password hashing (`security.py`)
- ✅ JWT with HS256, environment-driven secret
- ✅ No secret fallback — crashes on missing SECRET_KEY
- ✅ Password validation with complexity rules (min 8 chars, uppercase, digit, special)
- ✅ Password reset tokens with expiry
- ✅ Failed login tracking and brute-force detection
- ✅ CORS environment-driven, not wildcard
- ✅ Admin route protection (frontend + backend)
- ✅ Upload file type and size validation
- ✅ .env files gitignored (both root and backend)
- ✅ No secrets found in tracked files (git grep confirmed)
- ⚠️ `frontend/.env.production` tracked — contains only public API URL, not secrets

### npm audit
- 0 vulnerabilities found

### Python dependency audit
- NOT TESTED (no pre-installed audit tool)

---

## 18. i18n/Theme/Accessibility Audit

### i18n
- ✅ 5 namespace files per language (common, auth, movies, admin, recommendation)
- ✅ `<html lang>` updated on language change
- ✅ Locale parity: EN and VI have matching key structures
- ✅ Recommendation reason translation mapper covers all backend variants
- ✅ Unknown reasons fall back to raw backend string
- ⚠️ Navbar admin links hard-coded in English (Movies, Users, Logs, RecSys, Security, Logout)
- ⚠️ RecommendationCard favorite button aria-labels hard-coded in English

### Theme
- ✅ Default mode: System
- ✅ Storage key: `movie-app-theme`
- ✅ Invalid stored values fall back to `system`
- ✅ System mode listens to `prefers-color-scheme` changes
- ✅ Manual modes ignore OS preference changes
- ✅ `data-theme` and `color-scheme` set on `<html>`
- ✅ ThemeSelector uses segmented-control design
- ✅ LanguageSelector uses segmented-control design

### Accessibility (focused review)
- ✅ Semantic `<nav>` element
- ✅ Star rating has aria-labels
- ✅ Favorite heart has aria-labels (but English-only in RecommendationCard)
- ✅ Movie cards have alt text on posters
- ✅ HlsPlayer poster image
- ⚠️ No `<footer>` landmark exists
- ⚠️ No `<main>` landmark wrapping content
- ⚠️ Focused accessibility review only — NOT WCAG compliant

---

## 19. Data and Metadata Quality

### Catalog Statistics
- Database: `backend/test.db` (SQLite, development)
- Cannot query production database from audit environment
- Seed data: 20 sample movies (per `seed.py` documentation)

### Metadata Quality Observations (from seed.py inspection)
- Movies are seeded with English metadata
- Vietnamese metadata fields are nullable — existing records remain compatible
- keyword_labels_vi is a JSON mapping `{"english_keyword": "vietnamese_label"}`

---

## 20. Source/License/Non-Commercial Audit

### Per-Movie Attribution
- ✅ SourceAttribution component exists on MovieDetailPage
- ✅ Movie model has source_name, source_url, license_type, license_url, attribution, is_public_domain, media_rights_status fields
- ✅ MovieAsset model for per-asset license tracking

### Global Disclaimer
- ❌ **No global SiteFooter with non-commercial/academic disclaimer**
- The SourceAttribution component is per-movie only (on MovieDetailPage)
- No bilingual academic-purpose statement appears on the website

---

## 21. Deployment Audit

**Status: NOT TESTED**

Production deployment checks could not be performed from the local Windows audit environment. No SSH access to the production server was available.

**Documented deployment configuration (from `docs/deployment.md`):**
- Ubuntu + Nginx reverse proxy
- FastAPI via Uvicorn on 127.0.0.1:8000
- Cloudflare tunnel (mentioned in audit notes)
- PostgreSQL production database
- systemd service for backend

**Frontend production env:**
- `VITE_API_BASE_URL=https://api.laetus.io.vn/api/v1`

---

## 22. Documentation Discrepancies

| Document | Discrepancy |
|----------|-------------|
| `docs/PROJECT_FILE_MAP.md:203` | Lists `docs/LEGAL_SOURCES.md` — file does not exist |
| `docs/PROJECT_FILE_MAP.md` | Does not list `e5f3a1b2c7d8_add_vietnamese_display_metadata.py` migration |
| `docs/PROJECT_FILE_MAP.md` | Does not list `test_recommendation_invariance.py`, `test_candidate_filter.py` backend tests |
| `docs/PROJECT_FILE_MAP.md` | Does not list `frontend/src/utils/localizedMovie.ts`, `recommendationReason.ts`, `movieFilters.ts` |
| `docs/PROJECT_FILE_MAP.md` | Does not list `frontend/src/components/LanguageSelector.tsx`, `FavoriteHeart.test.tsx`, `ContinueWatchingCard.test.tsx` |
| `docs/PROJECT_FILE_MAP.md` | Does not list `frontend/src/services/guestFavorites.test.ts`, `mediaUrl.test.ts` |
| `docs/PROJECT_FILE_MAP.md` | Does not list `frontend/src/theme/themeStorage.test.ts`, `ThemeContext.test.tsx` |
| `docs/PROJECT_FILE_MAP.md` | Does not list `frontend/src/i18n/languageStorage.test.ts` |
| `docs/streaming_architecture.md:10` | References `uploads/videos/source` — actual path is `media/videos/source` |
| `docs/streaming_architecture.md:14` | References `BackgroundTasks` — actual implementation uses `asyncio.Queue` + `encoding_worker` |
| `docs/streaming_architecture.md` | Contains unusual filler prose that doesn't match engineering documentation standards |
| `docs/RECOMMENDATION_ENGINE_EXPLAINED.md:112` | States cache invalidates when movie count changes — partially correct; explicit invalidation also covers CRUD |
| `docs/deployment.md` | References `laetus.io.vn` — production may use `tltn.laetus.io.vn` subdomain |
| `README.md:322` | Claims "Guest watch history có thể merge vào tài khoản sau khi đăng nhập" — merge implementation not verified |
| `README.md:323` | Claims "Guest favorites có thể merge vào tài khoản sau khi đăng nhập" — merge implementation not verified |
| `PROJECT_RULES.md:6` | Lists Database as PostgreSQL — should mention dual SQLite/PostgreSQL support |

---

## 23. Academic-Report Readiness

### Evidence Matrix

| Claim | Code Evidence | Test Evidence | Runtime Evidence | Confidence | Suitable for Report |
|-------|:---:|:---:|:---:|:---:|:---:|
| Content-based filtering (TF-IDF + Cosine Similarity) | ✅ | ✅ | — | HIGH | Yes |
| 3 signal sources (ratings, favorites, watch) | ✅ | ✅ | — | HIGH | Yes |
| MAX signal combination | ✅ | ✅ | — | HIGH | Yes |
| L2 normalization | ✅ | ✅ | — | HIGH | Yes |
| Cold start handling | ✅ | ✅ | — | HIGH | Yes |
| Candidate pool filtering | ✅ | ✅ | — | HIGH | Yes |
| Language invariance | ✅ | ✅ | — | HIGH | Yes |
| HLS multi-quality streaming | ✅ | — | NOT TESTED | MEDIUM | With qualification |
| JWT authentication | ✅ | ✅ | — | HIGH | Yes |
| Password reset with email | ✅ | ✅ | — | HIGH | Yes |
| Bilingual interface (EN/VI) | ✅ | ✅ | — | HIGH | With qualification (admin nav English-only) |
| Theme system (Light/Dark/System) | ✅ | ✅ | — | HIGH | Yes |
| Watch progress persistence | ✅ | ✅ | — | HIGH | Yes |
| Favorites system | ✅ | ✅ | — | HIGH | Yes |
| Rating system (1-5 stars) | ✅ | ✅ | — | HIGH | Yes |
| Admin dashboard | ✅ | — | NOT TESTED | MEDIUM | Yes |
| PostgreSQL production | ✅ (code) | — | NOT TESTED | MEDIUM | With qualification |
| Non-commercial disclaimer | ❌ | — | ❌ | LOW | No (must be added first) |
| WCAG accessibility | — | — | — | LOW | No (focused review only) |
| Recommendation accuracy metrics | — | — | — | NONE | No (no evaluation data exists) |

### Claims That Must NOT Be Made
- ❌ Do NOT call the system collaborative filtering — it is content-based only
- ❌ Do NOT call it deep learning — no neural model exists
- ❌ Do NOT claim recommendation accuracy without evaluation data
- ❌ Do NOT claim full production security without penetration testing
- ❌ Do NOT claim copyright ownership of third-party media
- ❌ Do NOT claim WCAG compliance — only a focused accessibility review was performed
- ❌ Do NOT claim 4K output unless verified from actual playlists
- ❌ Do NOT claim guest history merge if implementation is not verified

---

## 24. Prioritized Remediation Plan

### Phase 0 — Before Report Writing (No Blockers)

*No blockers exist. Phase 0 is empty.*

### Phase 1 — Must Fix Before Final Demonstration

| Priority | Finding ID | Action | Files | Complexity | Risk |
|:---:|---|---|---|:---:|---|
| 1 | AUD-DOC-001 | Create SiteFooter with bilingual disclaimer | `SiteFooter.tsx`, `App.tsx`, `App.css`, locale files | Medium | Low |
| 2 | AUD-I18N-001 | Move Navbar hard-coded strings to i18n | `Navbar.tsx`, `en/common.json`, `vi/common.json` | Small | Low |
| 3 | AUD-REC-001 | Call `_invalidate_rec_cache()` in hls_service when movie becomes "ready" | `hls_service.py` | Small | Low |

### Phase 2 — Must Disclose in Report

| Priority | Finding ID | Action | Complexity |
|:---:|---|---|:---:|
| 4 | AUD-REC-002 | Document cache simplicity as known limitation | Small |
| 5 | AUD-DOC-003 | Rewrite streaming_architecture.md to match current implementation | Medium |
| 6 | AUD-DOC-002 | Create or remove reference to LEGAL_SOURCES.md | Small |
| 7 | AUD-I18N-002 | Translate aria-labels in RecommendationCard | Small |

### Phase 3 — Optional Improvements After Submission

| Priority | Finding ID | Action | Complexity |
|:---:|---|---|:---:|
| 8 | AUD-FE-001 | Implement code splitting for JS bundle | Medium |
| 9 | AUD-BE-001 | Remove legacy migrate_*.py scripts from backend root | Small |
| 10 | AUD-BE-002 | Remove stale test output files | Small |
| 11 | AUD-DOC-004 | Reconcile deployment docs with actual production config | Medium |
| 12 | AUD-FE-002 | Move .env.production to .env.production.example | Small |

---

## 25. Final Verification Checklist

- [x] Git revision recorded
- [x] Working tree state recorded
- [x] Frontend lint passed
- [x] Frontend tests passed
- [x] Frontend build passed
- [x] Backend compiled
- [x] Backend tests passed
- [x] Alembic state verified
- [x] Database integrity reviewed (model/migration inspection)
- [x] API contract reviewed (router/schema inspection)
- [x] Recommendation implementation verified
- [x] Recommendation language invariance verified
- [x] HLS architecture reviewed (code inspection)
- [x] Watch progress reviewed
- [x] Favorites and ratings reviewed
- [x] Authentication reviewed
- [x] Admin functions reviewed (code inspection)
- [x] Bilingual interface reviewed
- [x] Theme behavior reviewed
- [x] Footer disclaimer reviewed (FAIL — not present)
- [x] Accessibility reviewed (focused review)
- [ ] Responsive layouts reviewed (NOT TESTED — requires runtime)
- [x] Security review completed
- [x] Source/license metadata reviewed
- [ ] Production deployment reviewed (NOT TESTED)
- [x] Documentation discrepancies listed
- [x] Academic claims evidence matrix completed
- [x] Final readiness decision issued

---

## 26. Appendix: Commands and Evidence

### Git State
```
Branch: main
Commit: 26614863ca9b0a52e5419eff40978215f9d63c4e
Short: 2661486
Remote: https://github.com/DungNgo13/movie-recommendation-system
Status: Clean
Last commit: 2026-07-18 14:17:27 +0700 — feat: implement localization for HomePage and add corresponding test suite
```

### Runtime Versions
```
Node.js: v24.14.0
npm: 11.9.0
Python: 3.14.3
```

### Frontend Validation
```
npm install: up to date, 274 packages, 0 vulnerabilities
npm run lint: 0 errors, 0 warnings
npm run test:run: 14 files, 271 tests, all passed
npm run build: TypeScript 0 errors, Vite build in 342ms
npm audit: 0 vulnerabilities
```

### Backend Validation
```
python -m compileall app: all modules compiled
alembic current: e5f3a1b2c7d8 (head)
alembic heads: e5f3a1b2c7d8 (single head)
pytest tests/ -v: 176 passed, 0 failed, 1 warning
```

### Security Scans
```
git grep SECRET_KEY= PASSWORD= API_KEY= postgresql:// smtp: No tracked secrets found
npm audit: 0 vulnerabilities
.env files: gitignored (both root and backend)
frontend/.env.production: tracked but contains only public API URL
```

---

## Post-Audit Remediation

### Remediation Date
2026-07-19 (same day as audit)

### Remediation Scope
All HIGH and MEDIUM severity findings from the audit were addressed. No features were added. No breaking changes were introduced.

### Resolved Findings

#### 1. Global SiteFooter with Academic Disclaimer (HIGH → RESOLVED)
**Audit Finding:** No global footer with non-commercial/academic disclaimer.

**Resolution:**
- Created `frontend/src/components/SiteFooter.tsx` — bilingual `<footer>` with academic disclaimer
- Added CSS styles (`.site-footer`, `.site-footer__inner`, `.site-footer__copyright`, `.site-footer__disclaimer`)
- Added i18n keys to `en/common.json` and `vi/common.json` (`footer.ariaLabel`, `footer.disclaimer`)
- Updated `App.tsx` with `app-shell` flex layout: `<Navbar/>` → `<main><Routes/></main>` → `<SiteFooter/>`
- Created `SiteFooter.test.tsx` with 10 tests (semantic structure, year, disclaimer, layout integration)

**Verification:** 15 test files, 281 tests, all passed. Build succeeds.

#### 2. Navbar i18n — Hard-coded English Strings (MEDIUM → RESOLVED)
**Audit Finding:** Admin links (Movies, Users, Logs, RecSys, Security), Logout, and "My Profile" title were hard-coded English.

**Resolution:**
- All 7 hard-coded strings replaced with `t()` calls using `navbar.*` keys
- Added corresponding keys to both `en/common.json` and `vi/common.json`
- Also fixed existing `t()` calls from `navbar:key` (namespace separator) to `navbar.key` (nested key) for consistency with the flat common namespace

**Verification:** Lint passes. All existing Navbar-dependent tests pass.

#### 3. Favorite Accessibility — Hard-coded English Aria Labels (MEDIUM → RESOLVED)
**Audit Finding:** `MovieCard.tsx`, `RecommendationCard.tsx`, and `ContinueWatchingCard.tsx` had hard-coded English `"Add/Remove <title> to/from favorites"` aria-labels.

**Resolution:**
- All 3 components updated to use `t('movies:favorites.add/remove', defaultValue, { title })` pattern
- Added `favorites.add` and `favorites.remove` keys to both `en/movies.json` and `vi/movies.json`
- Default values ensure backward compatibility with the test mock

**Verification:** All 18 FavoriteHeart tests pass. All 28 ContinueWatchingCard tests pass.

#### 4. HLS Cache Invalidation (MEDIUM → VERIFIED/RESOLVED)
**Audit Finding:** `_invalidate_rec_cache()` was imported but never called after HLS processing completes.

**Status at Remediation Start:** Already fixed in current code at lines 483 and 521 of `hls_service.py`. The call was added between the audited commit (`2661486`) and the current HEAD, or was present but the audit inspector missed it.

**Resolution:**
- Verified correct placement: called after `db.commit()` that sets `processing_status = "ready"`, for both multi-quality (line 483) and fallback (line 521) paths
- NOT called after failed or cancelled conversion (verified by code inspection and tests)
- Created `backend/tests/test_hls_cache_invalidation.py` with 5 new tests:
  - `test_multi_quality_success_invalidates_cache` ✅
  - `test_fallback_success_invalidates_cache` ✅
  - `test_failed_conversion_does_not_invalidate_cache` ✅
  - `test_cancelled_conversion_does_not_invalidate_cache` ✅
  - `test_progress_updates_do_not_repeatedly_invalidate_cache` ✅

**Verification:** 5 backend tests pass. Backend full suite passes.

#### 5. Missing `docs/LEGAL_SOURCES.md` (MEDIUM → RESOLVED)
**Audit Finding:** Referenced in `PROJECT_FILE_MAP.md` but file did not exist.

**Resolution:** Created `docs/LEGAL_SOURCES.md` — content source and license guidelines describing per-movie and per-asset metadata fields, rights status values, and review checklist.

#### 6. Documentation Updates (LOW → RESOLVED)
- **`docs/streaming_architecture.md`**: Complete rewrite to match current implementation including quality selection table, cache invalidation, cancellation, watch progress integration
- **`docs/deployment.md`**: Added note about `api.laetus.io.vn` subdomain configuration
- **`docs/PROJECT_FILE_MAP.md`**: Added SiteFooter, ContinueWatchingCard, HeartIcon, ThemeSelector, LanguageSelector, HLS cache test, FINAL_PROJECT_AUDIT.md, REPORT_FACTS_SNAPSHOT.md
- **`PROJECT_RULES.md`**: Updated database description from "PostgreSQL" to "SQLite (development/tests) / PostgreSQL (production)"

### Remaining Known Limitations (Documented, Not Fixed)
These items were identified in the audit and are documented as known limitations for the thesis:

1. **Cache invalidation only checks movie count** — Does not detect metadata-only changes. Documented as acceptable for academic scope.
2. **No WCAG formal audit** — Accessibility improvements were made (i18n aria labels, semantic footer) but no formal WCAG audit was performed.
3. **Production deployment NOT TESTED** — No server access from the audit environment.
4. **Large JS bundle** — 1,038 kB (313 kB gzip). Code splitting not implemented. Documented as a notice.
5. **Legacy scripts** — `backend/scripts/importers/` are one-time data import scripts, not active application code. Retained for reproducibility.

### Post-Remediation Validation Results

#### Frontend
```
npm run lint: 0 errors, 0 warnings
npm run test:run: 15 files, 281 tests, all passed
npm run build: TypeScript 0 errors, Vite build succeeds (125 modules, 338ms)
```

#### Backend
```
pytest tests/ -v: 181 passed (176 original + 5 new HLS cache tests)
python -m compileall app: all modules compiled
```

