import { getToken } from './authService';
import type { MovieListItem } from '../models';

import { API_BASE_URL } from '../config';

export interface HistoryItem extends MovieListItem {
  watched_at: string;
  playback_position_seconds?: number;
  progress_percent?: number;
  is_completed?: boolean;
}

export interface WatchProgress {
  movie_id: string;
  current_time_seconds: number;
  duration_seconds: number;
  progress_percent: number;
  is_completed: boolean;
  watched_at?: string;
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/**
 * Save watch progress with full timing data.
 * Used during playback for real resume support.
 *
 * @param keepalive  When true, uses `fetch({ keepalive: true })` so the
 *                   request survives page unload (visibilitychange / beforeunload).
 *                   Regular periodic saves should leave this false.
 */
export const saveWatchProgress = async (
  movieId: string,
  currentTimeSeconds: number,
  durationSeconds: number,
  keepalive = false,
): Promise<void> => {
  const token = getToken();
  if (!token) {
    if (import.meta.env.DEV) {
      console.debug('[watch-progress] save skipped — no auth token');
    }
    return;
  }

  const progressPercent =
    durationSeconds > 0
      ? Math.min((currentTimeSeconds / durationSeconds) * 100, 100)
      : 0;

  const payload = {
    movie_id: movieId,
    current_time_seconds: Math.floor(currentTimeSeconds),
    duration_seconds: Math.floor(durationSeconds),
    progress_percent: parseFloat(progressPercent.toFixed(2)),
  };

  if (import.meta.env.DEV) {
    console.debug('[watch-progress] request', {
      method: 'POST',
      endpoint: `${API_BASE_URL}/watch-progress`,
      payload,
      keepalive,
    });
  }

  try {
    const res = await fetch(`${API_BASE_URL}/watch-progress`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive,
    });

    if (import.meta.env.DEV) {
      console.debug('[watch-progress] response', {
        status: res.status,
        ok: res.ok,
      });
    }

    if (!res.ok) {
      console.warn(
        `[watch-progress] save failed: ${res.status} ${res.statusText}`,
      );
    }
  } catch (err) {
    // keepalive requests may throw if the body exceeds 64 KiB, but our
    // payload is tiny (~200 bytes).  Log for diagnostics; do not crash.
    if (import.meta.env.DEV) {
      console.warn('[watch-progress] save error', err);
    }
  }
};

/**
 * Fire-and-forget save intended for page-exit events (beforeunload,
 * visibilitychange → hidden).  Uses `navigator.sendBeacon` when available
 * (most reliable for page unload) and falls back to keepalive fetch.
 */
export const saveWatchProgressBeacon = (
  movieId: string,
  currentTimeSeconds: number,
  durationSeconds: number,
): void => {
  const token = getToken();
  if (!token) return;

  const progressPercent =
    durationSeconds > 0
      ? Math.min((currentTimeSeconds / durationSeconds) * 100, 100)
      : 0;

  const payload = JSON.stringify({
    movie_id: movieId,
    current_time_seconds: Math.floor(currentTimeSeconds),
    duration_seconds: Math.floor(durationSeconds),
    progress_percent: parseFloat(progressPercent.toFixed(2)),
  });

  if (import.meta.env.DEV) {
    console.debug('[watch-progress] beacon save', { movieId, currentTimeSeconds, durationSeconds });
  }

  // sendBeacon cannot set Authorization headers, so use keepalive fetch.
  // keepalive fetch survives page unload as long as the body is < 64 KiB.
  try {
    fetch(`${API_BASE_URL}/watch-progress`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
      keepalive: true,
    }).catch(() => {
      // Swallow — page is closing, nothing useful to do with the error.
    });
  } catch {
    // fetch() itself can throw synchronously in edge cases during unload.
  }
};

/**
 * Fetch resume position for a movie.
 * Returns current_time_seconds = 0 if no record or movie is completed.
 */
