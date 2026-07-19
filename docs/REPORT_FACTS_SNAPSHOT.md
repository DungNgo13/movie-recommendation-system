# Report Facts Snapshot

> **Purpose:** Concise factual snapshot for use while writing the academic report. Contains only verified facts.

---

## 1. Audited Revision

| Item | Value |
|------|-------|
| Audit date | 2026-07-19 |
| Branch | `main` |
| Commit | `26614863ca9b0a52e5419eff40978215f9d63c4e` |
| Short hash | `2661486` |
| Repository | `https://github.com/DungNgo13/movie-recommendation-system` |
| Working tree | Clean |
| Last commit message | `feat: implement localization for HomePage and add corresponding test suite` |
| Last commit date | 2026-07-18 14:17:27 +0700 |

---

## 2. Project Purpose

An academic movie recommendation website demonstrating:
- Full-stack web development (React + FastAPI)
- Content-based recommendation using TF-IDF + Cosine Similarity
- HLS multi-quality video streaming via FFmpeg
- Bilingual interface (Vietnamese / English)
- User authentication and admin management

**NOT:** Collaborative filtering. **NOT:** Deep learning. **NOT:** Commercial product.

---

## 3. Technology Stack

| Layer | Technology | Source |
|-------|-----------|--------|
| Frontend | React 18 + TypeScript + Vite | `package.json`, `main.tsx` |
| Styling | Vanilla CSS with OKLCH color system | `App.css` (58 KB) |
| i18n | react-i18next (5 namespaces × 2 languages) | `i18n/index.ts` |
| Backend | FastAPI (Python) | `main.py` |
| ORM | SQLAlchemy | `database.py` |
| Migrations | Alembic (5 migrations) | `alembic/versions/` |
| Auth | JWT (python-jose) + bcrypt | `core/security.py` |
| AI/ML | scikit-learn (TfidfVectorizer, cosine_similarity) | `recommendation/vectorizer.py` |
| Video | FFmpeg → HLS multi-quality encoding | `services/hls_service.py` |
| Player | hls.js + Plyr | `components/HlsPlayer.tsx` |
| Dev DB | SQLite | `database.py` default |
| Prod DB | PostgreSQL | `database.py` env-driven |
| Email | smtplib + Jinja2 templates | `services/mail_service.py` |
| Deployment | Ubuntu + Nginx + Uvicorn + Cloudflare | `docs/deployment.md` |

---

## 4. System Architecture

```
Frontend (React + TypeScript + Vite)
  ↓ HTTP/HTTPS
Backend API (FastAPI)
  ├── Recommendation Engine (TF-IDF + Cosine Similarity)
  ├── Database (SQLite dev / PostgreSQL prod)
  ├── FFmpeg HLS Processing (async queue)
  └── Email Service (SMTP)
  ↓
Nginx / Cloudflare (production reverse proxy)
```

Source: `main.py`, `docs/deployment.md`, code inspection.

---

## 5. Main Frontend Modules

| Module | Files | Purpose |
|--------|-------|---------|
| Pages | 17 files in `pages/` | Home, MovieDetail, Favorites, Login, Register, ForgotPassword, ResetPassword, Profile, ConfirmPasswordChange, 6 Admin pages |
| Components | 21 files + 2 admin | Navbar, MovieCard, RecommendationCard, ContinueWatchingCard, HlsPlayer, StarRating, ThemeSelector, LanguageSelector, etc. |
| Services | 11 files | authService, movieService, recommendationService, continueWatchingService, favoriteService, ratingService, adminService, recsysService |
| Hooks | 7 files | useAuth, useAutoRefreshSession, useFavorites, useMovies, useTheme |
| Theme | 5 files | ThemeProvider, themeContext, themeStorage + tests |
| i18n | 3 files + 10 locale JSONs | i18n config, languageStorage + tests, EN/VI locale files |
| Utils | 7 files | localizedMovie, recommendationReason, movieFilters, passwordValidator, avatarUrl + tests |
| Models | 2 files | TypeScript interfaces (Movie, MovieListItem, PaginatedMovies, MovieAsset) |

Source: `frontend/src/` directory listing.

---

## 6. Main Backend Modules

