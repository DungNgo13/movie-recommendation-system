# MovSug — Comprehensive Technical Audit (Master Report)

| Field | Value |
|---|---|
| Audit date | 2026-10-25 |
| Auditor role | Senior Software Architect · AI/ML Engineer · DevSecOps · Technical Auditor |
| Repository | `movie-recommendation-system` (DungNgo13) |
| Branch / commit | `main` / `d276c547bf4756811165641fa0a63320da9b6f19` |
| Working tree | Clean before and after (only `docs/audit/*` added by this audit, uncommitted) |
| Scope | Full repository; local dev environment; no production, DB server or R2 access |
| Mode | **Read-only audit.** No application code, configuration, schema, credential or cloud resource was changed. |

## Document set

| Document | Content |
|---|---|
| [ARCHITECTURE_CURRENT.md](ARCHITECTURE_CURRENT.md) | Phase A — repository inventory, versions, architecture diagram |
| [FEATURE_STATUS_MATRIX.md](FEATURE_STATUS_MATRIX.md) | Feature status, Phase D database audit, Phase K gap table |
| [RECOMMENDATION_ENGINE_AUDIT.md](RECOMMENDATION_ENGINE_AUDIT.md) | Phase E (high priority) |
| [R2_UPLOAD_GAP_ANALYSIS.md](R2_UPLOAD_GAP_ANALYSIS.md) | Phase F (high priority) + Phase G FFmpeg/HLS |
| [SECURITY_AND_TESTING_AUDIT.md](SECURITY_AND_TESTING_AUDIT.md) | Phase H security + Phase I testing, executed results, Test Center proposal |
| [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) | Phase L roadmap, 7-day plan |
| this file | Phase B backend, Phase C frontend, Phase J deployment, executive summary |

---

## Phase B — Backend audit

### B.1 Subsystem findings

