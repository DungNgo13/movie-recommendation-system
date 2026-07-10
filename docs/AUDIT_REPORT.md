# Audit Report — Mov-Sug Movie Recommendation System

**Audit Date:** 2026-07-10  
**Auditor Role:** Senior Full-Stack Auditor, Security Reviewer & Academic Project Advisor  
**Branch:** main  
**Scope:** Full project (backend, frontend, AI recommendation, database, security, deployment)

---

## 1. Executive Summary

Mov-Sug is a well-structured academic project combining full-stack web development, AI-based recommendation (TF-IDF + Cosine Similarity), and HLS video streaming. The codebase is clean, well-documented, and follows good separation of concerns (routers → services → models). The recommendation engine implementation matches its documentation closely and is intellectually honest in describing its capabilities.

**Key strengths:**
- Clean architecture with proper layer separation
- Thorough documentation (README, project state, algorithm explanation)
- Honest description of AI capabilities — no overclaiming
- Admin recommendation explainer is excellent for thesis defense
- Proper auth flow with JWT, password reset, brute-force detection

**Key concerns:**
- SMTP credentials committed in `.env` (the `.gitignore` excludes `.env`, but the file exists in the working directory; verify it's not in git history)
- Hard-coded JWT secret fallback in `security.py`
- No file size limits on uploads
- TF-IDF cache can serve stale data when movie metadata changes without count change (documented weakness, simple fix available)
- Only ~20 seed movies limits recommendation quality for demo
- No recommendation engine end-to-end tests

---

## 2. Scores

| Metric | Score | Notes |
|--------|-------|-------|
| **Overall Project Health** | **7.5 / 10** | Well-built, good docs, some security gaps and testing holes |
| **Demo Readiness** | **7.0 / 10** | Functional but needs more movies (100+) and demo user profiles |
| **Security Readiness** | **6.0 / 10** | Adequate for academic demo; several issues for production |
| **Recommendation Engine Readiness** | **7.5 / 10** | Algorithm correct, well-documented; needs more data and e2e tests |

---

## 3. Bug Findings

| # | Severity | File | Function/Component | Root Cause | User-Visible Impact | Recommended Fix | Test Needed |
|---|----------|------|-------------------|------------|---------------------|-----------------|-------------|
| B1 | **High** | `backend/app/services/recommendation/engine.py:77` | `get_recommendations` | Loads ALL movies (`db.query(Movie).all()`) to build `movie_map`, even when only candidate-pool movies are in the TF-IDF matrix. If a movie exists outside the candidate pool but its ID appears in `scored_movies` (it won't, since `movie_ids` comes from the vectorizer), this is safe but wasteful. However, the real issue: if a movie is deleted between building the matrix and the lookup, `movie_map.get(mid)` returns `None` and the recommendation is silently dropped. | User may receive fewer than `top_n` recommendations if movies are deleted during the request. | Change to only load candidate pool movies or add padding: if `len(results) < top_n`, extend from next scored movies. | Yes — test with concurrent movie deletion |
| B2 | **Medium** | `backend/app/routers/admin_users.py:110` | `force_reset_password` | Password minimum length check is `< 6` (line 110) but the project's password complexity validator requires `>= 8` with uppercase + digit + special char. The Pydantic schema `ForceResetPasswordSchema` has `min_length=8` and its own validator, so this inline check at `< 6` is dead code that would never trigger — but it's misleading. | None (dead code), but confusing for maintenance. | Remove the inline `if len(payload.new_password) < 6` check — Pydantic already validates before the route body runs. | No |
| B3 | **Medium** | `backend/app/services/recommendation/vectorizer.py:71-79` | `_is_cache_valid` | Cache validity is checked by comparing current movie count with cached count. If movie metadata (genres, cast, keywords, overview) changes but no movies are added/deleted, the cache returns stale vectors. The `movie_service.py` correctly calls `invalidate_cache()` on create/update/delete, so this is mitigated — BUT if the admin updates a movie via a direct DB query or a migration, the cache would be stale. | Stale recommendations after metadata changes via non-service paths. | Already mitigated by `invalidate_cache()` calls in movie_service. Document that all metadata changes MUST go through the service layer. | Yes — test cache invalidation after movie update |
| B4 | **Medium** | `backend/app/services/recommendation/explainer_admin.py:201-212` | Signal 2: favorites | Favorite IDs include movies from ALL tables (not just candidates). If a user favorited a movie not in the candidate pool (e.g., a movie without video when `RECOMMEND_ONLY_UPLOADED_MOVIES=true`), the favorite still contributes to `movie_weights`, but `id_to_idx` lookup will miss it → it won't contribute to the user vector. This is actually correct behavior (matching the engine), but the explainer shows it as a signal with weight that appears unused. | Admin explainer shows favorite signals for movies not in the profile — potentially confusing in thesis defense. | Add a flag `"in_candidate_pool": mid in id_to_idx` to each signal_log entry. | Optional |
| B5 | **Low** | `frontend/src/pages/HomePage.tsx:58` | `useMovies(1, 100, filters)` | Always fetches up to 100 movies. With 100+ movies, this is fine for now but will need pagination. No loading-more mechanism exists. | All movies loaded on first page load — fine for demo, slow at scale. | Accept for now. Add pagination as future enhancement when catalog grows beyond 200. | No |
| B6 | **Low** | `backend/app/services/recommendation/engine.py:62` | `get_recommendations` | Only excludes favorited movies from recommendations. Does NOT exclude movies the user has already rated or watched. Documentation says "exclude favorited" which matches, but academically, you might want to exclude all interacted movies. | User may see movies they've already rated in recommendations. | This is a design choice, not a bug. Document it explicitly. Consider adding `exclude_rated` parameter. | Optional |
| B7 | **Low** | `backend/app/services/movie_asset_service.py:55` | `upload_video_asset` | References `video_original_filename` attribute on Movie model — this column exists in the model file but may not be in the initial Alembic baseline migration. | Could cause `OperationalError` on fresh Alembic migration if column is missing. | Verify the column exists in the baseline migration or add it. | Yes — test fresh migration |
| B8 | **Low** | `backend/app/schemas/movie.py:15-22` | `normalize_url` | Uses `_BACKEND_URL` env var for URL construction. In production behind Nginx, the frontend may need relative URLs (the user schema already uses relative paths for avatars). The two approaches are inconsistent. | Poster/video URLs might break if `BACKEND_URL` doesn't match the actual serving domain. | This is already working with the env var approach. Document the two strategies and why they differ. | No |

---

## 4. Security Findings

| # | Severity | Category | Issue | Affected File | Current Protection | Attack Scenario | Recommended Fix | Academic/Prod |
|---|----------|----------|-------|---------------|-------------------|-----------------|-----------------|---------------|
| S1 | **Critical** | Secrets | **SMTP password committed in `.env`** | `backend/.env:42` | `.gitignore` excludes `.env`, but the file exists in the working directory. If this was ever committed to git, the Gmail App Password is exposed. | Attacker with repo access can send emails as `noreply.tltn@gmail.com` or use the credential for further attacks. | 1) Verify `.env` is NOT in git history (`git log --all -- backend/.env`). 2) If found, rotate the SMTP password immediately. 3) Never store real credentials in `.env` files that may be committed. | **Both** |
| S2 | **High** | Secrets | **Hard-coded JWT secret fallback** | `backend/app/core/security.py:10` | Falls back to `"movie-rec-secret-key-change-in-production"` if `SECRET_KEY` env var is not set. | If deployed without setting `SECRET_KEY`, all JWTs are signed with a known, guessable secret. Any attacker can forge admin tokens. | Remove the default fallback — raise an error if `SECRET_KEY` is not set. Or at minimum log a CRITICAL warning. | **Both** |
| S3 | **High** | Secrets | **JWT secret in `.env` file** | `backend/.env:13` | The actual production-strength secret `LQ4EEt-umfMY...` is stored in the `.env` file. | If `.env` is leaked (accidentally committed, server compromise), all JWTs can be forged. | Ensure `.env` is never committed. Use environment-specific secrets management. | **Production** |
| S4 | **High** | Auth | **Password hash embedded in JWT** | `backend/app/routers/auth.py:343-351` | The change-password flow stores `new_hash` (bcrypt hash) inside a JWT sent via email. | The bcrypt hash is exposed in the email link URL. While bcrypt is one-way, exposing hashes is a security anti-pattern. If the email is intercepted, the attacker gets the hash. | Store the new hash server-side (e.g., in a temporary DB column or cache) and only include a reference token in the email JWT. | **Production** — acceptable for academic demo |
| S5 | **Medium** | Upload | **No file size limits** | `backend/app/services/file_storage_service.py`, `backend/app/routers/movies.py` | No `max_file_size` check on any upload endpoint (poster, backdrop, video, avatar). | Attacker can upload arbitrarily large files, exhausting disk space (DoS). A 100GB video upload would fill the server. | Add `Content-Length` checks or read-limit middleware. FastAPI's `UploadFile` doesn't enforce size by default. For academic demo: document the risk. For production: add size limits (e.g., 10MB images, 5GB videos). | **Production** — document for academic |
| S6 | **Medium** | Upload | **No filename sanitization** | `backend/app/services/file_storage_service.py:60` | Filenames are generated as `{prefix}_{timestamp}.{ext}` — this IS safe because the original filename is never used in the path. | N/A — this is actually well-handled. The original filename is stored but never used to construct file paths. | No fix needed — the current approach is secure. | N/A |
| S7 | **Medium** | Auth | **No rate limiting on login** | `backend/app/routers/auth.py:220-246` | Failed login attempts are tracked (`failed_login_attempts` counter, "suspect" status after 5 failures), but the endpoint is never throttled — requests continue at full speed. | Attacker can brute-force passwords at network speed. The "suspect" flag doesn't block login attempts. | For production: add rate limiting (e.g., `slowapi`). For academic demo: the tracking + suspect status is adequate to demonstrate awareness. | **Production** — current tracking is adequate for academic |
| S8 | **Medium** | Auth | **No token revocation / blacklist** | `backend/app/core/security.py` | Stateless JWTs — no server-side revocation. Old tokens remain valid until expiry (8 hours). | After password change or role change, old tokens still work. An attacker with a stolen token has 8 hours of access. | For production: implement a token blacklist (Redis) or reduce token lifetime + use refresh tokens. For academic: document the limitation. | **Production** — acceptable for academic |
| S9 | **Medium** | CORS | **Wildcard methods and headers** | `backend/app/main.py:88-89` | `allow_methods=["*"]`, `allow_headers=["*"]`. Origins are properly restricted. | Overly permissive — allows any HTTP method and header. In practice, this is fine since origins are restricted. | Restrict to actual methods used: `["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]` and needed headers: `["Authorization", "Content-Type"]`. | **Production** — acceptable for academic |
| S10 | **Low** | Auth | **User enumeration in registration** | `backend/app/routers/auth.py:203-207` | Returns `"Email already registered"` on duplicate email. | Attacker can enumerate valid email addresses by trying to register. | For academic demo: acceptable. For production: use a generic message like "Registration failed" or silently succeed. | **Production** |
| S11 | **Low** | Auth | **Forgot-password is properly implemented** | `backend/app/routers/auth.py:249-267` | Always returns 200 with generic message. Logs redacted. | N/A — this is correctly implemented to prevent user enumeration. | No fix needed — well done. | N/A |
| S12 | **Low** | Frontend | **Token in localStorage** | `frontend/src/services/authService.ts:34` | JWT stored in `localStorage`. | XSS vulnerability would expose the token. `httpOnly` cookies would be more secure. | For academic demo: acceptable and simpler. For production: consider `httpOnly` cookies with CSRF protection. | **Production** |
| S13 | **Low** | Video | **HLS segments publicly accessible** | `backend/app/main.py:76` | `/media` directory is mounted as static files — HLS `.ts` segments and `.m3u8` playlists are publicly accessible without auth. | Any user (even unauthenticated) can access video content by knowing the URL pattern. | For academic demo: acceptable (simplifies streaming). For production: serve HLS through an authenticated proxy. | **Production** |