| Module | Files | Purpose |
|--------|-------|---------|
| Routers | 14 files | auth, movies, ratings, favorites, history, watch_progress, recommendations, users, admin_users, admin_dashboard, admin_logs, admin_recommendations, movie_assets |
| Services | 16 files | auth, movie, rating, favorite, history, hls, avatar, file_storage, admin, asset_license, license_checker, movie_asset, mail, keyword_label_helpers |
| Recommendation | 6 files | engine, movie_profile, user_profile, vectorizer, explainer, explainer_admin |
| Models | 7 files | User, Movie, Rating, UserFavorite, WatchHistory, AdminAuditLog, MovieAsset |
| Schemas | 9 files | user, movie, rating, favorite, history, recommendation, watch_progress, movie_asset, admin |
| Core | 2 files | security (JWT + bcrypt), password_validator |

Source: `backend/app/` directory listing.

---

## 7. Database Tables and Important Fields

| Table | Key Fields | Source |
|-------|-----------|--------|
| `users` | id (UUID), email, password_hash, role, status, last_login_ip, failed_login_attempts, avatar_path, password_reset_token/expires | `models/user.py` |
| `movies` | id (UUID), title, overview, genres (JSON), cast (JSON), keywords (JSON), director, poster_path, backdrop_path, video_source_path, hls_playlist_path, processing_status, available_qualities, title_vi, overview_vi, keyword_labels_vi (JSON), source_name, source_url, license_type, is_public_domain, media_rights_status | `models/movie.py` |
| `ratings` | id (UUID), user_id (FK), movie_id (FK), rating (1–5 CHECK) | `models/rating.py` |
| `user_favorites` | id (UUID), user_id (FK), movie_id (FK), UNIQUE(user_id, movie_id) | `models/user_favorite.py` |
| `watch_histories` | id (UUID), user_id (FK), movie_id (FK), progress_percent, playback_position_seconds, duration_seconds, watched_at, is_completed | `models/watch_history.py` |
| `admin_audit_logs` | id (UUID), admin_id (FK), action, target_type, target_id, created_at | `models/admin_audit_log.py` |
| `movie_assets` | id (UUID), movie_id (FK), asset_type, url, source_name, license_type, is_public_domain, media_rights_status | `models/movie_asset.py` |

Source: Model files, verified against Alembic migrations.

---

## 8. API Groups

| Group | Prefix | Auth Required | Admin Required |
|-------|--------|:---:|:---:|
| Auth | `/api/v1/auth` | Varies | No |
| Movies | `/api/v1/movies` | No (list/detail), Yes (create/update/delete) | Yes (CUD) |
| Ratings | `/api/v1/ratings` | Yes | No |
| Favorites | `/api/v1/favorites` | Yes | No |
| History | `/api/v1/history` | Yes | No |
| Watch Progress | `/api/v1/watch-progress` | Yes | No |
| Recommendations | `/api/v1/recommendations` | Yes | No |
| Users | `/api/v1/users` | Yes | No |
| Admin Users | `/api/v1/admin/users` | Yes | Yes |
| Admin Dashboard | `/api/v1/admin/dashboard` | Yes | Yes |
| Admin Logs | `/api/v1/admin/logs` | Yes | Yes |
| Admin Recommendations | `/api/v1/admin/recommendations` | Yes | Yes |
| Movie Assets | `/api/v1/movie-assets` | Yes | Yes |

Source: Router files, prefix and dependency inspection.

---

## 9. Recommendation Algorithm

**Type:** Content-Based Filtering
**Technique:** TF-IDF Vectorization + Cosine Similarity
**Library:** scikit-learn (`TfidfVectorizer`, `cosine_similarity`)

### Pipeline:
1. Build movie text profile from metadata (English only)
2. Fit TF-IDF vectorizer on movie corpus
3. Build user preference vector from weighted interactions
4. Compute cosine similarity between user vector and all movie vectors
5. Exclude favorited movies
6. Sort by score descending, take top-N
7. Generate human-readable reason

Source: `recommendation/engine.py`, `recommendation/movie_profile.py`, `recommendation/user_profile.py`, `recommendation/vectorizer.py`, `recommendation/explainer.py`.

---

## 10. Exact Recommendation Weights

### Rating Weights
| Rating | Weight | Source |
|:---:|:---:|---|
| 5★ | 5.0 | `user_profile.py:67` |
| 4★ | 3.0 | `user_profile.py:66` |
| 3★ | 1.0 | `user_profile.py:65` |
| 2★ | 0.0 (excluded) | `user_profile.py:64` |
| 1★ | 0.0 (excluded) | `user_profile.py:63` |

