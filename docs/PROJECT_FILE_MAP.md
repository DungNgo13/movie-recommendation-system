# Project File Map

## Backend — Core

| File | Mô tả |
|------|-------|
| `backend/app/main.py` | FastAPI app entry point, router registration, CORS, static files, HLS worker |
| `backend/app/database.py` | SQLAlchemy engine, session factory, PostgreSQL/SQLite auto-detection |
| `backend/app/seed.py` | 20 sample movies for development seeding |
| `backend/app/__init__.py` | Package init |

## Backend — Models

| File | Mô tả |
|------|-------|
| `backend/app/models/user.py` | User model — email, role, login tracking, password reset |
| `backend/app/models/movie.py` | Movie model — metadata, video, source/license fields |
| `backend/app/models/rating.py` | Rating model — user×movie, 1–5 stars, CHECK constraint |
| `backend/app/models/user_favorite.py` | UserFavorite model — user×movie unique |
| `backend/app/models/watch_history.py` | WatchHistory model — progress, position, duration |
| `backend/app/models/admin_audit_log.py` | AdminAuditLog model — admin action tracking |
| `backend/app/models/movie_asset.py` | MovieAsset model — per-asset license tracking |

## Backend — Schemas (Pydantic)

| File | Mô tả |
|------|-------|
| `backend/app/schemas/user.py` | User create/response/login schemas, normalize_url helper |
| `backend/app/schemas/movie.py` | Movie CRUD schemas, quality_score computation, URL normalization |
| `backend/app/schemas/rating.py` | Rating create/response schemas |
| `backend/app/schemas/favorite.py` | Favorite toggle/response schemas |
| `backend/app/schemas/history.py` | Watch history schemas |
| `backend/app/schemas/recommendation.py` | RecommendedMovieSchema |
| `backend/app/schemas/watch_progress.py` | Watch progress save/load schemas |
| `backend/app/schemas/movie_asset.py` | MovieAsset CRUD schemas |
| `backend/app/schemas/admin.py` | Admin dashboard stats schema |

## Backend — Routers (API)

| File | Mô tả |
|------|-------|
| `backend/app/routers/auth.py` | Auth endpoints: register, login, refresh, forgot/reset password |
| `backend/app/routers/movies.py` | Movie CRUD, image/video upload, HLS processing |
| `backend/app/routers/ratings.py` | Rate movies (1–5 stars) |
| `backend/app/routers/favorites.py` | Toggle favorites, list favorites |
| `backend/app/routers/history.py` | Record and list watch history |
| `backend/app/routers/watch_progress.py` | Save/load video playback position |
| `backend/app/routers/recommendations.py` | GET /me — personalized recommendations |
| `backend/app/routers/users.py` | User profile, avatar upload |
| `backend/app/routers/admin_users.py` | Admin user management |
| `backend/app/routers/admin_dashboard.py` | Admin dashboard statistics |
| `backend/app/routers/admin_logs.py` | Admin audit log viewer |
| `backend/app/routers/admin_recommendations.py` | Admin recommendation explainer |
| `backend/app/routers/movie_assets.py` | Per-asset license CRUD |

## Backend — Services

| File | Mô tả |
|------|-------|
| `backend/app/services/auth_service.py` | Registration, login, password reset logic, IP tracking |
| `backend/app/services/movie_service.py` | Movie CRUD business logic |
| `backend/app/services/rating_service.py` | Rating create/read logic |
| `backend/app/services/favorite_service.py` | Favorite toggle, list, get IDs |
| `backend/app/services/history_service.py` | Watch history recording and listing |
| `backend/app/services/mail_service.py` | SMTP email sending (welcome, reset, confirm) |
| `backend/app/services/hls_service.py` | FFmpeg HLS multi-quality encoding worker |
| `backend/app/services/avatar_service.py` | Avatar image upload and storage |
| `backend/app/services/file_storage_service.py` | Generic file storage (poster, backdrop) |
| `backend/app/services/admin_service.py` | Audit log writing |
| `backend/app/services/asset_license_service.py` | MovieAsset CRUD logic |
| `backend/app/services/license_checker.py` | License validation and status checking |
| `backend/app/services/movie_asset_service.py` | MovieAsset query helpers |

