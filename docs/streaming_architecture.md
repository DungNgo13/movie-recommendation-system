# Streaming Architecture

## Overview

The Laetus movie recommendation system includes end-to-end HD video delivery
via HTTP Live Streaming (HLS). This document describes the current
implementation from source upload through frontend playback.

```
Admin upload (.mp4)
  ↓
FastAPI stores source → media/videos/source/
  ↓
HLS encoding queue (asyncio.Queue)
  ↓
Encoding worker (single FFmpeg process)
  ↓
FFprobe: detect resolution + audio
  ↓
FFmpeg: encode variant streams (no upscaling)
  ↓
Output: media/videos/hls/movie_<id>/master.m3u8
  ↓
Database: processing_status → "ready", available_qualities persisted
  ↓
Recommendation cache invalidated (_invalidate_rec_cache)
  ↓
Nginx serves /media/ (production) or FastAPI StaticFiles (dev)
  ↓
Frontend: hls.js parses master.m3u8 → Plyr UI controls
```

---

## 1. Source Upload

**Endpoint:** `POST /api/v1/movies/{id}/video`

- Administrators upload `.mp4` files via the admin Movie Form
- Backend stores the source file at `media/videos/source/<movie_id>.mp4`
- `video_source_path` is saved to the database
- Returns HTTP 202 and queues the encoding job

**Source:** `backend/app/routers/movies.py`, `backend/app/services/movie_service.py`

---

## 2. Encoding Queue

**Architecture:** In-memory async task queue (no Redis or Celery required)

```
POST /process-hls
  ↓
queue_encode_task(movie_id) → encode_queue.put_nowait()
  ↓
Returns HTTP 202 immediately (with queue position)
```

- `encode_queue` is an `asyncio.Queue` (unlimited depth)
- The `encoding_worker` coroutine starts at application boot via the FastAPI
  lifespan context manager
- Strictly one FFmpeg process runs at a time to prevent CPU exhaustion

**Source:** `backend/app/services/hls_service.py` (lines 30–110),
`backend/app/main.py` (lifespan)

---

## 3. Resolution Detection

Before encoding, the worker calls FFprobe to determine:

- **Duration** via `get_video_duration()` — used for progress calculation
- **Width × Height** via `get_video_dimensions()` — used for quality tier selection
- **Audio presence** via `has_audio_stream()` — determines whether to map audio

FFmpeg and FFprobe paths are resolved via `shutil.which()` at import time,
with fallback to `/usr/bin/ffmpeg` and `/usr/bin/ffprobe`.

**Source:** `backend/app/services/hls_service.py` (lines 114–172)

---

## 4. Quality Selection (No Upscaling)

The system selects encoding tiers based on source resolution without
upscaling:

| Source Height | Tiers Produced |
|:---:|---|
| ≥ 2160px | 2160p, 1440p, 1080p, 720p, 480p, 360p |
| ≥ 1440px | 1440p, 1080p, 720p, 480p, 360p |
| ≥ 1080px | 1080p, 720p, 480p, 360p |
| ≥ 720px | 720p, 480p, 360p |
| ≥ 480px | 480p, 360p |
| < 480px | 360p |

Qualities are never generated above the source resolution.

**Source:** `backend/app/services/hls_service.py` (`_build_multi_quality_cmd`)

---

## 5. FFmpeg Processing

### Multi-Quality Attempt (Primary)

- Encodes all selected tiers in a single FFmpeg invocation
- Generates per-tier variant playlists and a `master.m3u8` with
  `#EXT-X-STREAM-INF` entries including `RESOLUTION` tags
- Uses `-hls_time 10` for 10-second segments
- Progress is parsed from FFmpeg's `-progress pipe:2` stderr output
- The running process is registered in `active_encodes` for cancellation

### Single-Quality Fallback

If the multi-quality attempt fails (non-zero exit code or missing
`master.m3u8`):

- Previous partial output is cleaned up
- A single 480p stream is encoded
- On success, `available_qualities` is set to `"480p"`

### Failure Handling

