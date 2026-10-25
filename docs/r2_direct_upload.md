# Cloudflare R2 Direct Upload — Backend Contract (Phase 1.5)

| Field | Value |
|---|---|
| Status | Backend implemented and unit/integration tested with **mocked R2** |
| Live R2 verification | **NOT VERIFIED** (no live R2 operation has been performed) |
| PostgreSQL runtime validation | **NOT VERIFIED** (no disposable PostgreSQL available; see §6) |
| Migrations | `f7c3d9a1b2e4` (published in `5aaa604`) → `a1e5c7b9d3f2` (cleanup tracking, head) |

## 1. Flow

```mermaid
sequenceDiagram
  participant B as Admin browser
  participant API as FastAPI
  participant R2 as R2 (private bucket)
  participant DB as Database
  B->>API: POST /api/v1/admin/movies/{movie_id}/uploads {filename, content_type, size}
  API->>DB: upload_sessions (pending, server-generated object_key)
  API-->>B: 201 {session, upload_url, upload_method: PUT, upload_headers, expires_in_seconds}
  B->>R2: PUT upload_url (body = file, header Content-Type exactly as given)
  B->>API: POST /api/v1/admin/movies/{movie_id}/uploads/{session_id}/complete
  API->>R2: HeadObject (only while session is pending)
  API->>DB: session=completed; movies.source_storage='r2', source_object_key
  API-->>B: 200 session
```

## 2. Endpoints (admin JWT required)

### `POST /api/v1/admin/movies/{movie_id}/uploads` → `201`

Request:

```json
{ "filename": "movie.mp4", "content_type": "video/mp4", "size": 123456789 }
```

* `content_type` allow-list: `video/mp4`, `video/x-matroska`, `video/webm`, `video/quicktime`, `video/x-msvideo`.
* `size` > 0 and ≤ `R2_MAX_UPLOAD_BYTES` (hard cap 5 000 000 000 bytes, single PUT).

Response:

```json
{
  "session": { "id": "…", "movie_id": "…", "status": "pending", "original_filename": "movie.mp4",
               "content_type": "video/mp4", "expected_size": 123456789, "actual_size": null,
               "error": null, "created_at": "…", "expires_at": "…", "completed_at": null },
  "upload_url": "https://<account>.r2.cloudflarestorage.com/<bucket>/sources/…?X-Amz-…",
  "upload_method": "PUT",
  "upload_headers": { "Content-Type": "video/mp4" },
  "expires_in_seconds": 900
}
```

> [!IMPORTANT]
> `upload_url` is a short-lived secret capability. The frontend must use it once, must send
> **exactly** `upload_headers` (Content-Type is signed), and must never log or persist it.

| Status | Meaning |
|---|---|
| 400 | Declared size exceeds the limit |
| 401 / 403 | Not authenticated / not admin |
| 404 | Movie not found |
| 422 | Invalid filename, content type or size |
| 502 | URL could not be signed |
| 503 | R2 not configured |

### `POST /api/v1/admin/movies/{movie_id}/uploads/{session_id}/complete` → `200`

Returns the session (same schema as above). Idempotent.

| Session state / condition | Result |
|---|---|
| `completed` | `200`, recorded result; **no R2 call** (works even if R2 is down or unconfigured) |
| `pending`, object verified | `200`, session → `completed`, movie → `source_storage='r2'` |
| `pending`, object not uploaded yet, URL still valid | `409`, stays `pending` (retry after PUT finishes) |
| `pending`, object missing and URL expired | `409 "Upload session expired"`, → `expired` |
| `pending`, size/type mismatch | `422`, → `failed` |
| `failed` / `expired` | `409` |
| R2 error (after bounded retries) | `502`, stays `pending` |
| `pending` and R2 not configured | `503`, stays `pending` |
| Not the session creator | `403` (also for completed sessions) |
| Wrong movie id / unknown session | `404` |

Concurrent completions are serialized by a conditional `UPDATE … WHERE status='pending'`;
exactly one request performs the transition and writes the audit log.

## 3. Source consistency rules

