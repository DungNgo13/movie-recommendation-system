import { getToken } from './authService';
import type { MovieListItem } from '../models';

import { API_BASE_URL } from '../config';

// ─────────────────────────────────────────────────────────────────────────────
// Shared completion threshold — must match backend COMPLETION_THRESHOLD (95%)
// ─────────────────────────────────────────────────────────────────────────────

/** Percentage at which a movie is considered fully watched. */
export const COMPLETION_THRESHOLD = 95;

/**
 * Shared completion rule used by both guest and authenticated UI.
 * Backend uses the same 95% threshold in history_service.py.
 */
export const isWatchCompleted = (progressPercent: number): boolean =>
  Number.isFinite(progressPercent) && progressPercent >= COMPLETION_THRESHOLD;

// ─────────────────────────────────────────────────────────────────────────────
// Time formatting helper
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Format seconds into zero-padded HH:MM:SS or MM:SS.
 *
 * Examples:
 *   28   → "00:28"
 *   84   → "01:24"
 *   3661 → "01:01:01"
 */
export const formatPlaybackTime = (totalSeconds: number): string => {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = safe % 60;
  if (h > 0) {
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
};

// ─────────────────────────────────────────────────────────────────────────────
// Authenticated API types & helpers
// ─────────────────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────────────────
// Authenticated save / load
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Save watch progress with full timing data (authenticated users).
 *
 * @param keepalive  When true, uses `fetch({ keepalive: true })` so the
 *                   request survives page unload (visibilitychange / beforeunload).
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
    if (import.meta.env.DEV) {
      console.warn('[watch-progress] save error', err);
    }
  }
};

/**
 * Fire-and-forget save for page-exit events (authenticated users).
 * Uses keepalive fetch so the request survives page unload.
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

  try {
    fetch(`${API_BASE_URL}/watch-progress`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
      keepalive: true,
    }).catch(() => {});
  } catch {
    // fetch() itself can throw synchronously in edge cases during unload.
  }
};

/**
 * Fetch resume position for a movie (authenticated users).
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
// Guest (unauthenticated) localStorage tracking
// ─────────────────────────────────────────────────────────────────────────────

const GUEST_HISTORY_KEY = 'guest_watch_history';

/** Custom event name dispatched after guest progress changes. */
export const GUEST_HISTORY_EVENT = 'guest-watch-history-updated';

/**
 * Canonical guest watch entry stored in localStorage.
 * Old entries missing fields are migrated on read.
 */
export interface GuestWatchEntry {
  movie_id: string;
  playback_position_seconds: number;
  duration_seconds: number;
  progress_percent: number;
  is_completed: boolean;
  updated_at: string;  // ISO 8601
}

/**
 * Sanitise a numeric value: reject NaN, Infinity, and negatives.
 * Clamp to optional max. Returns 0 for invalid inputs.
 */
function sanitiseNum(v: unknown, max?: number): number {
  const n = Number(v);
  if (!Number.isFinite(n) || n < 0) return 0;
  return max !== undefined ? Math.min(n, max) : n;
}

/**
 * Migrate a raw localStorage entry (possibly old format) to canonical schema.
 * Old entries may have:
 *   { movie_id, duration_seconds, progress_percent }          — no position
 *   { movie_id, current_time_seconds, duration_seconds, progress_percent } — old field name
 * Canonical entries have:
 *   { movie_id, playback_position_seconds, duration_seconds, progress_percent, is_completed, updated_at }
 */
function migrateEntry(raw: Record<string, unknown>): GuestWatchEntry | null {
  const movieId = raw.movie_id;
  if (typeof movieId !== 'string' || !movieId) return null;

  const duration = sanitiseNum(raw.duration_seconds);
  const percent = sanitiseNum(raw.progress_percent, 100);

  // Derive playback position:
  //  1. canonical field
  //  2. old field name (current_time_seconds)
  //  3. compute from duration × percent
  let position: number;
  if (raw.playback_position_seconds !== undefined) {
    position = sanitiseNum(raw.playback_position_seconds);
  } else if (raw.current_time_seconds !== undefined) {
    position = sanitiseNum(raw.current_time_seconds);
  } else {
    position = duration > 0 ? Math.floor(duration * percent / 100) : 0;
  }

  const completed = typeof raw.is_completed === 'boolean'
    ? raw.is_completed
    : isWatchCompleted(percent);

  const updatedAt = typeof raw.updated_at === 'string' && raw.updated_at
    ? raw.updated_at
    : new Date(0).toISOString();  // epoch fallback for old entries

  return {
    movie_id: movieId,
    playback_position_seconds: Math.floor(position),
    duration_seconds: Math.floor(duration),
    progress_percent: parseFloat(percent.toFixed(2)),
    is_completed: completed,
    updated_at: updatedAt,
  };
}

/**
 * Save watch progress for a guest user into localStorage.
 * Upserts by movie_id — only the latest position per movie is kept.
 * Dispatches a custom event so other components can react.
 */
export const saveGuestWatchProgress = (
  movieId: string,
  currentTimeSeconds: number,
  durationSeconds: number,
): void => {
  const safeDuration = sanitiseNum(durationSeconds);
  const safePosition = sanitiseNum(currentTimeSeconds);

  const progressPercent =
    safeDuration > 0
      ? parseFloat(Math.min((safePosition / safeDuration) * 100, 100).toFixed(2))
      : 0;

  const entry: GuestWatchEntry = {
    movie_id: movieId,
    playback_position_seconds: Math.floor(safePosition),
    duration_seconds: Math.floor(safeDuration),
    progress_percent: progressPercent,
    is_completed: isWatchCompleted(progressPercent),
    updated_at: new Date().toISOString(),
  };

  const history = getGuestWatchHistory();
  const idx = history.findIndex((e) => e.movie_id === movieId);
  if (idx >= 0) {
    history[idx] = entry;
  } else {
    history.push(entry);
  }

  localStorage.setItem(GUEST_HISTORY_KEY, JSON.stringify(history));

  // Notify other components (e.g. HomePage) that guest history changed
  try {
    window.dispatchEvent(new CustomEvent(GUEST_HISTORY_EVENT));
  } catch {
    // SSR safety — window may not exist in tests
  }
};

/**
 * Read the full guest watch history array from localStorage.
 * Migrates old entries on read so callers always get canonical schema.
 */
export const getGuestWatchHistory = (): GuestWatchEntry[] => {
  try {
    const raw = localStorage.getItem(GUEST_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const migrated: GuestWatchEntry[] = [];
    for (const item of parsed) {
      if (item && typeof item === 'object') {
        const entry = migrateEntry(item as Record<string, unknown>);
        if (entry) migrated.push(entry);
      }
    }
    return migrated;
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