---

## 5. Recommendation Engine Findings

> Detailed analysis is in [RECOMMENDATION_AUDIT.md](file:///d:/TLTN/movie-recommendation-system/docs/RECOMMENDATION_AUDIT.md).

### Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| Algorithm implementation | ✅ Matches documentation | TF-IDF + Cosine Similarity correctly implemented |
| Movie profile builder | ✅ Working | Proper weighting via text repetition, actor/director prefixes |
| User profile builder | ✅ Working | 3-signal system with MAX rule, time decay, L2 normalization |
| TF-IDF vectorizer | ✅ Working | Proper config, edge-case handling (small corpus) |
| Cache invalidation | ⚠️ Mostly working | `invalidate_cache()` called on CRUD, but count-only check has edge cases |
| Cold-start handling | ✅ Working | Falls back to recent movies from candidate pool |
| Explainer (user) | ✅ Working | Simple, honest reason strings |
| Explainer (admin) | ✅ Excellent | Full diagnostic payload — ideal for thesis defense |
| `RECOMMEND_ONLY_UPLOADED_MOVIES` | ✅ Working | Properly filters candidate pool |
| Recommendation quality | ⚠️ Limited | ~20 seed movies is too few for meaningful diversity |
| End-to-end tests | ❌ Missing | No tests for the full recommendation pipeline |
| Negative feedback | ⚠️ Not implemented | Ratings ≤ 2 are excluded (neutral), not used as negative signal |

---

## 6. Frontend Findings

| # | Severity | File | Issue | Impact | Fix |
|---|----------|------|-------|--------|-----|
| F1 | **Low** | `HomePage.tsx:58` | Fetches 100 movies in single request | Fine for demo, but no pagination | Accept for now |
| F2 | **Low** | `MovieDetailPage.tsx:137-153` | Asset fetching uses raw `fetch` instead of service layer | Inconsistent with service pattern | Move to a service function |
| F3 | **Low** | `RecommendationCard.tsx:43` | Score displayed as `"X% match"` — for cold-start (score=0), shows "0% match" | Misleading for cold-start users | Check if score is 0 and hide the badge or show "New for you" |
| F4 | **Low** | `RecsysMonitorPage.tsx` | Inline styles throughout (~200 inline style objects) | Works but not maintainable | Accept — admin-only page, not user-facing |
| F5 | **Info** | `components/ProtectedAdminRoute.tsx` | Admin route guard exists | ✅ Properly guards admin pages | No fix needed |
| F6 | **Info** | `services/authService.ts` | Token refresh flow properly implemented | ✅ Sliding session with auto-refresh | No fix needed |
| F7 | **Info** | `hooks/useAutoRefreshSession.ts` | Auto-refresh hook exists | ✅ Good UX pattern | No fix needed |

---

## 7. Backend Findings

| # | Severity | File | Issue | Impact | Fix |
|---|----------|------|-------|--------|-----|
| BE1 | **Low** | `main.py:67-76` | `os.makedirs()` at module level — creates directories on import | Works but could fail in read-only environments | Accept — standard pattern for dev |
| BE2 | **Low** | `movie_service.py:48-53` | Genre filter uses `func.lower(func.cast(..., String)).like(...)` — casts JSON to string and searches with LIKE. Works but fragile for genres containing special chars. | Edge case: genre name containing `"` could cause false matches | Accept — works for standard genre names |
| BE3 | **Info** | `auth_service.py:95-109` | `_utc_now_naive()` and `_ensure_naive()` helpers handle timezone-naive datetimes for SQLite/PostgreSQL compatibility | ✅ Good cross-DB compatibility pattern | No fix needed |
| BE4 | **Info** | `hls_service.py` | Single-worker encoding queue with process registry and cancel support | ✅ Well-implemented for academic project | No fix needed |
| BE5 | **Info** | Multiple routers | `get_current_admin_user` dependency properly checks `user.role != "admin"` | ✅ Consistent admin guard | No fix needed |

---

## 8. Database / Migration Findings

| # | Severity | File | Issue | Impact | Fix |
|---|----------|------|-------|--------|-----|
| DB1 | **Medium** | `models/movie.py:3` | Uses `sqlalchemy.dialects.postgresql.UUID` and `JSON` — these work on SQLite only because SQLAlchemy falls back to `String`/`Text`. | Technically functional but not portable — SQLite UUID is stored as string, JSON as text. | Accept — documented as SQLite=dev, PostgreSQL=prod |
| DB2 | **Low** | `models/movie.py:20` | `video_original_filename` column exists in model but may not be in Alembic baseline | Could cause migration issues on fresh install | Verify column exists in baseline migration |
| DB3 | **Low** | Alembic versions | 4 migrations in good linear chain | ✅ Clean migration history | No fix needed |
| DB4 | **Info** | `models/rating.py` (assumed) | CHECK constraint `1-5` on rating column | ✅ Proper data integrity | No fix needed |
| DB5 | **Info** | All FK models | CASCADE deletes on all foreign keys | ✅ Proper cleanup on user/movie deletion | No fix needed |

---

## 9. Testing Gaps

| Area | Current Coverage | Gap | Priority |
|------|-----------------|-----|----------|
| Auth flow | ✅ 20 tests | Good coverage | — |
| Movie CRUD | ✅ ~15 tests | Good coverage | — |
| Password validator | ✅ ~8 tests | Good coverage | — |
| User profile builder | ✅ ~10 tests | Good coverage | — |
| Watch progress | ✅ ~12 tests | Good coverage | — |
| Movie assets | ✅ 9 tests | Good coverage | — |
| Candidate filter | ✅ Tests exist | `test_candidate_filter.py` found | — |
| **Recommendation engine e2e** | ❌ No tests | Full pipeline: movies → user interactions → recommendations | **High** |
| **Recommendation explainer** | ❌ No tests | Admin explainer output correctness | **Medium** |
| **Email sending** | ❌ No tests | SMTP/template rendering | Low |
| **HLS encoding** | ❌ No tests | FFmpeg integration (hard to test) | Low |
| **Frontend components** | ❌ No test files found | React component tests | Medium |
| **API integration tests** | ⚠️ Partial | Backend tests mock DB but don't test full HTTP flow | Low |

---

## 10. Over-Engineering Analysis

> Detailed analysis in [OVER_ENGINEERING_REVIEW.md](file:///d:/TLTN/movie-recommendation-system/docs/OVER_ENGINEERING_REVIEW.md).

### Summary Classification

| Module | Verdict |
|--------|---------|
| Recommendation engine (6 files) | ✅ Core — appropriate complexity |
| Admin recommendation explainer | ✅ Core — excellent for thesis |
| Admin dashboard | ✅ Good supporting feature |
| HLS multi-quality encoding | ✅ Good supporting feature |
| Auth + JWT + password reset | ✅ Good supporting feature |
| Source/License/MovieAsset system | ⚠️ Over-engineered for academic scope |
| Security audit page | ⚠️ Nice-to-have, not core |
| 5 data importers | ⚠️ Over-engineered — only 1-2 needed |
| IP login tracking | ⚠️ Nice-to-have |
| FFmpeg processing queue | ✅ Good engineering, demonstrates systems knowledge |
| PostgreSQL + SQLite dual support | ✅ Good, demonstrates flexibility |

---

## 11. Prioritized Action Plan

### 🔴 Must Fix Before Demo

| # | Action | Files | Effort | Why |
|---|--------|-------|--------|-----|
| 1 | Verify `.env` is not in git history | `backend/.env` | 10 min | SMTP password and JWT secret exposure risk |
| 2 | Import 80-100+ movies with metadata | Scripts + seed data | 2-3 hours | ~20 movies makes recommendation demo unconvincing |
| 3 | Create 3-5 demo user profiles with diverse interactions | Manual / script | 1-2 hours | Need different user profiles to demonstrate recommendation differences |
| 4 | Fix RecommendationCard cold-start display | `RecommendationCard.tsx` | 15 min | "0% match" is misleading for cold-start |

### 🟡 Should Fix Before Submission

| # | Action | Files | Effort | Why |
|---|--------|-------|--------|-----|
| 5 | Write recommendation engine e2e tests | New test file | 2-3 hours | PROJECT_RULES requires tests; core AI feature untested |
| 6 | Remove hard-coded JWT secret fallback | `security.py` | 10 min | Security best practice |
| 7 | Add file size limits to upload endpoints | `file_storage_service.py` or middleware | 30 min | Basic security |
| 8 | Document cache invalidation strategy | `vectorizer.py` / docs | 20 min | Clarify for thesis |

### 🟢 Optional Polish

| # | Action | Files | Effort | Why |
|---|--------|-------|--------|-----|
| 9 | Remove dead code in `force_reset_password` (line 110-114) | `admin_users.py` | 5 min | Code cleanliness |
| 10 | Add `in_candidate_pool` flag to admin explainer signals | `explainer_admin.py` | 20 min | Clearer thesis demo |
| 11 | Restrict CORS methods/headers | `main.py` | 5 min | Security polish |
| 12 | Add negative feedback handling (optional) | `user_profile.py` | 1 hour | Better algorithm, but not required |

### 🔵 Future Work Only

| # | Action | Why Defer |
|---|--------|----------|
| 13 | Collaborative filtering | Complex ML, not needed for content-based thesis |
| 14 | Token revocation / blacklist | Requires Redis, overkill for demo |
| 15 | Rate limiting (slowapi) | Production concern |
| 16 | httpOnly cookie auth | Requires CSRF protection, complex |
| 17 | Authenticated HLS streaming | Requires proxy/signed URLs |
| 18 | Deep learning / neural network recommendations | Wrong scope for this project |
| 19 | Frontend pagination (infinite scroll) | Only needed at 200+ movies |
| 20 | Production security hardening | Post-graduation |

---

## 12. Commands Inspection

### Backend

| Command | Expected Result | Notes |
|---------|----------------|-------|
| `python -m pytest` | Should pass ~74+ tests | 7 test files found |
| `python -m alembic current` | Shows current migration head | 4 migrations in chain |
| `python -m alembic upgrade head` | Applies all migrations | Should work on fresh DB |
| `python -m uvicorn app.main:app --reload` | Starts backend on :8000 | Requires `.env` and dependencies |
| `python -m compileall app` | Checks for syntax errors | Should pass |

### Frontend

| Command | Expected Result | Notes |
|---------|----------------|-------|
| `npm install` | Installs dependencies | `package.json` looks clean |
| `npm run build` | Compiles TypeScript + Vite build | `tsc -b && vite build` |
| `npm run test:run` | Runs Vitest | No test files found in frontend — may report 0 tests |
| `npm run lint` | ESLint check | `eslint .` |

---

*This audit was conducted as a code review only. No application code was modified.*