### Other Signal Weights
| Signal | Weight | Source |
|--------|:---:|---|
| Favorite | 3.0 | `user_profile.py:57` |
| Watch min (0% progress) | 1.0 | `user_profile.py:58` |
| Watch max (100% progress) | 3.0 | `user_profile.py:59` |
| Time decay rate | 0.05 | `user_profile.py:72` |

### Watch Weight Formula
```
base = 1.0 + (progress_percent / 100) × 2.0
decay = 1.0 / (1.0 + days_since × 0.05)
watch_weight = min(base × decay, 3.0)
```
Source: `user_profile.py:77-110`

### Signal Combination
- **Method:** MAX (not additive)
- **Rationale:** Prevents single movie from dominating profile via double-counting
- Source: `user_profile.py:148-150`

### User Vector Construction
```
user_vector = Σ(weight_i × movie_vector_i) / Σ(weight_i)
user_vector = L2_normalize(user_vector)
```
Source: `user_profile.py:182-198`

---

## 11. Exact TF-IDF Configuration

| Parameter | Value | Source |
|-----------|:---:|---|
| max_features | 5000 | `vectorizer.py:102` |
| stop_words | "english" | `vectorizer.py:103` |
| ngram_range | (1, 2) | `vectorizer.py:104` |
| min_df | 1 | `vectorizer.py:105` |
| max_df | 0.95 (or 1.0 if corpus < 2 docs) | `vectorizer.py:109` |

### Movie Profile Field Repetition
| Field | Repetition | Prefix | Source |
|-------|:---:|---|---|
| title | ×2 | none | `movie_profile.py:33-35` |
| overview | ×1 | none | `movie_profile.py:39` |
| genres | ×1 | none | `movie_profile.py:44-45` |
| cast | ×1 | "actor " | `movie_profile.py:50-51` |
| keywords | ×2 | none (lowercased) | `movie_profile.py:55-58` |
| director | ×1 | "director " | `movie_profile.py:62-63` |
| title_vi | NOT USED | — | Verified by test + code |
| overview_vi | NOT USED | — | Verified by test + code |
| keyword_labels_vi | NOT USED | — | Verified by test + code |

---

## 12. Candidate-Pool Behavior

| Config Flag | Value | Behavior | Source |
|-------------|:---:|---|---|
| `RECOMMEND_ONLY_UPLOADED_MOVIES` | `true` (default) | Only movies with `video_source_path IS NOT NULL` OR `hls_playlist_path IS NOT NULL` OR `processing_status = "ready"` | `vectorizer.py:36-58` |
| `RECOMMEND_ONLY_UPLOADED_MOVIES` | `false` | All movies in catalog | `vectorizer.py:48-49` |

**Test evidence:** `test_candidate_filter.py` — 7 tests covering all combinations. Source: `backend/tests/test_candidate_filter.py`.

---

## 13. Cold-Start Behavior

| Aspect | Behavior | Source |
|--------|----------|--------|
| Trigger | `build_user_profile()` returns `None` (no interactions) | `engine.py:47-49` |
| Fallback | Recent movies from candidate pool, `ORDER BY release_date DESC` | `engine.py:105-131` |
| Score | 0.0 | `engine.py:128` |
| Reason | "Popular movie — rate or favorite some movies for personalized picks!" | `engine.py:129` |
| Respects filter | Yes (uses `_candidate_query`) | `engine.py:111` |

**Test evidence:** 4 tests in `TestColdStart` class. Source: `backend/tests/test_recommendation_engine.py`.

---

## 14. HLS Architecture and Supported Qualities

### Processing Architecture
- Async queue-based encoding (`asyncio.Queue`)
- Single FFmpeg process at a time (prevents CPU exhaustion)
- Encoding worker runs as background task via FastAPI lifespan
- Source: `hls_service.py:30-72`, `main.py:39-60`

### Quality Ladder
- Determined by source video resolution (detected via FFprobe)
- Does not upscale — only encodes at or below source resolution
- Master playlist with RESOLUTION entries
- `available_qualities` stored as comma-separated string (e.g., "360p,720p,1080p")
- Source: `hls_service.py`, `models/movie.py:27`

