# Streaming Architecture & Demo Execution Guide

This document formally outlines the End-to-End HD Video Delivery System established across Phases 1 - 5. 

## Architectural Overview

1. **Ingestion (`backend/app/services/movie_service.py`)** 
   - Administrators post `.mp4` chunks via standard `UploadFile` endpoints.
   - The backend synchronously executes system cleanup (`os.remove` and `shutil.rmtree`), immediately destroying prior stale video outputs preventing Disk I/O bloat dynamically natively.
   - Files are stored as standard chunks locally inside `backend/uploads/videos/source`.

2. **Auto-Background Processing (`backend/app/services/hls_service.py`)**
   - The Rest API returns early yielding a HTTP UI payload natively.
   - Simultaneously, a native `BackgroundTasks` thread invokes `subprocess.run(["ffmpeg"...])` wrapping the exact path locally natively bounding status strings into SQLite organically (`processing` -> `ready` OR `failed`).

3. **Frontend Playback (`frontend/src/components/HlsPlayer.tsx`)**
   - The React API inherently auto-polls status until `ready`.
   - The DOM mounts `hls.js` natively bridging native `<video>` parsing bounds seamlessly resolving Firefox and Google Edge `.m3u8` unrecognition constraints naturally.

---

## Developer Requirements & Dependencies

**Crucial Prerequisite:** 
This application depends *strictly* on native `FFmpeg` being installed within the root Operating System tracking local `$PATH` scopes definitively.

* **Windows:** Install via `winget install ffmpeg` or download binaries explicitly mapping `sysdm.cpl -> Environment Variables`.
* **macOS:** Install via `brew install ffmpeg`.
* **Linux:** Install via `sudo apt install ffmpeg`.

*To verify your execution bounds locally, run `ffmpeg -version` directly inside the primary OS terminal.*

---

## Running a Final Demo End-to-End

### 1. Boot Servers
Ensure Npm and Python natively run side-by-side structurally:
```bash
# Terminal 1 - Boot Backend
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2 - Boot Frontend 
cd frontend
npm run dev
```

### 2. Manual Test Scenario Constraints
1. **Access Web Portal**: Navigate your browser directly tracking `localhost`, engaging an `Admin` log in natively.
2. **Access Detailed Record**: Open a target Movie record inside `<MovieForm>`.
3. **Trigger File Delivery**: Mount a new `Source Video (.mp4)` dynamically parsing your native file dialogue. Look exactly at the React component logic.
4. **Observe Background Magic**: 
   - Observe the string dynamically bounce to `PROCESSING` immediately seamlessly triggering auto-tasks avoiding second manual clicks.
   - Observe React `setInterval` auto-poll without requiring Nginx refreshing. 
   - Wait ~10-30 seconds securely letting native FFmpeg binaries natively push structural matrix outputs into `./uploads/videos/hls`.
5. **Observe Client Rendering**:
   - Status text changes precisely to `READY` mapping the `HLS: http://...` string strictly natively.
6. **Execute Playback**:
   - Leave the Admin screen parsing standard User Home.
   - Click your target Movie rendering `<MovieDetailPage>`.
   - The generic placeholder Image is explicitly removed. 
   - A fully functional `HLS Player` stream inherently natively runs resolving A/V chunks beautifully dynamically natively without buffering constraints natively!