## Backend — ★ AI Recommendation Engine

| File | Mô tả |
|------|-------|
| `backend/app/services/recommendation/engine.py` | Main orchestrator — cosine similarity scoring, cold-start fallback |
| `backend/app/services/recommendation/movie_profile.py` | Build text corpus from movie metadata (title, overview, genres, cast, keywords, director) |
| `backend/app/services/recommendation/user_profile.py` | Build user preference vector from ratings, favorites, watch history |
| `backend/app/services/recommendation/vectorizer.py` | TF-IDF vectorizer with in-memory cache |
| `backend/app/services/recommendation/explainer.py` | Generate short human-readable recommendation reasons |
| `backend/app/services/recommendation/explainer_admin.py` | Full diagnostic explainer for admin/thesis defense |

## Backend — Core / Security

| File | Mô tả |
|------|-------|
| `backend/app/core/security.py` | JWT creation/decoding, bcrypt hash/verify, token helpers |
| `backend/app/core/password_validator.py` | Password strength validation rules |

## Backend — Scripts & Data

| File | Mô tả |
|------|-------|
| `backend/scripts/importers/import_movielens.py` | MovieLens dataset importer (metadata only, no media) |
| `backend/scripts/importers/import_wikidata.py` | Wikidata movie metadata importer |
| `backend/scripts/importers/import_wikimedia_commons.py` | Wikimedia Commons image importer (license-filtered) |
| `backend/scripts/importers/import_loc_public_domain.py` | Library of Congress public domain film importer |
| `backend/scripts/importers/import_stock_assets.py` | Stock photo placeholder importer |
| `backend/scripts/public_domain_movies.json` | ~10 public domain movie records for seeding |
| `backend/scripts/migrate_sqlite_to_pg.py` | SQLite → PostgreSQL data migration script |

## Backend — Migrations (Alembic)

| File | Mô tả |
|------|-------|
| `backend/alembic/versions/1780d0eefc59_initial_baseline.py` | Initial schema baseline |
| `backend/alembic/versions/87079e588ea0_add_cascade_deletes_and_indexes.py` | CASCADE deletes, indexes |
| `backend/alembic/versions/c3a1f7e9d042_add_source_license_fields.py` | Add source/license columns to movies |
| `backend/alembic/versions/d4b2e8f1a053_create_movie_assets_table.py` | Create movie_assets table |

## Backend — Tests

| File | Mô tả |
|------|-------|
| `backend/tests/test_auth.py` | 20 tests: login, JWT, IP tracking, password reset, welcome email |
| `backend/tests/test_movie_assets.py` | 9 tests: asset CRUD, license checker, media rights |
| `backend/tests/test_movies.py` | ~15 tests: movie CRUD, upload, validation |
| `backend/tests/test_password_validator.py` | ~8 tests: password strength rules |
| `backend/tests/test_user_profile.py` | ~10 tests: user profile builder, signal weights |
| `backend/tests/test_watch_progress.py` | ~12 tests: watch progress save/load |

## Frontend — Entry

| File | Mô tả |
|------|-------|
| `frontend/src/main.tsx` | React DOM root entry point |
| `frontend/src/App.tsx` | Router setup, Navbar, route definitions |
| `frontend/src/App.css` | Global styles (OKLCH design system, ~2250 lines) |
| `frontend/src/index.css` | CSS reset and base variables |
| `frontend/src/config.ts` | API_BASE_URL configuration |

## Frontend — Pages