| Subsystem | Current implementation | Files | Test evidence | Problems / debt | Recommendation |
|---|---|---|---|---|---|
| Entry point | Lifespan starts encoding worker; static mounts; CORS | [main.py](file:///d:/TLTN/movie-recommendation-system/backend/app/main.py) | indirectly via TestClient | Creates dirs at import (side effect); `/media` exposes source videos; no health endpoint | Add `/healthz` (DB + disk + ffmpeg); restrict static scope |
| Routers | 13 routers, consistent `/api/v1` prefix | `routers/*` | most have tests | Business logic in routers: status mutation in [movies.py L233-237](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/movies.py#L233-L237), direct DB writes in [admin_users.py L60-119](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/admin_users.py#L60-L119) — contradicts `PROJECT_RULES.md` "router only handles request/response" | Move into services when touched |
| Service layer | Clear per-domain modules | `services/*` | good coverage | Duplicates: `explainer_admin` re-implements profile building; `record_watch` vs `save_watch_progress` ([history_service.py L12-108](file:///d:/TLTN/movie-recommendation-system/backend/app/services/history_service.py#L12-L108)); `avatar_service` duplicates file validation | Consolidate opportunistically |
| Dependency injection | `Depends(get_db)`, `get_current_user`, `get_current_admin_user` | [database.py L28-33](file:///d:/TLTN/movie-recommendation-system/backend/app/database.py#L28-L33), [auth.py L43-91](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/auth.py#L43-L91) | overridden in tests | Background worker and cancel path create their own `SessionLocal()` (acceptable) | — |
| Pydantic schemas | v2, `from_attributes`, computed URL fields | `schemas/*` | `test_normalize_url.py` | Some endpoints lack `response_model` (`/status`, `/process-hls`, admin explain) — undocumented OpenAPI shapes | Add response models |
| SQLAlchemy models | 7 models, UUID PKs, cascades | `models/*` | via API tests | `postgresql.UUID/JSON` types used on SQLite in tests; no timestamps on movies | See DB audit |
| Session lifecycle | request-scoped generator | database.py | — | HLS progress commits from executor thread on its own session (OK); long FFmpeg holds a session open for the whole encode | Acceptable at current scale |
| AuthN / JWT | HS256, `sub`=user id, 8 h default (`.env.example` 1440 min), sliding refresh | [security.py](file:///d:/TLTN/movie-recommendation-system/backend/app/core/security.py) | `test_auth.py` | No `typ`, no revocation, status not enforced (S3–S5) | See security audit |
| AuthZ | role string `admin`/`user` | auth.py L81-91 | admin overrides in tests | No admin-router tests | Add negative tests (403) |
| File upload | Local disk, MIME prefix check, 5 GB chunked size check | [file_storage_service.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/file_storage_service.py) | `test_upload_limits.py`, `test_movies.py` | Reads entire stream twice (validate then copy); second-resolution filenames; extension fallback (S8) | Replace video path with R2 direct upload |
| Error handling | `HTTPException`; generic 500 in reset flow | routers | partial | Raw exception text stored in `processing_error` and exposed (S6); admin explain maps service errors to 500 | Map to typed errors |
| Logging | `logging.getLogger` per module; no config | — | — | No request IDs, no structured logs, FFmpeg command logged at INFO (paths only) | Configure logging (JSON) in main |
| Background jobs | asyncio queue + thread executor, single FFmpeg | [hls_service.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py) | mocked | Not persistent; H1 deadlock; H2 cancel→ready | See R2/HLS doc |
| Configuration | `os.getenv` scattered; `load_dotenv()` in 3 modules | main.py, security.py, mail_service.py | — | No central settings object; R2 vars undocumented | Pydantic `BaseSettings` (optional) |
| API docs | FastAPI auto OpenAPI | — | — | Title "Mov-Sug API" v0.1.0; docs endpoints exposed in production (not verified) | Consider disabling `/docs` in prod |

### B.2 Inconsistent API conventions

- Two watch endpoints families (`/history` and `/watch-progress`) writing the same table with different semantics.
- Status codes: `POST /history/{id}` → 201 on upsert; `POST /watch-progress` → 200 on upsert.
- Upload audit text says "triggered HLS processing" but processing is manual ([movies.py L192](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/movies.py#L192)).
- `GET /movies/{id}/status` is public while all other processing endpoints are admin-only.

---

## Phase C — Frontend audit

| Area | Finding | Evidence | Risk |
|---|---|---|---|
| Routing | 16 routes; admin routes behind `ProtectedAdminRoute` (client-side; backend enforces too) | [App.tsx L34-53](file:///d:/TLTN/movie-recommendation-system/frontend/src/App.tsx#L34-L53) | Low |
| API integration | Central `API_BASE_URL`; per-domain service modules; consistent `detail` error extraction | [config.ts](file:///d:/TLTN/movie-recommendation-system/frontend/src/config.ts), `services/*` | Low |
| Auth handling | JWT in `localStorage`; sliding refresh hook; `fetchCurrentUser` clears token on failure | [authService.ts](file:///d:/TLTN/movie-recommendation-system/frontend/src/services/authService.ts) | Medium (XSS token theft) |
| State management | React context + hooks (`useAuth`, `useFavorites`, `useMovies`, theme) — no global store | `hooks/*` | Low |
| Movie management UI | `MovieForm.tsx` (657 lines) + `MovieTable.tsx`; table tested, form untested | `components/admin/*` | Medium (complex, untested upload/poll logic) |
| Upload component | XHR with progress; file `accept` list; no cancel path; no client-side size check | [movieService.ts L115-158](file:///d:/TLTN/movie-recommendation-system/frontend/src/services/movieService.ts#L115-L158), [MovieForm.tsx L274, L627](file:///d:/TLTN/movie-recommendation-system/frontend/src/components/admin/MovieForm.tsx#L274) | Medium |
| Processing progress | `setInterval` polling of `/status` in `MovieForm`, `AdminMoviesPage`, `MovieCard` | MovieForm.tsx L233, AdminMoviesPage.tsx L60, MovieCard.tsx L28 | Low (three pollers, duplicated logic) |
| Error handling | Loading/error components present; services throw `Error(detail)` | `ErrorMessage.tsx`, `LoadingSpinner.tsx` | Low |
| Video player | hls.js + Plyr; dynamic quality list; ABR badge sync with loop guard; fatal error recovery; Safari native fallback (no quality menu) | [HlsPlayer.tsx L71-255](file:///d:/TLTN/movie-recommendation-system/frontend/src/components/HlsPlayer.tsx#L71-L255) | Low; NETWORK_ERROR retries without backoff (L236-239) |
| HLS quality switching | `hls.currentLevel` set from Plyr `onChange` | L123-161 | Untested |
| i18n | i18next, `en`/`vi`, 5 namespaces each | `i18n/locales/*` | Low |
| Responsive design | CSS in `index.css`/`App.css`; not measured | — | UV |
| Tests | 17 files / 323 tests pass; lint clean | executed | — |

Integration risks for R2: the upload service must switch from multipart-to-API to `PUT` to a presigned URL with exact `Content-Type`; R2 returns no JSON body, so success must be confirmed by the new `/complete` call. Dead-code analysis was **not** exhaustive (UV).

---

## Phase J — Deployment & infrastructure audit

| Topic | Finding | Status |
|---|---|---|
| Ubuntu + systemd + Uvicorn | Single process on 127.0.0.1:8000 documented | Documented only — NOT VERIFIED |
| Nginx | Config only in docs; `/media` proxied to Uvicorn in deployment.md vs `alias` in streaming doc | Conflicting docs — NOT VERIFIED |
| Cloudflare Tunnel | Mentioned in prior audit; no config in repo | NOT VERIFIED |
| HTTPS | Let's Encrypt in docs; Cloudflare edge TLS likely in reality | NOT VERIFIED |
| PostgreSQL | Supported via `DATABASE_URL`; migration script SQLite→PG exists; all tests run on SQLite only | PG behaviour untested (e.g. NULL ordering R3) |
| Static assets | Vite `dist` served by Nginx | NOT VERIFIED |
| Video distribution | HLS from local disk through FastAPI StaticFiles or Nginx; no CDN caching rules versioned | NOT VERIFIED |
| Upload size | Nginx 2G vs app 5 GB vs Cloudflare plan limit (100 MB Free/Pro per Cloudflare docs) | Mismatch — confirmed in docs; runtime NOT VERIFIED |
| Env variables | `.env.example` complete except R2; frontend `.env.production` tracked (public URL only) | Confirmed |
| Background workers | In-process; lost on restart | Confirmed |
| Backups | None documented (DB, media) | Gap |
| Logs | journald only (docs) | Gap: no rotation/structured logs |
| Health checks | None beyond `/` | Gap |
| CI/CD | None | Gap |
| Domain drift | `laetus.io.vn`, `tltn.laetus.io.vn`, `api.laetus.io.vn` used inconsistently across docs/env | Confirmed (docs) |

Operational risks (ordered): source-video exposure (S1) · upload failures above Cloudflare limit · stuck encodes after restart (H1) · disk growth (sources never offloaded) · no backups · single-process coupling of API and FFmpeg CPU load.

---

## Executive summary

### 1. What is already working?
Authentication (register/login/JWT/reset/password change), catalog CRUD with search/filters and Vietnamese display metadata, favorites/ratings/watch-progress, local poster/backdrop/video upload with progress, single-worker FFmpeg multi-bitrate HLS with progress and cancel, hls.js + Plyr playback with quality menu, English/Vietnamese UI, admin dashboard/logs/security pages, and a TF-IDF content-based recommender with weighted user profiles. **Verified locally: 210 backend tests and 323 frontend tests pass; ESLint clean.**

### 2. What is partially implemented?
Negative feedback (ignored, with a leak), seen-item exclusion (favorites only), cold start (release-date fallback mislabelled "popular"), explanations (generic/ungrounded), upload cancellation (no UI path), job recovery (none after restart), account-status enforcement, R2 (connectivity script only), deployment documentation (conflicting).

### 3. What is completely missing?
R2 presign/upload/completion/DB sync/FFmpeg integration; upload-session schema; offline evaluation dataset, metrics and reports; MMR; embeddings; hybrid; latency measurement; CI/CD; coverage; E2E/load/security testing; rate limiting; health checks; backups; consolidated test reporting.

### 4. Current R2 integration status
Only [check_r2.py](file:///d:/TLTN/movie-recommendation-system/backend/scripts/check_r2.py) (`head_bucket`). `boto3` not declared or installed; `R2_*` variables absent from `.env`, `.env.example` and the shell. Owner's `200` result is accepted as external evidence but **not reproducible from the repo**. No direct-upload flow exists.

### 5. Current recommendation engine status
Working, tested TF-IDF + cosine baseline over a ~16-movie candidate pool, with defects R1 (rated/watched items re-recommended), R2 (disliked-but-watched counts positive), R3 (cold-start ordering differs SQLite vs PG). No evaluation infrastructure; local data (5 users, 2 ratings) cannot support metrics — an offline MovieLens-based harness is required.

### 6. Existing tests
pytest (14 modules, 210 tests, in-memory SQLite, mocked SMTP/FFmpeg) and Vitest (17 files, 323 tests). No coverage, CI, Playwright, k6, ZAP, Allure, static Python analysis, or recommendation evaluation.

### 7. Most important security risks
S1 public source-video download · S2 no rate limiting/lockout · S3 account status not enforced · S4 JWT purpose confusion/replay with password hash in emailed token · S5 no revocation + localStorage token · S6 internal error disclosure.

### 8. Top five technical priorities
1. R2 direct upload MVP (presign → verify → DB → FFmpeg) with tests.
2. Freeze and make the TF-IDF baseline reproducible (pinned deps, shared scorer).
3. Offline evaluation harness + dataset + metrics + reports.
4. Fix R1/R2 and measure v1.0 vs v1.1; then cold-start + MMR.
5. CI + isolated test config + security quick wins (S1, S3, S4, S6) and HLS H1/H2.

### 9. What should be implemented first?
Week 1: R2 storage service + `upload_sessions` + presign/complete endpoints with mocked-R2 tests, in parallel with CI and the baseline freeze (see [IMPLEMENTATION_ROADMAP.md §3](IMPLEMENTATION_ROADMAP.md)).

### 10. Assumptions requiring verification
- R2 credentials, write permission, bucket CORS, and token scope (owner environment).
- Production topology: Cloudflare Tunnel vs Nginx TLS, Cloudflare plan body-size limit, Uvicorn worker count, Nginx `/media` handling, security headers.
- Production PostgreSQL version, schema at Alembic head, and interaction data volume.
- Production dependency versions (requirements unpinned).
- Real FFmpeg behaviour (GOP alignment, ABR switching quality) on the production host.
- Whether source videos are actually reachable publicly in production (S1).

---

## Audit actions log (for traceability)

| Action | Side effects |
|---|---|
| `git branch/rev-parse/status/log`, `git ls-files`, `git check-ignore` | none |
| `.env` inspection — key names + set/empty only | none (values never displayed) |
| Read-only SQLite stats (`mode=ro`) on `backend/test.db` | none |
| pytest ×2 from scratch CWD, cache/bytecode disabled | test upload files written to scratch dir only |
| `npm run test:run`, `npx --no-install eslint .`, `npm audit --json` | possible Vitest cache in `node_modules/.vite`; audit queried npm registry (read-only) |
| Created `docs/audit/*.md` (7 files) | documentation only, not committed |
| Not performed | installs, migrations, deployments, R2 calls, network scans, FFmpeg encodes, code changes |

> [!IMPORTANT]
> **Implementation has not started.** Please review these findings — in particular the R2 design (§7 of the R2 document), the proposed schema, and the baseline-freeze approach — before any application-code changes are made.