export const getWatchProgress = async (movieId: string): Promise<WatchProgress> => {
  const token = getToken();
  const empty: WatchProgress = {
    movie_id: movieId,
    current_time_seconds: 0,
    duration_seconds: 0,
    progress_percent: 0,
    is_completed: false,
  };
  if (!token) return empty;

  try {
    const res = await fetch(`${API_BASE_URL}/watch-progress/${movieId}`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      if (import.meta.env.DEV) {
        console.warn(`[watch-progress] GET progress failed: ${res.status}`);
      }
      return empty;
    }
    const data = await res.json();
    if (import.meta.env.DEV) {
      console.debug('[watch-progress] loaded', {
        savedPosition: data.current_time_seconds,
        duration: data.duration_seconds,
        isCompleted: data.is_completed,
      });
    }
    return data;
  } catch {
    return empty;
  }
};

/**
 * Backward-compatible: record a watch event with only position.
 * Used for the initial page-open record and legacy call sites.
 */
export const recordWatch = async (movieId: string, playbackSeconds: number = 0): Promise<void> => {
  const token = getToken();
  if (!token) return;

  await fetch(`${API_BASE_URL}/history/${movieId}`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ playback_position_seconds: Math.floor(playbackSeconds) }),
  });
};

/**
 * Backward-compatible: get raw playback position from old history endpoint.
 */
export const getWatchStatus = async (movieId: string): Promise<{ playback_position_seconds: number }> => {
  const token = getToken();
  if (!token) return { playback_position_seconds: 0 };

  try {
    const res = await fetch(`${API_BASE_URL}/history/${movieId}`, {
      headers: authHeaders(),
    });
    if (!res.ok) return { playback_position_seconds: 0 };
    return res.json();
  } catch {
    return { playback_position_seconds: 0 };
  }
};

/**
 * Gets the current user's watch history list.
 */
export const getWatchHistory = async (limit = 10): Promise<HistoryItem[]> => {
  const token = getToken();
  if (!token) return [];

  const res = await fetch(`${API_BASE_URL}/history/me?limit=${limit}`, {
    headers: authHeaders(),
  });
  if (!res.ok) return [];
  return res.json();
};

// ─────────────────────────────────────────────────────────────────────────────
// Guest (unauthenticated) localStorage tracking — Cold Start Problem
// ─────────────────────────────────────────────────────────────────────────────

const GUEST_HISTORY_KEY = 'guest_watch_history';

export interface GuestWatchEntry {
  movie_id: string;
  current_time_seconds: number;
  duration_seconds: number;
  progress_percent: number;
}

/**
 * Save watch progress for a guest user into localStorage.
 * Upserts by movie_id — only the latest position per movie is kept.
 */
export const saveGuestWatchProgress = (
  movieId: string,
  currentTimeSeconds: number,
  durationSeconds: number,
): void => {
  const progressPercent =
    durationSeconds > 0
      ? parseFloat(Math.min((currentTimeSeconds / durationSeconds) * 100, 100).toFixed(2))
      : 0;

  const entry: GuestWatchEntry = {
    movie_id: movieId,
    current_time_seconds: Math.floor(currentTimeSeconds),
    duration_seconds: Math.floor(durationSeconds),
    progress_percent: progressPercent,
  };

  const history = getGuestWatchHistory();
  const idx = history.findIndex((e) => e.movie_id === movieId);
  if (idx >= 0) {
    history[idx] = entry;
  } else {
    history.push(entry);
  }

  localStorage.setItem(GUEST_HISTORY_KEY, JSON.stringify(history));
};

/**
 * Read the full guest watch history array from localStorage.
 */
export const getGuestWatchHistory = (): GuestWatchEntry[] => {
  try {
    const raw = localStorage.getItem(GUEST_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

/**
 * Get a single movie's guest progress (for resume prompt).
 */
export const getGuestWatchProgressForMovie = (movieId: string): GuestWatchEntry | null => {
  const history = getGuestWatchHistory();
  return history.find((e) => e.movie_id === movieId) ?? null;
};

/**
 * Remove all guest watch data from localStorage (called after successful login merge).
 */
export const clearGuestWatchHistory = (): void => {
  localStorage.removeItem(GUEST_HISTORY_KEY);
};