If both attempts fail:
- `processing_status` → `"failed"`
- `processing_error` stores a cleaned FFmpeg error message (last 600 chars)

**Source:** `backend/app/services/hls_service.py` (`process_hls_conversion`,
`_spawn_ffmpeg`)

---

## 6. Database Updates

After successful encoding:

```python
db_movie.processing_status = "ready"
db_movie.hls_playlist_path = "media/videos/hls/movie_<id>/master.m3u8"
db_movie.available_qualities = "720p,360p"  # comma-separated
db_movie.processing_progress = 100
db.commit()
```

### Recommendation Cache Invalidation

After the database commit that sets `processing_status = "ready"`, the
system calls `_invalidate_rec_cache()` from `recommendation.vectorizer`.
This ensures the newly playable movie becomes eligible for recommendations
when `RECOMMEND_ONLY_UPLOADED_MOVIES` is enabled.

Cache invalidation occurs:
- After successful multi-quality conversion (line 483)
- After successful single-quality fallback (line 521)
- NOT after failed or cancelled conversion

**Source:** `backend/app/services/hls_service.py` (lines 475–521)

---

## 7. Cancellation

Administrators can cancel a running encode via `cancel_encode_task()`:
- Kills the FFmpeg subprocess
- Deregisters from `active_encodes`
- Sets `processing_status = "ready"` with `processing_step = "Cancelled"`

The `process_hls_conversion` function checks
`if db_movie.processing_status != "processing"` after `_spawn_ffmpeg`
returns, preventing a cancelled movie from being marked as `"ready"` with
a valid playlist.

**Source:** `backend/app/services/hls_service.py` (`cancel_encode_task`)

---

## 8. Frontend Playback

### HLS Loading (hls.js)

The `HlsPlayer` component (`frontend/src/components/HlsPlayer.tsx`) uses
hls.js for browsers that do not natively support HLS:

1. Creates an `Hls` instance with `maxBufferLength: 30` and
   `enableWorker: true`
2. Cache-busts the master playlist URL with a timestamp parameter
3. Attaches to the `<video>` element

### Player Controls (Plyr)

After `MANIFEST_PARSED`, a Plyr instance wraps the video element:

- Controls: play, rewind, fast-forward, progress, current-time, duration,
  mute, volume, settings, fullscreen
- Settings menu: quality and speed
- Quality options are derived dynamically from the HLS manifest levels

### Quality Switching

- User selection triggers `hls.currentLevel = idx` (no `video.src`
  replacement)
- A `LEVEL_SWITCHED` handler syncs the Plyr quality badge
- `levelSwitchInProgress` flag prevents infinite loops between Plyr's
  `onChange` and the `LEVEL_SWITCHED` handler

### Zombie Prevention

An `isMounted` flag prevents the async `MANIFEST_PARSED` callback from
creating a Plyr instance after the component has unmounted (race condition
guard).

**Source:** `frontend/src/components/HlsPlayer.tsx`

---

## 9. Watch Progress Integration

The HLS player reports watch progress:

- `onTimeUpdate` fires periodically with `(currentTime, duration)`
- `onPause` fires when the user pauses
- `onEnded` fires when playback completes

These callbacks are used by the watch-progress service to persist
`playback_position_seconds`, `progress_percent`, and `is_completed` to the
backend.

**Source:** `frontend/src/components/HlsPlayer.tsx` (callback refs),
`frontend/src/services/continueWatchingService.ts`

---

## 10. Media Serving

### Development

FastAPI serves the `media/` directory as static files.

### Production

Nginx serves `/media/` directly from the filesystem, bypassing the Python
backend for better performance:

```nginx
location /media/ {
    alias /path/to/backend/media/;
    add_header Cache-Control "public, max-age=3600";
}
```

**Source:** `docs/deployment.md`

---

## 11. Dependencies

| Component | Requirement |
|-----------|-------------|
| FFmpeg | Must be installed on the system PATH |
| FFprobe | Bundled with FFmpeg |
| hls.js | npm package (`hls.js`) |
| Plyr | npm package (`plyr`) |

Verify FFmpeg installation: `ffmpeg -version`
