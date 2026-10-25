# MovSug — Cloudflare R2 Upload & FFmpeg/HLS Gap Analysis (HIGH PRIORITY)

| Field | Value |
|---|---|
| Audit date | 2026-10-25 |
| Commit | `d276c547bf4756811165641fa0a63320da9b6f19` |
| Scope | Repo-wide search for R2/S3/boto3/presign/Cloudflare; `check_r2.py`; upload, storage and HLS code paths; deployment docs |
| Owner-provided evidence | Bucket `movsug-media-test`, public access disabled, `check_r2.py` printed `R2 connection OK: 200`, bucket empty at screenshot time |

---

## 1. Bottom line

> [!IMPORTANT]
> **Only an R2 connectivity check exists.** There is no presigned-URL endpoint, no upload-session model, no frontend direct upload, no completion verification, no DB synchronisation and no FFmpeg integration with R2. The current video pipeline is 100 % local-disk.

Repo-wide search (`r2`, `R2_`, `boto3`, `presign`, `generate_presigned`, `s3`, `cloudflare`) matches **only** [check_r2.py](file:///d:/TLTN/movie-recommendation-system/backend/scripts/check_r2.py) plus prose in older docs.

---

## 2. What `check_r2.py` actually does

[check_r2.py L1-20](file:///d:/TLTN/movie-recommendation-system/backend/scripts/check_r2.py#L1-L20):

| Aspect | Observation |
|---|---|
| Client | `boto3.client("s3", endpoint_url=R2_ENDPOINT, region_name="auto", signature_version="s3v4")` — correct R2 pattern |
| Credentials | `os.environ[...]` for `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` (hard `KeyError` if missing) |
| Operation | `head_bucket` only — proves credentials + bucket reachability, nothing about write permission, CORS, or presigning |
| Secrets | Not printed (only HTTP status) ✔ |

Configuration evidence in this workspace:

| Check | Result |
|---|---|
| `boto3` in `requirements.txt` | **Absent** |
| `boto3` installed in any local venv | **No** (`.venv`, `backend/.venv`, `backend/venv`) |
| `R2_*` keys in `backend/.env` | **Absent** (key names inspected, values never read) |
| `R2_*` in OS environment of this shell | **Absent** |
| `R2_*` documented in `.env.example` | **Absent** |

**Conclusion:** the owner's `R2 connection OK: 200` was produced in a different environment (another machine or shell with exported variables). It is accepted as owner evidence but is **NOT VERIFIED** in this workspace and is **not reproducible from the repository** as committed.

---

## 3. Current upload flow (strictly from code)

```mermaid
sequenceDiagram
  participant A as Admin browser (MovieForm)
  participant N as Nginx / Cloudflare (NOT VERIFIED)
  participant API as FastAPI
  participant FS as Local disk media/
  participant DB as DB
  participant W as encoding_worker (in-process)
  A->>N: POST /api/v1/movies/{id}/video (multipart, XHR progress)
  N->>API: proxied body (limit 2G per docs; Cloudflare plan limit applies)
  API->>API: MIME starts with video/ ; size ≤ 5 GB (reads whole stream once)
  API->>FS: write media/videos/source/movie_{id}/source_{ts}.{ext}
  API->>FS: delete previous source + previous HLS folder
  API->>DB: video_source_path, status="uploaded"
  A->>API: POST /movies/{id}/process-hls
  API->>DB: status="processing"
  API->>W: encode_queue.put(movie_id)
  W->>FS: ffprobe + ffmpeg → media/videos/hls/movie_{id}/master.m3u8
  W->>DB: status="ready", hls_playlist_path, available_qualities
  A->>API: GET /movies/{id}/status (polling, unauthenticated)
```

Evidence: [movieService.ts L115-158](file:///d:/TLTN/movie-recommendation-system/frontend/src/services/movieService.ts#L115-L158), [movies.py L172-255](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/movies.py#L172-L255), [movie_asset_service.py L30-64](file:///d:/TLTN/movie-recommendation-system/backend/app/services/movie_asset_service.py#L30-L64), [file_storage_service.py L80-124](file:///d:/TLTN/movie-recommendation-system/backend/app/services/file_storage_service.py#L80-L124), [hls_service.py L406-552](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L406-L552).

> [!WARNING]
> Cloudflare's proxy enforces a maximum request body size per plan (100 MB on Free/Pro per Cloudflare documentation). If production traffic goes through a Cloudflare Tunnel/proxy, **video uploads above that size through the current API endpoint will fail**. This is the strongest operational argument for direct-to-R2 upload. Plan and actual limit: **NOT VERIFIED**.

---

## 4. Step-by-step R2 gap matrix

| # | Step | Status | Evidence / Gap |
|---|---|---|---|
| 1 | boto3 S3-compatible client | **Partial** | Only in `check_r2.py`; no reusable `storage` service; boto3 not declared |
| 2 | Endpoint & region config | **Partial** | Correct in script; not part of app config |
| 3 | Bucket configuration | **Blocked by config** | Bucket exists (owner); name not in `.env.example` |
| 4 | Credential loading | **Partial** | Script uses `os.environ`; no validation/startup check in app; no least-privilege token scope documented |
| 5 | Presigned PUT generation | **Missing** | No `generate_presigned_url` anywhere |
| 6 | AuthN/AuthZ for presign | **Missing** | Must reuse `get_current_admin_user` ([auth.py L81-91](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/auth.py#L81-L91)) |
| 7 | File type validation | **Partial (local only)** | `video/*` MIME prefix only ([file_storage_service.py L93](file:///d:/TLTN/movie-recommendation-system/backend/app/services/file_storage_service.py#L93)); no allow-list, no magic bytes, no ffprobe validation |
| 8 | Upload size validation | **Partial (local only)** | 5 GB server-side read ([L13, L40-77](file:///d:/TLTN/movie-recommendation-system/backend/app/services/file_storage_service.py#L40-L77)); for presigned PUT the size must be declared up front and re-checked on completion via `HeadObject` |
| 9 | Unique object key generation | **Missing** | Local naming is second-resolution timestamp `source_{YYYYmmdd_HHMMSS}` ([L103-106](file:///d:/TLTN/movie-recommendation-system/backend/app/services/file_storage_service.py#L103-L106)) — collision-prone; R2 needs `sources/{movie_id}/{session_uuid}/{safe_name}` |
| 10 | Direct browser upload | **Missing** | Frontend posts multipart to API |
| 11 | R2 bucket CORS | **Missing / NOT VERIFIED** | Browser PUT needs bucket CORS for frontend origins, `PUT`, `Content-Type`, expose `ETag` |
| 12 | Upload progress | **Implemented (local)** | XHR `upload.progress` ([movieService.ts L127-133](file:///d:/TLTN/movie-recommendation-system/frontend/src/services/movieService.ts#L127-L133)) — reusable for presigned PUT |
| 13 | Upload cancellation | **Partial** | `abort` listener exists (L152) but the XHR object is never exposed; no cancel button path |
| 14 | Completion verification | **Missing** | No `HeadObject` size/type/ETag check |
| 15 | DB synchronisation | **Missing** | `Movie` has only `video_source_path` (String 255); no storage backend / object key / size / checksum |
| 16 | Idempotent completion | **Missing** | No session state machine |
| 17 | Error recovery / retry | **Missing** | No session expiry, no orphan cleanup |
| 18 | Temp file cleanup | **N/A today**, required for R2-source encode (download to temp → encode → delete) |
| 19 | Ownership verification | **Missing** | No `owner_user_id` on any upload record |
| 20 | Audit logging | **Implemented (local)** | `create_audit_log` on upload (description inaccurately says "triggered HLS processing" — [movies.py L192](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/movies.py#L192)) |
| 21 | Tests | **Missing** | No mocked-S3 tests (e.g. botocore `Stubber` or moto) |

---

## 5. Database support for direct upload

Current relevant columns: [movie.py L19-27](file:///d:/TLTN/movie-recommendation-system/backend/app/models/movie.py#L19-L27) (`video_source_path`, `video_original_filename`, `processing_status`, `processing_progress`, `processing_step`, `hls_playlist_path`, `processing_error`, `available_qualities`) and [movie_asset.py](file:///d:/TLTN/movie-recommendation-system/backend/app/models/movie_asset.py#L29-L62) (licence metadata, `url`, `local_path`; no size/checksum/status).

| Requirement | Supported? | Missing |
|---|---|---|
| Direct R2 upload sessions | No | `upload_sessions` table |
| Completion verification | No | `expected_size`, `content_type`, `etag`, `verified_at` |
| Unique R2 object keys | No | `object_key` with UNIQUE constraint |
| Upload ownership | No | `created_by_user_id` FK |
| Idempotent completion | No | `status` enum + unique `(id)` transition guard; completion returns same result if already `completed` |
| Video processing jobs | Partial | job state lives on `movies` row; no `processing_jobs` table, no attempt counter, no `started_at/finished_at` |
| Recovery from failed uploads | No | `expires_at`, `failed_reason`, cleanup job |
| Coexistence local + R2 | No | `movies.source_storage` (`local`/`r2`) + `movies.source_object_key` |

Proposed minimal schema (for review only — **no migration created**):

```text
upload_sessions
  id UUID PK
  movie_id UUID FK movies(id) ON DELETE CASCADE
  created_by_user_id UUID FK users(id)
  object_key VARCHAR(512) UNIQUE NOT NULL
  original_filename VARCHAR(255)
  content_type VARCHAR(100) NOT NULL
  expected_size BIGINT NOT NULL
  status VARCHAR(20) NOT NULL  -- pending | uploaded | completed | failed | expired | aborted
  etag VARCHAR(128) NULL
  actual_size BIGINT NULL
  error TEXT NULL
  created_at, expires_at, completed_at TIMESTAMP
  INDEX (movie_id, status)

movies (+ columns)
  source_storage VARCHAR(10) NOT NULL DEFAULT 'local'   -- local | r2
  source_object_key VARCHAR(512) NULL
```

---

## 6. FFmpeg / HLS pipeline audit (Phase G)

| Question | Answer (evidence) |
|---|---|
| Where are source videos stored? | `media/videos/source/movie_{id}/source_{ts}.{ext}` on local disk ([file_storage_service.py L105-111](file:///d:/TLTN/movie-recommendation-system/backend/app/services/file_storage_service.py#L105-L111)) |
| How do uploads reach the backend? | Multipart POST through API ([movies.py L172-194](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/movies.py#L172-L194)) |
| How are jobs created? | Manual `POST /process-hls` → `encode_queue.put_nowait` ([movies.py L198-255](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/movies.py#L198-L255), [hls_service.py L60-72](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L60-L72)) |
| Inside or outside API process? | **Inside** — asyncio task started in lifespan, FFmpeg run via `run_in_executor` thread ([main.py L51-60](file:///d:/TLTN/movie-recommendation-system/backend/app/main.py#L51-L60), [hls_service.py L80-110](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L80-L110)) |
| Queue persistence? | **None** — `asyncio.Queue` in memory ([L57](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L57)) |
| FFprobe usage | 3 separate calls: duration, dimensions, audio presence ([L114-172](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L114-L172)) |
| Quality selection | No-upscale ladder 360p→2160p by source height ([L231-268](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L231-L268)) |
| HLS generation | Single-pass multi-variant with `var_stream_map`, 10 s segments, `master.m3u8`; fallback single 480p ([L271-386](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L271-L386)) |
| HLS storage | `media/videos/hls/movie_{id}/` local disk ([L438](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L438)) |
| Serving | FastAPI `StaticFiles` at `/media` ([main.py L76](file:///d:/TLTN/movie-recommendation-system/backend/app/main.py#L76)); Nginx proxies or aliases — docs conflict, **NOT VERIFIED** |
| Progress reporting | `-progress pipe:2`, parsed `out_time_us`, committed to DB, polled via `/status` ([L209-221](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L209-L221)) |
| Failure handling | Status `failed` + last 600 chars of stderr ([L523-529](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L523-L529)) |
| R2 sources supported? | **No** — `os.path.exists(source_path)` required ([L418-424](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L418-L424)) |
| Interruption recovery? | **No** (see H1) |
| Local + R2 coexistence? | Not today; feasible with a source-resolver (see §7) |

### Pipeline defects found

| ID | Finding | Severity | Evidence |
|---|---|---|---|
| H1 | **Stuck-job deadlock after restart**: `/process-hls` sets `processing` *before* enqueue; queue is lost on restart; afterwards `/process-hls` returns 409 (already processing) and `/cancel-encode` returns 409 (no active process). Only re-uploading the video resets status. | High | [movies.py L219-237](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/movies.py#L219-L237), [hls_service.py L566-569](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L566-L569) |
| H2 | **Cancel marks movie `ready`** although the previous HLS directory was already deleted at encode start (L439-447) → `hls_playlist_path` may point to a deleted folder; movie stays in the recommendation pool. | Medium | [hls_service.py L584](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L584) |
| H3 | Previous playable HLS output is destroyed before the new encode succeeds (no blue/green output dir). | Medium | [L439-447](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L439-L447) |
| H4 | No GOP/keyframe alignment (`-g`, `-keyint_min`, `-sc_threshold 0` or `-force_key_frames`), no `-preset`, no `maxrate/bufsize` → variant segment boundaries may not align, which can cause ABR switching glitches; bitrate spikes. **Runtime impact NOT VERIFIED.** | Low-Medium | [L327-353](file:///d:/TLTN/movie-recommendation-system/backend/app/services/hls_service.py#L327-L353) |
| H5 | Single-worker guarantee holds only with **one Uvicorn process**; `--workers N` would create N queues/workers. | Info (docs use 1 worker) | [deployment.md L117](file:///d:/TLTN/movie-recommendation-system/docs/deployment.md#L117) |
| H6 | `/status` is unauthenticated and returns raw `processing_error` (FFmpeg stderr may include server paths). | Low-Medium | [movies.py L257-277](file:///d:/TLTN/movie-recommendation-system/backend/app/routers/movies.py#L257-L277) |
| H7 | Source MP4 is publicly downloadable: `/media` mounts the whole tree, and public `MovieDetailSchema.video_url` exposes the source path. | High (licensing) | [main.py L76](file:///d:/TLTN/movie-recommendation-system/backend/app/main.py#L76), [schemas/movie.py L254-257](file:///d:/TLTN/movie-recommendation-system/backend/app/schemas/movie.py#L254-L257) |
| H8 | Docs drift: streaming doc says upload returns 202 and auto-queues encoding; code returns 200 and requires manual trigger; source path format also differs. | Low | [streaming_architecture.md L37-42](file:///d:/TLTN/movie-recommendation-system/docs/streaming_architecture.md#L37-L42) |

---

## 7. Smallest safe integration path (proposal — not implemented)

Keep FFmpeg, HLS output location, Nginx serving, player and queue unchanged. Add R2 **only as a source-video store**.

```mermaid
sequenceDiagram
  participant A as Admin browser
  participant API as FastAPI
  participant R2 as R2 (private bucket)
  participant DB as DB
  participant W as encoding_worker
  A->>API: POST /api/v1/admin/movies/{id}/uploads {filename, content_type, size}
  API->>API: admin check, allow-list type, size ≤ limit
  API->>DB: upload_sessions(pending, object_key, expires_at)
  API-->>A: {session_id, presigned PUT url (≤15 min, Content-Type bound)}
  A->>R2: PUT object (XHR progress, abortable)
  A->>API: POST /uploads/{session_id}/complete
  API->>R2: HeadObject(object_key)
  API->>API: verify size/type; idempotent if already completed
  API->>DB: session=completed; movie.source_storage=r2, source_object_key, status=uploaded
  A->>API: POST /movies/{id}/process-hls  (unchanged)
  W->>R2: download object to temp file
  W->>W: existing FFprobe/FFmpeg pipeline on temp path
  W->>W: delete temp file (finally)
```

Minimal code touch points (future work):

1. `services/storage/r2_client.py` — lazily built boto3 client from env, `presign_put`, `head_object`, `download_to_path`.
2. `models/upload_session.py` + Alembic migration + 2 columns on `movies`.
3. `routers/uploads.py` — `create` and `complete` endpoints, admin-only, with Pydantic schemas.
4. `hls_service.process_hls_conversion` — replace the `os.path.exists` guard with a `resolve_source(movie) -> local_path` context manager (local: return path; r2: download to `tempfile`, cleanup in `finally`).
5. Frontend `uploadMovieVideoDirect()` — reuse XHR progress code, expose `abort()`.
6. Config: `R2_ENDPOINT`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_PRESIGN_EXPIRES_SECONDS`, `R2_MAX_UPLOAD_BYTES` in `.env.example`; `boto3` pinned in requirements.
7. Bucket CORS rule (frontend origins, `PUT`, `Content-Type`, expose `ETag`) — Cloudflare dashboard change, owner action.
8. Tests: botocore `Stubber` for presign/head; session state machine; idempotent completion; ownership/role checks; temp cleanup.

Constraints to respect:

- R2 single PUT has an upper object-size limit (5 GiB per Cloudflare docs); larger files require multipart upload with per-part presigned URLs. Start with single PUT and a 5 GB cap; multipart is optional.
- Presigned URLs must never be logged or persisted; return once in the response.
- Keep the local-upload endpoint working as a fallback until R2 is verified end-to-end.

---

## 8. Verification status summary

| Item | Status |
|---|---|
| R2 credentials valid | Owner evidence only — **NOT VERIFIED** here |
| Write permission on bucket | **NOT VERIFIED** |
| Bucket CORS | **NOT VERIFIED** |
| Cloudflare request-size limit on current upload path | **NOT VERIFIED** |
| FFmpeg encode behaviour | Unit-tested with mocks only (`test_hls_cache_invalidation.py`); real encode **NOT VERIFIED** |
| No R2 objects were created, modified, listed or deleted during this audit | Confirmed |