### Frontend Player
- hls.js for HLS parsing + Plyr for UI controls
- Quality switching via `hls.currentLevel` (no video.src replacement)
- Cache-bust on master playlist URL
- Source: `components/HlsPlayer.tsx`

---

## 15. Authentication and Authorization

| Feature | Implementation | Source |
|---------|---------------|--------|
| Password hashing | bcrypt | `core/security.py:25-26` |
| JWT algorithm | HS256 | `core/security.py:18` |
| Token expiry | 480 min (8 hours, configurable) | `core/security.py:20-22` |
| Secret management | Environment variable, no fallback, crashes if missing | `core/security.py:11-17` |
| Password validation | Min 8 chars, uppercase, digit, special char | `core/password_validator.py` |
| Reset tokens | Short-lived JWT (15 min), stored hash in DB | `core/security.py:51-57` |
| Failed login tracking | Counter + "suspect" status at 5 failures | `models/user.py:27` |
| Admin authorization | Role check in routers + frontend ProtectedAdminRoute | `routers/admin_users.py`, `components/ProtectedAdminRoute.tsx` |
| Token refresh | Silent refresh via useAutoRefreshSession hook | `hooks/useAutoRefreshSession.ts` |

---

## 16. User-Facing Features

| Feature | Status | Source |
|---------|:---:|---|
| Movie listing with search/filter/sort | ✅ | `HomePage.tsx` |
| Movie detail with metadata | ✅ | `MovieDetailPage.tsx` |
| HLS video player | ✅ | `HlsPlayer.tsx` |
| Star rating (1-5) | ✅ | `StarRating.tsx` |
| Favorites | ✅ | `FavoriteHeart.test.tsx`, `favoriteService.ts` |
| Continue Watching (auth) | ✅ | `continueWatchingService.ts` |
| Continue Watching (guest) | ✅ | `continueWatchingService.ts` (localStorage) |
| Personalized recommendations | ✅ | `recommendationService.ts` |
| Metadata discovery | ✅ | `MovieDetailPage.tsx`, `movieService.ts` |
| Bilingual interface | ✅ (partial — admin nav English-only) | `i18n/`, locale files |
| Theme system | ✅ | `theme/ThemeProvider.tsx` |
| Registration/Login | ✅ | `LoginPage.tsx`, `RegisterPage.tsx` |
| Password reset | ✅ | `ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx` |
| Profile/Avatar | ✅ | `ProfilePage.tsx`, `AvatarUpload.tsx` |

---

## 17. Admin Features

| Feature | Status | Source |
|---------|:---:|---|
| Dashboard statistics | ✅ | `AdminDashboardPage.tsx` |
| Movie CRUD | ✅ | `AdminMoviesPage.tsx`, `MovieForm.tsx`, `MovieTable.tsx` |
| Video upload + HLS processing | ✅ | `AdminMoviesPage.tsx`, `hls_service.py` |
| User management | ✅ | `AdminUsersPage.tsx` |
| Audit logs | ✅ | `AdminAuditLogsPage.tsx` |
| Security audit | ✅ | `AdminSecurityAuditPage.tsx` |
| Recommendation monitor | ✅ | `RecsysMonitorPage.tsx` |
| Vietnamese metadata editing | ✅ | `MovieForm.tsx` |

---

## 18. Bilingual and Theme Behavior

### Language
| Aspect | Value | Source |
|--------|-------|--------|
| Languages | Vietnamese (vi), English (en) | `i18n/index.ts` |
| Default language | Vietnamese | `languageStorage.ts:18` |
| Storage key | `movie-app-language` | `languageStorage.ts:3` |
| Namespaces | common, auth, movies, admin, recommendation | `i18n/index.ts:43` |
| `<html lang>` update | Yes, on language change | `i18n/index.ts:50-52` |

### Theme
| Aspect | Value | Source |
|--------|-------|--------|
| Modes | Light, Dark, System | `themeStorage.ts:12` |
| Default mode | System | `themeStorage.ts:38` |
| Storage key | `movie-app-theme` | `themeStorage.ts:19` |
| DOM attributes | `data-theme`, `color-scheme` | `themeStorage.ts:83-85` |
| OS preference follow | Only in System mode | `ThemeProvider.tsx:35-52` |

---

## 19. Testing Evidence

