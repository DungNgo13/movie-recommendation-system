import { getToken } from './authService';
import type { MovieListItem } from '../models';

const API_BASE_URL = 'http://localhost:8000/api/v1';

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
 */
export const saveWatchProgress = async (
  movieId: string,
  currentTimeSeconds: number,
  durationSeconds: number,
): Promise<void> => {
  const token = getToken();
  if (!token) return;

  const progressPercent =
    durationSeconds > 0
      ? Math.min((currentTimeSeconds / durationSeconds) * 100, 100)
      : 0;

  await fetch(`${API_BASE_URL}/watch-progress`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      movie_id: movieId,
      current_time_seconds: Math.floor(currentTimeSeconds),
      duration_seconds: Math.floor(durationSeconds),
      progress_percent: parseFloat(progressPercent.toFixed(2)),
    }),
  });
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
    if (!res.ok) return empty;
    return res.json();
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