| File | Mô tả |
|------|-------|
| `frontend/src/pages/HomePage.tsx` | Movie listing with search, filter, sort, recommendations |
| `frontend/src/pages/MovieDetailPage.tsx` | Movie detail, rating, favorite, HLS player, recommendations |
| `frontend/src/pages/FavoritesPage.tsx` | User favorites list |
| `frontend/src/pages/LoginPage.tsx` | Login form |
| `frontend/src/pages/RegisterPage.tsx` | Registration form |
| `frontend/src/pages/ForgotPasswordPage.tsx` | Forgot password form |
| `frontend/src/pages/ResetPasswordPage.tsx` | Reset password form |
| `frontend/src/pages/ProfilePage.tsx` | User profile, avatar upload, change password |
| `frontend/src/pages/ConfirmPasswordChangePage.tsx` | Password change confirmation |
| `frontend/src/pages/AdminMoviesPage.tsx` | Admin movie CRUD with modal form |
| `frontend/src/pages/AdminUsersPage.tsx` | Admin user management |
| `frontend/src/pages/AdminDashboardPage.tsx` | Admin statistics dashboard |
| `frontend/src/pages/AdminAuditLogsPage.tsx` | Admin audit log viewer |
| `frontend/src/pages/RecsysMonitorPage.tsx` | Admin recommendation algorithm monitor |
| `frontend/src/pages/AdminSecurityAuditPage.tsx` | Admin security audit |

## Frontend — Components

| File | Mô tả |
|------|-------|
| `frontend/src/components/Navbar.tsx` | Top navigation bar with auth state |
| `frontend/src/components/MovieCard.tsx` | Movie card (poster, title, year) |
| `frontend/src/components/RecommendationCard.tsx` | Recommendation card (score + reason) |
| `frontend/src/components/StarRating.tsx` | Star rating UI (1–5) |
| `frontend/src/components/HlsPlayer.tsx` | HLS.js video player with quality switching |
| `frontend/src/components/SourceAttribution.tsx` | Source/license display component |
| `frontend/src/components/ProtectedAdminRoute.tsx` | Admin route guard |
| `frontend/src/components/AvatarUpload.tsx` | Avatar upload widget |
| `frontend/src/components/ChangePasswordForm.tsx` | Password change form |
| `frontend/src/components/PasswordStrengthIndicator.tsx` | Password strength meter |
| `frontend/src/components/SkeletonCard.tsx` | Loading skeleton card |
| `frontend/src/components/LoadingSpinner.tsx` | Loading spinner |
| `frontend/src/components/ErrorMessage.tsx` | Error display |
| `frontend/src/components/admin/MovieForm.tsx` | Admin movie create/edit form |
| `frontend/src/components/admin/MovieTable.tsx` | Admin movie table |

## Frontend — Services

| File | Mô tả |
|------|-------|
| `frontend/src/services/authService.ts` | Login, register, JWT storage, token refresh |
| `frontend/src/services/movieService.ts` | Movie CRUD, upload, video processing API calls |
| `frontend/src/services/recommendationService.ts` | Fetch personalized recommendations |
| `frontend/src/services/ratingService.ts` | Rate movies API calls |
| `frontend/src/services/favoriteService.ts` | Toggle favorites API calls |
| `frontend/src/services/continueWatchingService.ts` | Watch progress save/load |
| `frontend/src/services/adminService.ts` | Admin user management API calls |
| `frontend/src/services/recsysService.ts` | Admin recommendation explainer API calls |

## Frontend — Models & Hooks

| File | Mô tả |
|------|-------|
| `frontend/src/models/types.ts` | TypeScript interfaces: Movie, MovieListItem, PaginatedMovies, MovieAsset |
| `frontend/src/models/index.ts` | Re-exports from types.ts |
| `frontend/src/hooks/useAutoRefreshSession.ts` | Auto JWT refresh hook |

## Documentation

| File | Mô tả |
|------|-------|
| `docs/CURRENT_PROJECT_STATE.md` | Full Vietnamese project report |
| `docs/PROJECT_EXPORT_FOR_CHATGPT.md` | Compact context for AI assistants |
| `docs/PROJECT_FILE_MAP.md` | This file |
| `docs/RECOMMENDATION_ENGINE_EXPLAINED.md` | Detailed AI algorithm explanation |
| `docs/LEGAL_SOURCES.md` | Legal source guidelines |
| `docs/deployment.md` | Deployment guide |
| `docs/streaming_architecture.md` | HLS streaming architecture |
| `docs/workflow.md` | Development workflow |
| `PROJECT_RULES.md` | Project development rules |
| `README.md` | Project README |