### Frontend
| Metric | Value | Source |
|--------|:---:|---|
| Test files | 14 | `npm run test:run` output |
| Tests | 271 | `npm run test:run` output |
| Pass rate | 100% | `npm run test:run` output |
| Framework | Vitest | `package.json` |
| ESLint errors | 0 | `npm run lint` output |
| npm audit | 0 vulnerabilities | `npm audit` output |

### Backend
| Metric | Value | Source |
|--------|:---:|---|
| Test files | 12 | `pytest tests/ -v` output |
| Tests | 176 | `pytest tests/ -v` output |
| Pass rate | 100% | `pytest tests/ -v` output |
| Warnings | 1 (httpx deprecation) | `pytest tests/ -v` output |
| Framework | pytest | `requirements.txt` |
| Test database | SQLite in-memory | Test fixture inspection |

---

## 20. Deployment Evidence

| Aspect | Status | Source |
|--------|:---:|---|
| Deployment docs | ✅ Present | `docs/deployment.md` |
| Nginx config | ✅ Documented | `docs/deployment.md` |
| systemd service | ✅ Documented | `docs/deployment.md` |
| Production URL | `https://tltn.laetus.io.vn` | Documented |
| Production API | `https://api.laetus.io.vn/api/v1` | `frontend/.env.production` |
| Production DB | PostgreSQL | `docs/deployment.md` |
| Production verification | NOT TESTED | No server access from audit environment |

---

## 21. Dataset/Catalog Statistics

| Metric | Value | Source |
|--------|:---:|---|
| Seed movies | 20 | `seed.py` documentation |
| Development database | SQLite (`test.db`) | `database.py` default |
| Production database | PostgreSQL | `docs/deployment.md` |

> **Note:** Actual catalog statistics from the production database were NOT obtained during this audit (no production database access).

---

## 22. Source and License Approach

- Each movie has: `source_name`, `source_url`, `license_type`, `license_url`, `attribution`, `is_public_domain`, `media_rights_status`
- Per-asset tracking via `movie_assets` table
- `media_rights_status` enum: `safe_to_use`, `attribution_required`, `non_commercial_only`, `unknown`, `blocked`
- SourceAttribution component displays per-movie info on MovieDetailPage
- **MISSING:** Global non-commercial/academic disclaimer footer

Source: `models/movie.py:34-44`, `components/SourceAttribution.tsx`.

---

## 23. Verified Limitations

1. **Content-based only** — no collaborative filtering, no user-user similarity
2. **No negative feedback** — ratings 1-2★ are excluded, not used as negative signals
3. **English-only TF-IDF** — stop words only support English
4. **Simple cache** — invalidates on CRUD but not on HLS completion
5. **Filter bubble risk** — only recommends similar content
6. **Small catalog** — ~20 seed movies (production catalog size unknown)
7. **No evaluation metrics** — no precision/recall/NDCG calculations exist
8. **Single JS bundle** — no code splitting (1 MB uncompressed)
9. **Focused accessibility** — NOT a formal WCAG audit
10. **Admin nav English-only** — bilingual coverage incomplete

---

## 24. Claims That Must NOT Be Made

| ❌ Incorrect Claim | ✅ Correct Statement |
|---|---|
| Collaborative filtering | Content-based filtering only |
| Deep learning / neural network | TF-IDF + Cosine Similarity (classical NLP) |
| High recommendation accuracy | No formal evaluation metrics calculated |
| Full production security | Academic-level security review only |
| Copyright ownership of media | Third-party content rights remain with owners |
| WCAG compliant | Focused accessibility review performed |
| 4K video support | Depends on source video resolution; not verified |
| Guest history merge | Implementation not verified in this audit |
| Complete bilingual support | Admin navigation links remain English-only |

---

## 25. Remaining Work Before Report Writing

| Priority | Task | Finding ID |
|:---:|---|---|
| 1 | Create SiteFooter with bilingual non-commercial disclaimer | AUD-DOC-001 |
| 2 | Move Navbar hard-coded strings to i18n | AUD-I18N-001 |
| 3 | Fix HLS cache invalidation gap | AUD-REC-001 |
| 4 | Update PROJECT_FILE_MAP.md with new files | AUD-DOC-002 |
| 5 | Rewrite streaming_architecture.md | AUD-DOC-003 |
| 6 | Translate RecommendationCard aria-labels | AUD-I18N-002 |
| 7 | Document cache limitations clearly in report | AUD-REC-002 |
