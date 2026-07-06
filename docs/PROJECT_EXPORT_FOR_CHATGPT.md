# Movie Recommendation System — Context for AI Assistant

## Project Summary
AI-based Movie Recommendation Website using Content-Based Filtering (TF-IDF + Cosine Similarity). React+TypeScript frontend, FastAPI+Python backend, PostgreSQL database.

## Tech Stack
- Frontend: React 18 + TypeScript + Vite, vanilla CSS (OKLCH), react-router-dom, hls.js
- Backend: FastAPI, SQLAlchemy, Alembic, scikit-learn, NumPy, SciPy, bcrypt, python-jose (JWT)
- Database: PostgreSQL (prod) / SQLite (dev)
- Deployment: Ubuntu + Nginx + Uvicorn

## AI Recommendation Algorithm (ACTUAL CODE)

### Algorithm: TF-IDF Content-Based Filtering + Cosine Similarity

**Pipeline:**
1. `movie_profile.py` → builds text string per movie: `{title×2} {overview} {genres} {actor names} {keywords×2} {director}`
2. `vectorizer.py` → `TfidfVectorizer(max_features=5000, stop_words="english", ngram_range=(1,2))` → sparse matrix
3. `user_profile.py` → builds user preference vector from 3 signals:
   - Ratings: 5★=5.0, 4★=3.0, 3★=1.0, 2★/1★=excluded
   - Favorites: weight=3.0
   - Watch history: `(1.0 + progress%/100 × 2.0) × time_decay` capped at 3.0
   - Per-movie: takes MAX weight across signals (no double-counting)
   - Final: weighted average of movie vectors → L2 normalized
4. `engine.py` → `cosine_similarity(user_vector, movie_matrix)` → rank → exclude favorited → top-N
5. Cold-start: returns recent movies when user has no interactions

**Key files:** `backend/app/services/recommendation/` (6 files)
**API:** `GET /api/v1/recommendations/me?top_n=10` (auth required)
**Admin explainer:** `GET /api/v1/admin/recommendations/explain/{user_id}` (admin only)

## Database Models

### users
id(UUID), email(unique), password_hash, role("user"/"admin"), status, created_at, last_login_ip, last_login_at, failed_login_attempts, password_reset_token, password_reset_expires, avatar_path

### movies
id(UUID), title(indexed), overview, release_date, genres(JSON), cast(JSON), keywords(JSON), director, poster_path, backdrop_path, video_source_path, processing_status, processing_progress, hls_playlist_path, available_qualities, source_name, source_url, license_type, license_url, attribution, is_public_domain, media_rights_status

### ratings
id(UUID), user_id(FK→users CASCADE), movie_id(FK→movies CASCADE), rating(1-5 CHECK), created_at, updated_at. UNIQUE(user_id, movie_id)

### user_favorites
id(UUID), user_id(FK→users CASCADE), movie_id(FK→movies CASCADE), created_at. UNIQUE(user_id, movie_id)

### watch_history
id(UUID), user_id(FK→users CASCADE), movie_id(FK→movies CASCADE), watched_at, progress_percent(0-100), playback_position_seconds, duration_seconds, is_completed. UNIQUE(user_id, movie_id)

### admin_audit_logs
id(UUID), admin_user_email, action_type, target_type, target_id, description, created_at

### movie_assets
id(UUID), movie_id(FK→movies CASCADE), asset_type, url, local_path, source_name, source_url, license_type, license_url, attribution, is_public_domain, media_rights_status, created_at

## API Endpoints

### Auth (`/api/v1/auth`)
- POST `/register` — create account + welcome email
- POST `/login` — JWT token + IP tracking
- POST `/refresh` — refresh JWT
- POST `/forgot-password` — send reset email
- POST `/reset-password` — change password via token
- PUT `/change-password` — change password (auth)
- PUT `/change-email` — change email (auth)

### Movies (`/api/v1/movies`)
- GET `/` — paginated list with filters
- GET `/{id}` — movie detail
- POST `/` — create (admin)
- PUT `/{id}` — update (admin)
- DELETE `/{id}` — delete (admin)
- POST `/{id}/upload-poster` — upload poster (admin)
- POST `/{id}/upload-backdrop` — upload backdrop (admin)
- POST `/{id}/upload-video` — upload video (admin)
- POST `/{id}/process-video` — start HLS encoding (admin)
- GET `/{id}/processing-status` — encoding status

### Ratings (`/api/v1/ratings`)
- POST `/` — rate movie (auth)
- GET `/movie/{id}` — get user's rating

### Favorites (`/api/v1/favorites`)
- POST `/toggle` — toggle favorite (auth)
- GET `/` — list favorites (auth)
- GET `/ids` — get favorite IDs (auth)

### Watch History (`/api/v1/history`)
- POST `/` — record watch (auth)
- GET `/` — list history (auth)

### Watch Progress (`/api/v1/watch-progress`)
- PUT `/{movie_id}` — save position (auth)
- GET `/{movie_id}` — load position (auth)

### Recommendations (`/api/v1/recommendations`)
- GET `/me` — personalized recommendations (auth)

### Admin
- GET `/api/v1/admin/dashboard/stats` — statistics
- GET/POST/PUT/DELETE `/api/v1/admin/users` — user management
- GET `/api/v1/admin/logs` — audit logs
- GET `/api/v1/admin/recommendations/explain/{user_id}` — algorithm explainer

### Users (`/api/v1/users`)
- GET `/me` — current user profile
- POST `/me/avatar` — upload avatar

### Assets (`/api/v1/movies/{id}/assets`)
- GET `/` — list assets
- POST `/` — create asset (admin)
- DELETE `/{asset_id}` — delete asset (admin)

## Frontend Structure
- Pages: HomePage, MovieDetailPage, FavoritesPage, LoginPage, RegisterPage, ForgotPasswordPage, ResetPasswordPage, ProfilePage, AdminMoviesPage, AdminUsersPage, AdminDashboardPage, AdminAuditLogsPage, RecsysMonitorPage, AdminSecurityAuditPage
- Key components: Navbar, MovieCard, RecommendationCard, StarRating, HlsPlayer, SourceAttribution, admin/MovieForm, admin/MovieTable

## Source/License System Status
- Backend: fully implemented (MovieAsset model, CRUD API, license_checker)
- Frontend: hidden from admin form by default, only 3 fields in collapsed "Advanced" section
- Assessment: NOT required for academic scope, documented as future production feature

## Tests
- 6 test files, ~74 tests total (pytest)
- Covers: auth, movie assets, movies CRUD, password validation, user profile, watch progress
- Not covered: recommendation engine e2e, email sending, HLS encoding

## Current Status & Next Steps
1. Import more movies (100+) for better recommendation quality
2. Create test user profiles for thesis demo
3. Write recommendation engine e2e tests
4. Prepare RecsysMonitor demo for defense
5. Replace TMDB poster URLs with public domain images