| Event | `source_storage` | `source_object_key` | `video_source_path` / HLS fields |
|---|---|---|---|
| Local upload succeeds | `local` | cleared | replaced (existing behaviour) |
| Local upload fails | unchanged | unchanged | unchanged |
| R2 completion succeeds | `r2` | verified key | **unchanged** (HLS still uses local source until the R2 resolver exists) |
| R2 completion fails | unchanged | unchanged | unchanged |

`source_storage` / `source_object_key` are not part of any public schema and the bucket stays private.

## 4. Session state machine

```text
pending ──verified──────────────────▶ completed  (never cleaned up)
   ├────size/type mismatch──────────▶ failed
   ├────missing after URL expiry────▶ expired
   └────cleanup: expiry + grace─────▶ expired
failed / expired ──cleanup --execute──▶ object_deleted_at set
```

## 5. Opt-in cleanup of abandoned uploads

Nothing is deleted automatically. Run manually from `backend/`:

```bash
python scripts/cleanup_r2_uploads.py              # DRY-RUN (default): report only, no R2 calls
python scripts/cleanup_r2_uploads.py --execute    # delete eligible objects
python scripts/cleanup_r2_uploads.py --grace-hours 48 --limit 50
```

Eligible: `failed`, `expired`, and `pending` sessions whose URL expired more than the grace period
(default 24 h) ago, with `object_deleted_at IS NULL`. An object is deleted only if its key lies in
the session's own namespace `sources/movie_<movie_id>/<session_id>/` **and** no movie references it.
Transient R2 errors are retried up to 3 attempts (0.5 s, 1 s back-off); persistent errors leave the
session for the next run. `--execute` refuses to run without R2 configuration.

### Storage cost and orphan-object limitations

* Objects of `failed`/`expired` sessions keep consuming R2 storage until cleanup is run.
* Objects uploaded for a session that later becomes **superseded** (a newer completed R2 upload or a
  local upload replaced it) are **not** cleaned up — completed sessions are never touched.
  Removing superseded sources needs a separate, reviewed policy.
* Objects uploaded without any session (e.g. manual uploads in the dashboard) are invisible to cleanup.
* A size limit is enforced only at completion (Content-Length is not part of the signature), so an
  oversized object can exist in the bucket until its session is cleaned up.
* An R2 lifecycle rule on the `sources/` prefix can act as a backstop, but it would also delete
  in-use sources unless restricted carefully — **do not enable without review**.

## 6. Migrations `f7c3d9a1b2e4` → `a1e5c7b9d3f2`

Both purely additive.

* `f7c3d9a1b2e4` (already committed/pushed in `5aaa604` — not edited):
  `movies.source_storage VARCHAR(10) NOT NULL DEFAULT 'local'`, `movies.source_object_key VARCHAR(512)`,
  table `upload_sessions` with FKs (`movie_id` → `movies` ON DELETE CASCADE,
  `created_by_user_id` → `users` ON DELETE SET NULL), `UNIQUE(object_key)`, index `(movie_id, status)`.
* `a1e5c7b9d3f2`: `upload_sessions.object_deleted_at`, index `(status, expires_at)`.

Validate on a **disposable** PostgreSQL before production:

```bash
python scripts/validate_migration_pg.py --url postgresql://…/throwaway_db --confirm-disposable
```

The script refuses non-PostgreSQL URLs, the configured `DATABASE_URL`, and non-empty databases.

> [!WARNING]
> The repository's baseline migration (`1780d0eefc59`) only ALTERs existing tables, so
> `alembic upgrade head` cannot bootstrap an empty database. The validator therefore creates the
> pre-migration schema from the models and stamps `e5f3a1b2c7d8`.

Production steps (owner action): backup → `alembic upgrade head --sql` review → `alembic upgrade head`.

## 7. Configuration

See `backend/.env.example` (`R2_ENDPOINT`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY`, `R2_PRESIGN_EXPIRES_SECONDS`, `R2_MAX_UPLOAD_BYTES`).
Bucket CORS (owner action, Cloudflare dashboard): allow frontend origins, method `PUT`,
header `Content-Type`, expose `ETag`.

## 8. Not yet implemented

* React direct-upload UI (progress, cancel, completion call).
* FFmpeg R2 source resolver (`download_to_path` exists but is not wired into `hls_service`).
* Multipart upload for files > 5 GB.
* Cleanup of superseded completed sources.
